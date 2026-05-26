# services/gemini_insights.py
# ==========================================================
# GEMINI — GERADOR DE INSIGHTS (ROBUSTO E AUTODESCUBERTO)
# ==========================================================
# Este módulo:
# - Descobre automaticamente um modelo Gemini válido
# - Funciona mesmo se o Google mudar os nomes
# - Não quebra para aprendiz
# ==========================================================

import sys
import os
import json
from datetime import date
from decimal import Decimal

# ----------------------------------------------------------
# AJUSTE DE PATH (EXECUÇÃO DIRETA)
# ----------------------------------------------------------

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ----------------------------------------------------------
# IMPORTS
# ----------------------------------------------------------

import psycopg2
from psycopg2.extras import DictCursor
import google.generativeai as genai

from core.config import DATABASE_URL, ENABLE_GEMINI, GEMINI_API_KEY
from core.logger import get_logger

logger = get_logger(__name__)

# ----------------------------------------------------------
# CONFIGURAÇÃO DO GEMINI (AUTOMÁTICA)
# ----------------------------------------------------------

model = None


def escolher_modelo_gemini():
    if not ENABLE_GEMINI:
        raise RuntimeError("Gemini desativado: ENABLE_GEMINI=false")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    """
    Lista os modelos disponíveis e escolhe automaticamente
    um que suporte generateContent.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        modelos = genai.list_models()
        for m in modelos:
            if "generateContent" in m.supported_generation_methods:
                logger.info(f"Modelo Gemini selecionado automaticamente: {m.name}")
                return m.name

        raise RuntimeError("Nenhum modelo Gemini compatível encontrado.")

    except Exception as e:
        logger.error(f"Erro ao listar modelos Gemini: {e}")
        raise


def obter_modelo_gemini():
    global model
    if not ENABLE_GEMINI:
        raise RuntimeError("Gemini desativado: ENABLE_GEMINI=false")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY nao configurada")
    if model is None:
        model = genai.GenerativeModel(escolher_modelo_gemini())
    return model

# ----------------------------------------------------------
# BANCO DE DADOS
# ----------------------------------------------------------

def conectar():
    return psycopg2.connect(DATABASE_URL)

# ----------------------------------------------------------
# COLETA DE DADOS
# ----------------------------------------------------------

def coletar_resumo():
    logger.info("Coletando dados consolidados para insights")

    conn = conectar()

    resumo = {
        "data_analise": date.today().isoformat(),
        "total_geral": Decimal("0.00"),
        "por_categoria": [],
        "top_produtos": [],
    }

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT SUM(h.preco_pago * h.quantidade) AS total
                FROM historico_precos h;
            """)
            row = cur.fetchone()
            resumo["total_geral"] = float(row["total"] or 0)

            cur.execute("""
                SELECT
                    COALESCE(NULLIF(TRIM(p.categoria), ''), 'Outros') AS categoria,
                    SUM(h.preco_pago * h.quantidade) AS total
                FROM historico_precos h
                JOIN produtos p ON p.ean = h.ean
                GROUP BY categoria
                ORDER BY total DESC;
            """)
            resumo["por_categoria"] = [
                {"categoria": r["categoria"], "total": float(r["total"])}
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT
                    p.nome_limpo AS produto,
                    SUM(h.preco_pago * h.quantidade) AS total
                FROM historico_precos h
                JOIN produtos p ON p.ean = h.ean
                GROUP BY produto
                ORDER BY total DESC
                LIMIT 10;
            """)
            resumo["top_produtos"] = [
                {"produto": r["produto"], "total": float(r["total"])}
                for r in cur.fetchall()
            ]

    finally:
        conn.close()

    logger.info("Resumo coletado com sucesso")
    return resumo

# ----------------------------------------------------------
# GERAR INSIGHTS
# ----------------------------------------------------------

def gerar_insights(resumo: dict) -> str:
    gemini_model = obter_modelo_gemini()
    logger.info("Gerando insights com Gemini")

    prompt = f"""
Você é um analista financeiro especializado em consumo doméstico.

Analise os dados abaixo e gere INSIGHTS claros, objetivos e úteis.

DADOS (JSON):
{json.dumps(resumo, ensure_ascii=False, indent=2)}

REGRAS:
- Não repetir dados brutos
- Destacar padrões e tendências
- Gerar de 5 a 10 insights numerados
"""

    try:
        resposta = gemini_model.generate_content(prompt)
        return resposta.text.strip()

    except Exception as e:
        logger.error(f"Erro ao gerar insights: {e}")
        return "❌ Não foi possível gerar insights no momento."

# ----------------------------------------------------------
# EXECUÇÃO DIRETA
# ----------------------------------------------------------

def main():
    logger.info("Iniciando Gemini Insights")

    if not ENABLE_GEMINI:
        print("Gemini desativado: ENABLE_GEMINI=false")
        return

    resumo = coletar_resumo()

    if resumo["total_geral"] == 0:
        print("⚠️ Nenhum dado encontrado no banco.")
        return

    insights = gerar_insights(resumo)

    print("\n📊 INSIGHTS DE CONSUMO")
    print("=" * 70)
    print(insights)
    print("=" * 70)

    logger.info("Execução finalizada")


if __name__ == "__main__":
    main()
