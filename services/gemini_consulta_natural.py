# gemini_consulta_natural.py
# ==========================================================
# GEMINI — CONSULTA EM LINGUAGEM NATURAL AO BANCO DE DADOS
# ==========================================================
# Permite que o usuário faça perguntas em português,
# o Gemini interpreta, gera SQL, o sistema executa
# e o Gemini explica o resultado.
# ==========================================================

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import google.generativeai as genai

from core.config import DATABASE_URL, ENABLE_GEMINI, GEMINI_API_KEY


# ----------------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------------

load_dotenv()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não encontrada no .env")

model = None


def obter_modelo_gemini():
    global model
    if not ENABLE_GEMINI:
        raise RuntimeError("Gemini desativado: ENABLE_GEMINI=false")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY nao encontrada no .env")
    if model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
    return model


# ----------------------------------------------------------
# CONTEXTO DO BANCO (IMPORTANTE PARA O GEMINI)
# ----------------------------------------------------------

SCHEMA_BANCO = """
Tabelas disponíveis:

1) produtos
- ean (TEXT, PK)
- nome_original (TEXT)
- nome_limpo (TEXT)
- marca (TEXT)
- categoria (TEXT)
- unidade (TEXT)

2) historico_precos
- id (SERIAL, PK)
- ean (TEXT, FK -> produtos.ean)
- data_compra (DATE)
- mercado (TEXT)
- preco_pago (NUMERIC)
- quantidade (NUMERIC)

Relacionamento:
historico_precos.ean -> produtos.ean
"""


# ----------------------------------------------------------
# BANCO
# ----------------------------------------------------------

def conectar():
    return psycopg2.connect(DATABASE_URL)


# ----------------------------------------------------------
# GEMINI → SQL
# ----------------------------------------------------------

def gerar_sql(pergunta: str) -> str:
    gemini_model = obter_modelo_gemini()
    prompt = f"""
Você é um especialista em SQL (PostgreSQL).

Baseado no esquema abaixo, gere APENAS UMA QUERY SQL válida,
sem explicações, sem comentários e sem markdown.

ESQUEMA:
{SCHEMA_BANCO}

REGRAS:
- Use apenas SELECT
- Não use DELETE, UPDATE, INSERT ou DROP
- Sempre limite resultados quando fizer sentido
- Use JOIN corretamente entre as tabelas

PERGUNTA DO USUÁRIO:
"{pergunta}"
"""
    resposta = gemini_model.generate_content(prompt)
    return resposta.text.strip().rstrip(";")


# ----------------------------------------------------------
# EXECUTAR SQL
# ----------------------------------------------------------

def executar_sql(sql: str):
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


# ----------------------------------------------------------
# GEMINI → EXPLICA RESULTADO
# ----------------------------------------------------------

def explicar_resultado(pergunta: str, dados: list[dict]) -> str:
    gemini_model = obter_modelo_gemini()
    prompt = f"""
Você é um analista de dados.

O usuário fez a pergunta:
"{pergunta}"

O resultado retornado pelo banco foi:
{json.dumps(dados, ensure_ascii=False, indent=2)}

Explique o resultado de forma clara,
em português simples, como para um leigo.
"""
    resposta = gemini_model.generate_content(prompt)
    return resposta.text.strip()


# ----------------------------------------------------------
# FLUXO PRINCIPAL
# ----------------------------------------------------------

def main():
    if not ENABLE_GEMINI:
        print("Gemini desativado: ENABLE_GEMINI=false")
        return

    print("\n🧠 CONSULTA EM LINGUAGEM NATURAL (GEMINI)")
    print("=" * 70)

    pergunta = input("Digite sua pergunta (ou ENTER para sair): ").strip()

    if not pergunta:
        print("Encerrando consulta.")
        return

    try:
        print("\n🔎 Interpretando pergunta e gerando SQL...\n")
        sql = gerar_sql(pergunta)
        print("📄 SQL GERADO:")
        print(sql)

        print("\n📊 Executando consulta...\n")
        dados = executar_sql(sql)

        if not dados:
            print("⚠️ Nenhum dado encontrado.")
            return

        print("📋 RESULTADO BRUTO:")
        for linha in dados:
            print(linha)

        print("\n🧠 EXPLICAÇÃO:")
        explicacao = explicar_resultado(pergunta, dados)
        print(explicacao)

    except Exception as e:
        print("\n❌ ERRO NA CONSULTA")
        print(str(e))


# ----------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------

if __name__ == "__main__":
    main()
