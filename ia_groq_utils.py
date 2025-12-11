import os
import time
import json
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from groq import Groq

from classificador_regras import aplicar_regras_nome_categoria

# ==========================================
# 1. CONFIGURAÇÃO INICIAL
# ==========================================

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Groq (IA)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # Modelo atual e suportado

# Configuração do Banco de Dados
LINK_BANCO = os.getenv("DATABASE_URL")

# Validação das configurações essenciais
if not GROQ_API_KEY:
    print("❌ ERRO: Chave da API do Groq não encontrada no arquivo .env.")
    print("   Edite o arquivo .env e adicione: GROQ_API_KEY=sua_chave_aqui")
    raise SystemExit(1)

if not LINK_BANCO:
    print("❌ ERRO: URL do banco de dados não encontrada no arquivo .env.")
    print("   Edite o arquivo .env e adicione: DATABASE_URL=sua_url_de_conexao")
    raise SystemExit(1)

# Inicializa cliente Groq
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
    print(f"✅ Cliente Groq inicializado com modelo: {GROQ_MODEL}")
except Exception as e:
    print(f"❌ ERRO ao inicializar cliente Groq: {e}")
    raise SystemExit(1)

# ==========================================
# 2. FUNÇÕES DE INFRAESTRUTURA
# ==========================================


# Funções de Banco de Dados (PostgreSQL)
def conectar():
    """Estabelece conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(LINK_BANCO)
        return conn
    except psycopg2.Error as e:
        print(f"❌ ERRO ao conectar ao banco de dados: {e}")
        raise


def criar_tabelas_se_nao_existirem():
    """Cria as tabelas necessárias se não existirem."""
    conn = conectar()
    cursor = conn.cursor()

    try:
        # Tabela de produtos
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS produtos (
            ean VARCHAR(50) PRIMARY KEY,
            nome_original TEXT NOT NULL,
            nome_limpo VARCHAR(255) NOT NULL,
            marca VARCHAR(100),
            categoria VARCHAR(100) NOT NULL,
            unidade VARCHAR(20) NOT NULL
        );
        """
        )

        # Tabela de histórico de preços
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS historico_precos (
            id SERIAL PRIMARY KEY,
            ean VARCHAR(50) REFERENCES produtos(ean),
            data_compra DATE NOT NULL,
            mercado VARCHAR(255) NOT NULL,
            preco_pago NUMERIC(10,2) NOT NULL,
            quantidade NUMERIC(10,3) NOT NULL
        );
        """
        )

        conn.commit()
        print("✅ Tabelas verificadas/criadas com sucesso")
    except Exception as e:
        print(f"❌ ERRO ao criar tabelas: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def produto_ja_existe(id_produto: str) -> bool:
    """Verifica se um produto já existe no banco de dados."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nome_limpo FROM produtos WHERE ean = %s", (id_produto,))
        res = cursor.fetchone()
        return res is not None
    finally:
        cursor.close()
        conn.close()


def salvar_produto(id_produto, original, limpo, marca, categoria, unidade):
    """Salva um produto no banco de dados."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO produtos (ean, nome_original, nome_limpo, marca, categoria, unidade)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ean) DO NOTHING;
        """,
            (id_produto, original, limpo, marca, categoria, unidade),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def salvar_compra(id_produto, data, mercado, preco, qtd):
    """Salva uma compra no histórico de preços."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO historico_precos (ean, data_compra, mercado, preco_pago, quantidade)
            VALUES (%s, %s, %s, %s, %s);
        """,
            (id_produto, data, mercado, preco, qtd),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# ==========================================
# 3. CAMADA DE IA (GROQ) + REGRAS
# ==========================================


def consultar_ia(nome_sujo: str) -> dict:
    """
    Consulta a IA para classificar um produto usando Groq
    e, em seguida, aplica regras fixas para padronizar
    NOME e CATEGORIA.
    """
    print(
        f"   🤖 IA (Groq) processando: '{nome_sujo[:60]}{'...' if len(nome_sujo) > 60 else ''}'"
    )

    # Prompt detalhado em português
    prompt = (
        "Você é um especialista em classificação de produtos de supermercado.\n"
        "Analise a descrição abaixo e extraia as informações solicitadas.\n\n"
        f"DESCRIÇÃO DO PRODUTO: \"{nome_sujo}\"\n\n"
        "Retorne APENAS um JSON válido com estas chaves:\n"
        '- "produto": nome limpo e curto do produto (ex: LEITE INTEGRAL, ARROZ PARBOILIZADO)\n'
        '- "marca": marca do produto (ex: NESTLÉ, COCA-COLA, TIROLEZ). Se não identificar, deixe vazio.\n'
        '- "categoria": categoria principal (ex: LATICÍNIOS, BEBIDAS, LIMPEZA, HIGIENE PESSOAL)\n'
        '- "unidade": unidade de medida (ex: kg, g, l, ml, un, pct, cx)\n\n'
        "IMPORTANTE:\n"
        "1. Use SEMPRE português do Brasil\n"
        '2. Se a categoria não for óbvia, use: "Outros"\n'
        '3. Se a unidade não for óbvia, tente identificar pelo contexto ou use "un"\n'
        "4. NÃO adicione texto extra além do JSON\n"
        "5. NÃO inclua comentários ou explicações"
    )

    try:
        # Chamada à API do Groq com parâmetros otimizados
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um especialista em análise de dados de supermercado. "
                        "Suas respostas são sempre em formato JSON válido sem conteúdo extra."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            model=GROQ_MODEL,
            temperature=0.2,  # Baixa temperatura para respostas consistentes
            max_tokens=250,
            response_format={"type": "json_object"},  # Força resposta em JSON
        )

        # Processa a resposta
        resposta_bruta = chat_completion.choices[0].message.content.strip()
        dados = json.loads(resposta_bruta)

        # Monta objeto básico vindo da IA
        resultado = {
            "produto": str(dados.get("produto", nome_sujo)).strip() or nome_sujo,
            "marca": str(dados.get("marca", "")).strip(),
            "categoria": str(dados.get("categoria", "Outros")).strip() or "Outros",
            "unidade": str(dados.get("unidade", "un")).strip() or "un",
        }

        # Aplica camada de regras para padronizar nome/categoria
        produto_final, categoria_final = aplicar_regras_nome_categoria(
            nome_original=nome_sujo,
            nome_ia=resultado["produto"],
            categoria_ia=resultado["categoria"],
        )
        resultado["produto"] = produto_final
        resultado["categoria"] = categoria_final

        # Pequeno atraso para evitar rate limiting
        time.sleep(0.5)

        print(f"   ✅ IA retornou: {resultado['produto']} ({resultado['categoria']})")
        return resultado

    except Exception as e:
        print(f"   ⚠️ Erro na IA: {str(e)[:100]}")
        # Fallback seguro quando a IA falha
        resultado = {
            "produto": nome_sujo,
            "marca": "",
            "categoria": "Outros",
            "unidade": "un",
        }
        try:
            produto_final, categoria_final = aplicar_regras_nome_categoria(
                nome_original=nome_sujo,
                nome_ia=resultado["produto"],
                categoria_ia=resultado["categoria"],
            )
            resultado["produto"] = produto_final
            resultado["categoria"] = categoria_final
        except Exception:
            # Se der qualquer erro nas regras, mantém o básico
            pass
        return resultado


# ==========================================
# 4. EXTRAÇÃO DE DADOS DO PDF (SIMULADO)
# ==========================================


def extrair_dados_pdf(caminho_arquivo):
    """
    Simula a extração de dados de um PDF de nota fiscal.
    Em produção, substitua esta função por um extrator real de PDF/OCR.
    """
    print(f"📄 Lendo dados do PDF: {caminho_arquivo}")

    # Extração de dados simulada (baseada nos dados do exemplo)
    data_compra = "2025-06-16"  # Data do exemplo
    nome_mercado = "ATACADAO DIA A DIA S.A"

    # Lista de itens da nota fiscal (dados do exemplo)
    itens = [
        ("5428", "JARDINEIRA CONG DEMARCHI 1.02kg C MILHO", 1.000, 17.99),
        ("10456", "EMP PERDIGAO BIG CHICKEN 1kg TRAD", 1.000, 26.99),
        ("4704", "FILEZINHO SASSAMI SUPER FRANGO IQF FGO", 1.000, 21.99),
        ("1821", "PETIT SUISSE TREVINHO LANCHE 70G MOR", 4.000, 1.99),
        ("15416", "LING FRANGO LAR FININHA CONG PCT 1K NG PCT 1", 1.000, 16.49),
        ("2327", "QJO MUSS DEALE 400G FAT", 1.000, 15.99),
        ("10368", "PATE SADIA 100G PEITO PERU", 1.000, 4.39),
        ("2327", "QJO MUSS DEALE 400G FAT", 1.000, 15.99),
        ("15685", "IOG LIQ TREVINHO 1.100kg MOR", 1.000, 7.99),
        ("5284", "IOG FRUTAP 850G ACAI BAN", 1.000, 8.79),
        ("16089", "CR RICOTA LIGHT TIROLEZ 370G", 1.000, 12.49),
        ("5110", "GRANOLA NATUREZA E CIA 800G MIX", 1.000, 14.99),
        ("13495", "BOLINHO RECH BAUDUCCO 40G CHOC BAUN CHOC BAU", 16.000, 1.79),
        ("2952", "PAO FORMA SEVENBOYS 450G LEITE", 2.000, 8.99),
        ("2893", "PAO FORMA INTG DI NAPOLI 500G TRAD", 2.000, 7.79),
        ("20294", "ROSQUINHA ADORALLE 600G COCO", 1.000, 7.39),
        ("12446", "BISC RECH OREO 36G CHOC", 8.000, 2.29),
        ("11383", "BISC INTG CLUB SOCIAL 288G ORIG", 1.000, 8.99),
        ("8099", "BOMBOM CX LACTA 250.6G BRAND MIX", 1.000, 11.99),
        ("918", "ARROZ PATOSUL 5kg TP1", 1.000, 18.99),
        ("8101", "BOMBOM CX TORTUGUITA 134.5G", 1.000, 8.79),
        ("10511", "MOLHO TOM POMAROLA CASEIRO SCH 300G MANJERIC", 1.000, 4.39),
        ("10510", "MOLHO TOM POMAROLA CASEIRO SCH 300G CLASSIC", 1.000, 4.39),
        ("6211", "SALG ANELITOS 41G CEB", 2.000, 2.99),
        ("9008", "FEIJÃO DA MAMAE 1kg CARIOCA", 1.000, 4.99),
        ("9008", "FEIJÃO DA MAMAE 1kg CARIOCA", 1.000, 4.99),
        ("6235", "SALG KARITOS 40G BACON", 6.000, 1.99),
        ("12351", "CAFE PILAO POUCH 500G TRAD", 1.000, 27.99),
        ("13277", "BISC RECH CLUB SOCIAL 141G CEB SOUR", 1.000, 4.79),
        ("7928", "BISC MARILAN PIT STOP 137G PAO NA CHAPA", 1.000, 4.99),
        ("15577", "BATATA CRONY 35G CHURR 35G CHURR", 3.000, 2.79),
        ("16197", "SALG SKINY 60G ORIG", 2.000, 1.99),
        ("4171", "OVO STA CLARA PVC 30UN BCO", 1.000, 17.99),
        ("13277", "BISC RECH CLUB SOCIAL 141G CEB SOUR", 1.000, 4.79),
        ("13457", "GELATINA APTI 20G MARAC", 1.000, 1.39),
        ("6899", "TEMP TEMPERE 30G ANA MARIA", 1.000, 2.59),
        ("6898", "TEMP TEMPERE 30G ALHO CEB TOM", 1.000, 3.59),
        ("17992", "GELATINA DR OETKER SCH C 2 INCOLOR 2 INCOLO", 1.000, 6.79),
        ("6211", "SALG ANELITOS 41G CEB", 1.000, 2.99),
        ("13003", "GARFO MESA TRAMONTINA LEME VERM", 6.000, 1.99),
        ("3973", "MOSTARDA BONARE 190G AMARELA", 1.000, 6.99),
        ("13415", "REFR PO TANG 18G UVA", 4.000, 0.99),
        ("13414", "REFR PO TANG 18G MARAC", 6.000, 0.99),
        ("12694", "SARDINHA 88 MANJUBA BOCA TORTA 125G TOM", 3.000, 6.39),
        ("1052", "AZEITE PORT ANDORINHA 500ML TP UNICO PURO", 1.000, 34.90),
        ("12622", "OLEO SOJA VILA VELHA 900ML", 1.000, 6.49),
        ("3550", "MEL PIMEL 1kg", 1.000, 39.99),
        ("12467", "MAC INST CUP NOODLES 65G COSTELA CHURR", 1.000, 4.29),
        ("12466", "MAC INST CUP NOODLES 65G GALINHA PIC", 2.000, 4.29),
        ("12457", "MAC INST CUP NOODLES 65G GALINHA CAIP", 1.000, 4.29),
        ("21127", "EXT TOM ELEFANTE PT 300G CARNE PANELA", 1.000, 7.79),
        ("14146", "SUCO MISTO SUMMER VIBES 1L MARAC UVA BCA", 1.000, 9.99),
        ("14105", "SUCO MISTO SUMMER VIBES 1L ABAC MACA UVA", 1.000, 9.99),
        ("6121", "VINAGRE ALCOOL CASTELO 750ML LIMAO", 1.000, 6.79),
        ("4333", "LENCO UMED SELECT WIPES BABY 100UN", 1.000, 9.99),
        ("21723", "TABUA PLASTICO INGA ESTAMPADA", 1.000, 12.99),
        ("2131", "PRENDEDOR CAB BELLISSIMA 3UN MEDIO", 1.000, 5.79),
        ("14878", "SAND HAVAIANAS SLIM FEM 312 ROSA BALLET", 1.000, 28.99),
        ("11405", "SAB LIQ GRANADO BEBE REF 250ML ERVA DOCE", 1.000, 15.49),
        ("10639", "ESPUMA BARB GILLETTE 150G SENS", 1.000, 19.99),
        ("12963", "DEO AERO NIVEA MASC 200ML BLACK WHITE", 1.000, 17.49),
        ("10036", "ENX BUCAL ORAL B L500 P300 COMPL HORT", 1.000, 15.99),
        ("6512", "SH OX 400ML LISOS", 1.000, 23.99),
        ("11055", "DEO AERO NIVEA MASC 150ML SENS PROT", 1.000, 14.99),
        ("11528", "LIMP PERF VEJA 2L FLORES", 1.000, 9.99),
        ("5537", "PACK TIRA MANCHAS GEL VANISH 1.2L BCO ROSA", 1.000, 53.99),
        ("541", "BANANA PRATA kg", 2.410, 5.99),
        ("14322", "PASTILHA SANIT INSPIRA 3UN MARINE", 1.000, 5.79),
        ("15609", "CR DENT SORRISO XTREME 140G FRESH MINT", 1.000, 5.99),
        ("16214", "DIFUSOR COALA 100ML TANG PATCHOULI", 2.000, 11.99),
        ("14125", "SAB FRANCIS BRASILIDADES 80G LARANJA", 1.000, 2.79),
        ("5595", "LAVA ROUPAS LIQ OMO 3L PURO CUIDADO", 1.000, 39.99),
        ("5577", "LAVA ROUPAS LIQ BRILHANTE 3L LIMP TOTAL", 1.000, 39.99),
        ("11374", "LIMP LIMPEZA PESADA AJAX 1L LIMAO", 1.000, 17.49),
        ("13253", "AMAC YPE 2L DELICADO", 1.000, 11.49),
        ("6629", "SODA CAUSTICA SOL 1kg", 1.000, 21.99),
    ]

    print(f"✅ Dados extraídos: {len(itens)} itens encontrados")
    return data_compra, nome_mercado, itens


# ==========================================
# 5. LÓGICA DE EXECUÇÃO PRINCIPAL
# ==========================================


def importar_pdf_direto(caminho_pdf: str):
    """Processa um PDF de nota fiscal e salva os dados no banco."""
    print("\n" + "=" * 60)
    print(f"🚀 INICIANDO IMPORTAÇÃO: {os.path.basename(caminho_pdf)}")
    print("=" * 60)

    # 1. Extrai os dados do PDF
    try:
        data_compra, nome_mercado, itens = extrair_dados_pdf(caminho_pdf)
    except Exception as e:
        print(f"❌ Erro ao extrair dados do PDF: {e}")
        return

    if not itens:
        print("❌ Erro: Não foi possível extrair os itens da nota.")
        return

    print(f"\n🛒 Mercado: {nome_mercado}")
    print(f"📅 Data da compra: {data_compra}")
    print(f"📦 Total de itens na nota: {len(itens)}")
    print("-" * 50)

    # 2. Processa cada item
    itens_processados = 0
    itens_novos = 0

    for id_prod, nome_original, qtd, preco_unit in itens:
        # Usa o código interno como identificador único (ATENÇÃO: isso é apenas para demonstração)
        # Em produção, você deve usar o EAN/código de barras real
        id_unico = str(id_prod)

        try:
            # Verifica se o produto já existe
            if produto_ja_existe(id_unico):
                print(
                    f"✅ Produto conhecido [{id_unico}]: {nome_original[:40]}{'...' if len(nome_original) > 40 else ''}"
                )
                dados_ia = None  # Não precisa consultar a IA novamente
            else:
                print(
                    f"🆕 Produto novo [{id_unico}]: {nome_original[:40]}{'...' if len(nome_original) > 40 else ''}"
                )
                dados_ia = consultar_ia(nome_original)
                itens_novos += 1

                # Salva o produto no banco
                salvar_produto(
                    id_unico,
                    nome_original,
                    dados_ia["produto"],
                    dados_ia["marca"],
                    dados_ia["categoria"],
                    dados_ia["unidade"],
                )
                print(
                    f"   💾 Produto salvo: {dados_ia['produto']} ({dados_ia['categoria']})"
                )

            # Salva a compra no histórico
            salvar_compra(id_unico, data_compra, nome_mercado, preco_unit, qtd)
            itens_processados += 1

        except Exception as e:
            print(f"   ❌ Erro ao processar item [{id_unico}]: {str(e)[:80]}")
            continue

    print("-" * 50)
    print("✅ IMPORTAÇÃO CONCLUÍDA!")
    print(f"   Itens processados: {itens_processados}/{len(itens)}")
    print(f"   Novos produtos: {itens_novos}")
    print(f"   Data de processamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# ==========================================
# 6. PONTO DE ENTRADA DO PROGRAMA
# ==========================================


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📊 SISTEMA DE GESTÃO DE COMPRAS")
    print("=" * 60)

    # Verifica conexão com a IA
    print("\n🔍 Verificando conexão com a IA (Groq)...")
    try:
        _ = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": "OK"}],
            model=GROQ_MODEL,
            max_tokens=2,
        )
        print("✅ Conexão com Groq estabelecida com sucesso!")
    except Exception as e:
        print(f"❌ Erro de conexão com Groq: {e}")
        print("   Verifique sua chave de API no arquivo .env")
        raise SystemExit(1)

    # Cria tabelas se necessário
    print("\n🗃️  Verificando estrutura do banco de dados...")
    criar_tabelas_se_nao_existirem()

    # Processa o PDF (nome simbólico - pode ou não existir, pois os dados são simulados)
    nome_arquivo_pdf = "b5c8f464-ba83-4a53-88d4-2667ea9896e9.pdf"
    print(f"\n📄 Arquivo a ser processado: {nome_arquivo_pdf}")

    if not os.path.exists(nome_arquivo_pdf):
        print(
            f"\n⚠️  ATENÇÃO: O arquivo '{nome_arquivo_pdf}' não foi encontrado no diretório atual."
        )
        print(
            "   Coloque o arquivo PDF neste diretório ou atualize o nome do arquivo no código."
        )
        print("   Continuando com dados simulados para demonstração...")

    # Executa a importação
    importar_pdf_direto(nome_arquivo_pdf)

    print("\n✨ Processo finalizado! Verifique seus dados no banco de dados.")
