# core/database.py
# Módulo centralizado de acesso ao banco de dados (Neon/PostgreSQL)

import os
import logging
from typing import Any, Iterable, Optional

import psycopg2
import pandas as pd

logger = logging.getLogger(__name__)

# Conexão global simples reaproveitada entre chamadas
_connection = None


def get_database_url() -> str:
    """
    Retorna a DATABASE_URL a partir das variáveis de ambiente.

    Exemplo de DATABASE_URL:
      postgresql://usuario:senha@host.neon.tech:5432/nome_banco?sslmode=require
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Variável de ambiente DATABASE_URL não configurada. "
            "Defina a URL de conexão do Neon antes de executar o sistema."
        )

    return database_url


def get_connection():
    """
    Retorna uma conexão psycopg2 reutilizável com o banco Neon.
    Lança exceção em caso de erro (tratada pela camada chamadora).
    """
    global _connection

    # Reaproveita conexão existente, se ainda estiver aberta
    if _connection is not None and getattr(_connection, "closed", 1) == 0:
        return _connection

    database_url = get_database_url()

    try:
        _connection = psycopg2.connect(
            database_url,
            connect_timeout=10,
            application_name="gestao_compras_dashboard",
        )
        # Testa rapidamente a conexão
        with _connection.cursor() as cur:
            cur.execute("SELECT 1")

        logger.info("Conexão com o banco estabelecida com sucesso.")
        return _connection
    except Exception as e:
        logger.exception("Erro ao conectar ao banco de dados.")
        _connection = None
        raise RuntimeError(f"Erro ao conectar ao banco de dados: {e}") from e


def run_query(sql: str, params: Optional[Iterable[Any]] = None) -> pd.DataFrame:
    """
    Executa uma consulta SQL (SELECT) e retorna um DataFrame do pandas.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    except Exception as e:
        logger.exception("Erro ao executar consulta SQL.")
        raise RuntimeError(f"Erro ao executar consulta SQL: {e}") from e


def execute_sql(sql: str, params: Optional[Iterable[Any]] = None) -> None:
    """
    Executa um comando SQL (INSERT, UPDATE, DELETE) com commit automático.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception("Erro ao executar comando SQL.")
        raise RuntimeError(f"Erro ao executar comando SQL: {e}") from e


def close_connection() -> None:
    """
    Fecha explicitamente a conexão, se existir.
    """
    global _connection
    if _connection is not None and getattr(_connection, "closed", 1) == 0:
        _connection.close()
    _connection = None
