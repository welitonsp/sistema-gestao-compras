import os
import time
import json
import psycopg2 
import google.generativeai as genai
from dotenv import load_dotenv

# ==========================================
# 1. FUNÇÕES DE INFRAESTRUTURA (REUTILIZADAS)
# ==========================================

# Conexão com o cofre de senhas (.env)
load_dotenv()
CHAVE_API = os.getenv("GEMINI_API_KEY")
LINK_BANCO = os.getenv("DATABASE_URL")

# Verifica se a IA e o Banco estão configurados
if not CHAVE_API or not LINK_BANCO:
    print("❌ ERRO DE CONFIGURAÇÃO: Verifique o arquivo .env.")
    exit()

# Inicializa o Gemini
genai.configure(api_key=CHAVE_API)
model = genai.GenerativeModel('models/gemini-2.5-flash')

# Funções de Banco de Dados
def conectar():
    return psycopg2.connect(LINK_BANCO)

def iniciar_tabelas():
    # Esta função estava faltando e causou o erro!
    try:
        print("🔌 Tentando conectar ao Banco Neon...")
        conn = conectar()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                ean TEXT PRIMARY KEY,
                nome_original TEXT,
                nome_limpo TEXT,
                marca TEXT,
                categoria TEXT,
                unidade TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_precos (
                id SERIAL PRIMARY KEY,
                ean TEXT,
                data_compra DATE,
                mercado TEXT,
                preco_pago NUMERIC(10,2),
                quantidade NUMERIC(10,3)
            );
        """)
        conn.commit()
        conn.close()
        print("✅ CONECTADO AO NEON COM SUCESSO E TABELAS VERIFICADAS!")
    except Exception as e:
        print(f"❌ Erro ao conectar no Neon: {e}")
        exit()

def produto_ja_existe(ean):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT nome_limpo FROM produtos WHERE ean = %s", (ean,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def salvar_produto(ean, original, limpo, marca, categoria, unidade):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO produtos (ean, nome_original, nome_limpo, marca, categoria, unidade)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ean) DO NOTHING;
    """, (ean, original, limpo, marca, categoria, unidade))
    conn.commit()
    conn.close()

def salvar_compra(ean, data, mercado, preco, qtd):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historico_precos (ean, data_compra, mercado, preco_pago, quantidade)
        VALUES (%s, %s, %s, %s, %s);
    """, (ean, data, mercado, preco, qtd))
    conn.commit()
    conn.close()

def consultar_ia(nome_sujo):
    print(f"   🤖 IA Lendo: '{nome_sujo}'...")
    prompt = f"""Analise: "{nome_sujo}". Retorne JSON: {{"produto": "nome", "marca": "marca", "categoria": "categoria", "unidade": "unidade"}}"""
    try:
        res = model.generate_content(prompt)
        texto = res.text.replace("```json", "").replace("```", "").strip()
        time.sleep(1)
        return json.loads(texto)
    except:
        return {"produto": nome_sujo, "marca": "", "categoria": "Outros", "unidade": ""}

# ==========================================
# 2. PARSER DE ARQUIVO MANUAL (A LÓGICA NOVA)
# ==========================================

def parse_e_processar_txt(caminho_arquivo):
    print(f"\n📂 Iniciando importação manual: {caminho_arquivo}")

    # --- 2.1 Coleta de dados Faltantes ---
    data_compra = input("➡️ Digite a Data da Compra (AAAA-MM-DD): ").strip()
    nome_mercado = input("➡️ Digite o Nome do Mercado: ").strip()
    
    if not data_compra or not nome_mercado:
        print("❌ Data e Mercado são obrigatórios. Abortando.")
        return

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {caminho_arquivo}")
        return

    # Remove o cabeçalho e linhas em branco
    linhas = [l.strip() for l in linhas if l.strip() and not l.startswith('Num.')]
    
    itens_processados = 0
    
    for linha in linhas:
        # Lógica de extração de dados do texto
        partes = linha.split()
        
        # Pega o Valor no final
        try:
            valor_str = partes[-1].replace(',', '.')
            preco_total = float(valor_str)
        except:
            continue

        # Tenta pegar a Qtd (é o terceiro valor de trás para frente, ignorando a Unidade e o Preço)
        try:
            qtd_str = partes[-3].replace(',', '.')
            qtd = float(qtd_str)
        except:
            qtd = 1.0 

        # A Descrição (nome do produto) é todo o resto
        try:
            nome_original = " ".join(partes[1:-3]) # Começa após o Num. e para antes da Qtd
        except:
             nome_original = " ".join(partes[1:-3])

        if not nome_original or nome_original.lower() in ['descrição', 'comercial', 'valor(r$)']: continue

        # Calcula o preço unitário (necessário para rastreamento de preço)
        preco_unitario = preco_total / qtd if qtd > 0 else 0.0

        # --- LÓGICA DE CADASTRO ---
        # Cria um ID ÚNICO baseado no NOME (já que o EAN não existe no TXT)
        ean_temp = f"MANUAL_{abs(hash(nome_original))}"

        if not produto_ja_existe(ean_temp):
            print(f"🆕 Novo item: {nome_original}")
            dados_ia = consultar_ia(nome_original)
            
            salvar_produto(
                ean_temp, nome_original, dados_ia['produto'], 
                dados_ia['marca'], dados_ia['categoria'], dados_ia['unidade']
            )
        else:
            print(f"✅ Item conhecido: {nome_original}")
            
        salvar_compra(ean_temp, data_compra, nome_mercado, preco_unitario, qtd)
        itens_processados += 1
        
    print(f"\n🏁 Processamento Manual Finalizado! {itens_processados} itens salvos no Neon.")


if __name__ == "__main__":
    # Garante que as tabelas estão prontas (agora a função existe!)
    iniciar_tabelas() 
    
    # O arquivo deve se chamar 'manual_extract.txt'
    parse_e_processar_txt('manual_extract.txt')