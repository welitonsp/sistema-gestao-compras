# ia_groq_utils.py
# ==========================================================
# FACHADA DE IA + INFRA — GROQ / LLAMA
# ==========================================================
# Este arquivo garante compatibilidade com scripts antigos
# e encapsula decisões de infraestrutura.
# ==========================================================

import os
import time
import json
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from groq import Groq

from classificador_regras import aplicar_regras_nome_categoria
from core.logger import get_logger

logger = get_logger(__name__)

# ==========================================
# 1. CONFIGURAÇÃO INICIAL
# ==========================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
LINK_BANCO = os.getenv("DATABASE_URL")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY não encontrada no .env")

if not LINK_BANCO:
    raise RuntimeError("DATABASE_URL não encontrada no .env")

groq_client = Groq(api_key=GROQ_API_KEY)
logger.info(f"Cliente Groq inicializado com modelo: {GROQ_MODEL}")

# ==========================================
# 2. BANCO DE DADOS
# ==========================================

def conectar():
    return psycopg2.connect(LINK_BANCO)


def produto_ja_existe(id_produto: str) -> bool:
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM produtos WHERE ean = %s", (id_produto,))
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def salvar_produto(id_produto, original, limpo, marca, categoria, unidade):
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO produtos (ean, nome_original, nome_limpo, marca, categoria, unidade)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ean) DO NOTHING;
            """,
            (id_produto, original, limpo, marca, categoria, unidade),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def salvar_compra(id_produto, data, mercado, preco, qtd):
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO historico_precos
            (ean, data_compra, mercado, preco_pago, quantidade)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (id_produto, data, mercado, preco, qtd),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

# ==========================================
# 3. IA — FUNÇÃO ORIGINAL
# ==========================================

def consultar_ia(nome_sujo: str) -> dict:
    logger.info(f"IA classificando produto: {nome_sujo}")

    prompt = (
        "Você é um especialista em classificação de produtos de supermercado.\n"
        f"DESCRIÇÃO: \"{nome_sujo}\"\n\n"
        "Retorne APENAS um JSON com:\n"
        "produto, marca, categoria, unidade"
    )

    try:
        resposta = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
            model=GROQ_MODEL,
            temperature=0.2,
            max_tokens=250,
            response_format={"type": "json_object"},
        )

        dados = json.loads(resposta.choices[0].message.content)

        produto_final, categoria_final = aplicar_regras_nome_categoria(
            nome_original=nome_sujo,
            nome_ia=dados.get("produto", nome_sujo),
            categoria_ia=dados.get("categoria", "Outros"),
        )

        time.sleep(0.3)

        return {
            "produto": produto_final,
            "marca": dados.get("marca", ""),
            "categoria": categoria_final,
            "unidade": dados.get("unidade", "un"),
        }

    except Exception as e:
        logger.error(f"Erro na IA: {e}")
        return {
            "produto": nome_sujo,
            "marca": "",
            "categoria": "Outros",
            "unidade": "un",
        }

# ==========================================
# 4. FUNÇÕES FACHADA (COMPATIBILIDADE TOTAL)
# ==========================================

def classificar_produto(descricao: str, contexto: dict | None = None) -> dict:
    """
    Função fachada esperada por importadores antigos.
    """
    logger.debug("Chamando classificar_produto (fachada)")
    return consultar_ia(descricao)


def criar_tabelas_se_nao_existirem():
    """
    Função fachada esperada por scripts antigos.
    Encaminha para o script correto de infraestrutura.
    """
    logger.info("Garantindo existência das tabelas (fachada)")

    try:
        import reset_tabelas
        if hasattr(reset_tabelas, "criar_tabelas_se_nao_existirem"):
            reset_tabelas.criar_tabelas_se_nao_existirem()
        else:
            reset_tabelas.main()
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")
        raise
