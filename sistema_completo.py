import os
import glob
import time
import json
import xml.etree.ElementTree as ET
import psycopg2 
import google.generativeai as genai

# ==========================================
# 1. FUNÇÃO DE LEITURA MANUAL (A SALVA-VIDAS)
# ==========================================
def ler_env_manual():
    """Lê o arquivo .env linha por linha sem depender de bibliotecas externas."""
    chaves = {}
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                # Pula linhas vazias ou comentários
                if not linha or linha.startswith("#"): continue
                
                # Separa a Chave do Valor (ex: CHAVE=VALOR)
                if "=" in linha:
                    parte_chave, parte_valor = linha.split("=", 1)
                    # Remove as aspas se tiver
                    valor_limpo = parte_valor.strip().strip('"').strip("'")
                    chaves[parte_chave.strip()] = valor_limpo
        return chaves
    except FileNotFoundError:
        print("❌ ERRO CRÍTICO: O arquivo .env não foi encontrado na pasta!")
        print(f"Pasta atual: {os.getcwd()}")
        return {}
    except Exception as e:
        print(f"❌ Erro ao ler .env: {e}")
        return {}

# ==========================================
# 2. CONFIGURAÇÃO
# ==========================================
# Carrega as chaves usando nossa função manual
config = ler_env_manual()

CHAVE_API = config.get("GEMINI_API_KEY")
LINK_BANCO = config.get("DATABASE_URL")

# Diagnóstico na tela para você ver o que está acontecendo
print("-" * 40)
print("🔍 DIAGNÓSTICO INICIAL")
if CHAVE_API:
    print(f"✅ Chave Google encontrada: {CHAVE_API[:5]}... (Oculta)")
else:
    print("❌ Chave Google NÃO encontrada.")

if LINK_BANCO:
    print(f"✅ Banco Neon encontrado: {LINK_BANCO[:15]}...")
else:
    print("❌ Banco Neon NÃO encontrado.")
print("-" * 40)

# Verificação final antes de continuar
if not CHAVE_API or "COLE_SUA" in CHAVE_API:
    print("❌ ERRO: A chave do Google está inválida ou não foi lida.")
    exit()

if not LINK_BANCO:
    print("❌ ERRO: O link do Banco de Dados não foi encontrado.")
    exit()

# Configura a IA
genai.configure(api_key=CHAVE_API)
model = genai.GenerativeModel('models/gemini-2.5-flash')

# ==========================================
# 3. BANCO DE DADOS
# ==========================================
def conectar():
    return psycopg2.connect(LINK_BANCO)

def iniciar_tabelas():
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
        print("✅ CONECTADO AO NEON COM SUCESSO!")
    except Exception as e:
        print(f"❌ Erro ao conectar no Neon: {e}")
        exit()

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

def produto_ja_existe(ean):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT nome_limpo FROM produtos WHERE ean = %s", (ean,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# ==========================================
# 4. INTELIGÊNCIA ARTIFICIAL
# ==========================================
def consultar_ia(nome_sujo):
    print(f"   🤖 IA Lendo: '{nome_sujo}'...")
    prompt = f"""Analise: "{nome_sujo}". Retorne JSON: {{"produto": "nome", "marca": "marca", "categoria": "categoria", "unidade": "unidade"}}"""
    try:
        res = model.generate_content(prompt)
        texto = res.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except:
        return {"produto": nome_sujo, "marca": "", "categoria": "Outros", "unidade": ""}

# ==========================================
# 5. PROCESSAMENTO
# ==========================================
def ler_xml_e_processar(caminho):
    print(f"\n📂 Processando: {caminho}")
    try:
        tree = ET.parse(caminho)
        root = tree.getroot()
        for elem in root.iter():
            if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]
            
        mercado = root.find(".//emit/xNome").text if root.find(".//emit/xNome") is not None else "Desconhecido"
        data = root.find(".//dhEmi").text.split('T')[0] if root.find(".//dhEmi") is not None else "2024-01-01"
        itens = root.findall(".//det")

        if not itens: 
            print("⚠️ Nenhum item no XML.")
            return

        print(f"🛒 {mercado} | 📅 {data}")

        for item in itens:
            prod = item.find("prod")
            nome = prod.find("xProd").text
            ean = prod.find("cEAN").text
            if not ean or ean == "SEM GTIN": ean = f"GEN_{abs(hash(nome))}"
            
            try: qtd = float(prod.find("qCom").text)
            except: qtd = 1.0
            try: preco = float(prod.find("vUnCom").text)
            except: preco = 0.0

            if not produto_ja_existe(ean):
                print(f"🆕 Novo: {nome}")
                dados = consultar_ia(nome)
                salvar_produto(ean, nome, dados['produto'], dados['marca'], dados['categoria'], dados['unidade'])
            
            salvar_compra(ean, data, mercado, preco, qtd)

    except Exception as e:
        print(f"❌ Erro no arquivo: {e}")

if __name__ == "__main__":
    iniciar_tabelas()
    lista_xml = glob.glob("*.xml")
    
    if lista_xml:
        for arq in lista_xml:
            ler_xml_e_processar(arq)
            time.sleep(1)
        print("\n🏁 FINALIZADO COM SUCESSO!")
    else:
        print("⚠️ Tudo conectado! Mas não achei arquivos .xml na pasta para processar.")