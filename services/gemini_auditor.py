# gemini_auditor.py
# ======================================================
# GEMINI — AUDITOR DE CLASSIFICAÇÕES DE PRODUTOS
# ======================================================

import os
import json
from datetime import date

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import google.generativeai as genai


# ------------------------------------------------------
# CONFIGURAÇÃO
# ------------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não encontrada no .env")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY não encontrada no .env")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ------------------------------------------------------
# BANCO
# ------------------------------------------------------

def conectar():
    return psycopg2.connect(DATABASE_URL)


# ------------------------------------------------------
# COLETA DE AMOSTRA
# ------------------------------------------------------

def coletar_amostra(limit: int = 25):
    """
    Coleta uma amostra recente de produtos classificados
    para auditoria cognitiva.
    """
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    p.nome_original,
                    p.nome_limpo,
                    p.marca,
                    p.categoria,
                    p.unidade
                FROM produtos p
                ORDER BY RANDOM()
                LIMIT %s;
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ------------------------------------------------------
# AUDITORIA COM GEMINI
# ------------------------------------------------------

def auditar(amostra: list[dict]) -> str:
    """
    Envia a amostra para o Gemini e recebe um relatório
    de auditoria qualitativa.
    """
    prompt = f"""
Você é um auditor de dados especializado em classificação
de produtos de supermercado.

Receberá uma AMOSTRA de produtos já classificados.
Seu trabalho é identificar POSSÍVEIS PROBLEMAS, como:
- Categoria inadequada
- Nome limpo inconsistente
- Unidade improvável
- Marca ausente quando deveria existir

DADOS (JSON):
{json.dumps(amostra, ensure_ascii=False, indent=2)}

Regras:
- NÃO reescreva todos os dados
- Liste apenas itens com possível problema
- Explique o motivo da suspeita
- Sugira correção quando possível
- Seja conservador (apenas quando houver boa evidência)

Formato da resposta:
1. [PROBLEMA] descrição
2. [PROBLEMA] descrição
"""

    resposta = model.generate_content(prompt)
    return resposta.text.strip()


# ------------------------------------------------------
# FLUXO PRINCIPAL
# ------------------------------------------------------

def main():
    print("\n🧪 INICIANDO AUDITORIA INTELIGENTE (GEMINI)\n")

    amostra = coletar_amostra(limit=25)

    if not amostra:
        print("⚠️ Nenhum produto encontrado para auditoria.")
        return

    relatorio = auditar(amostra)

    print("📋 RELATÓRIO DE AUDITORIA DE CLASSIFICAÇÕES")
    print("=" * 70)
    print(f"Data da auditoria: {date.today().isoformat()}\n")
    print(relatorio)
    print("=" * 70)


if __name__ == "__main__":
    main()
