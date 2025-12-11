# ver_relatorio_categorias.py
# Relatório de gastos por categoria usando os dados do Neon

import os
import sys
from decimal import Decimal

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv


def carregar_variaveis():
    """Carrega DATABASE_URL do .env"""
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ ERRO: DATABASE_URL não encontrada no .env.")
        print("   Verifique se o arquivo .env contém a linha:")
        print("   DATABASE_URL=postgres://usuario:senha@host:5432/banco")
        sys.exit(1)

    return db_url


def conectar(db_url: str):
    """Abre conexão com o PostgreSQL (Neon)."""
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"❌ ERRO ao conectar no banco: {e}")
        sys.exit(1)


def obter_resumo_por_categoria(conn):
    """
    Retorna lista de categorias com o total gasto (preço_pago * quantidade).
    """
    sql = """
        SELECT
            COALESCE(NULLIF(TRIM(p.categoria), ''), 'Outros') AS categoria,
            SUM(h.preco_pago * h.quantidade) AS total_gasto
        FROM historico_precos h
        JOIN produtos p ON p.ean = h.ean
        GROUP BY categoria
        ORDER BY total_gasto DESC;
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()


def obter_total_geral(conn):
    """
    Retorna o total geral gasto em todos os lançamentos.
    """
    sql = """
        SELECT SUM(preco_pago * quantidade) AS total_geral
        FROM historico_precos;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] or Decimal("0.00")


def formatar_moeda(valor):
    """Formata Decimal como R$ 1.234,56"""
    if valor is None:
        valor = Decimal("0.00")
    valor = Decimal(valor).quantize(Decimal("0.01"))
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def exibir_relatorio(resumo, total_geral):
    print()
    print("📊 RESUMO DE GASTOS POR CATEGORIA")
    print("─" * 80)
    print(f"{'CATEGORIA':<30} | {'TOTAL GASTO':>15} | {'% DO TOTAL':>10}")
    print("─" * 80)

    for linha in resumo:
        categoria = linha["categoria"]
        total = linha["total_gasto"] or Decimal("0.00")
        perc = (total / total_geral * 100) if total_geral > 0 else Decimal("0.00")
        print(f"{categoria:<30} | {formatar_moeda(total):>15} | {perc:6.2f}%")

    print("─" * 80)
    print(f"{'TOTAL GERAL':<30} | {formatar_moeda(total_geral):>15} | {100:6.2f}%")
    print("─" * 80)
    print()


def main():
    print()
    print("============================================================")
    print("📊 RELATÓRIO – GASTOS POR CATEGORIA")
    print("============================================================")

    db_url = carregar_variaveis()
    conn = conectar(db_url)

    try:
        total_geral = obter_total_geral(conn)
        if total_geral == 0:
            print("⚠️  Nenhum lançamento encontrado em historico_precos.")
            print("   Rode primeiro o importador (ia_groq_utils.py).")
            return

        resumo = obter_resumo_por_categoria(conn)
        if not resumo:
            print("⚠️  Não foi possível agrupar por categoria.")
            print("   Verifique se há dados nas tabelas 'produtos' e 'historico_precos'.")
            return

        exibir_relatorio(resumo, total_geral)

    finally:
        conn.close()
        print("🔌 Conexão com o banco encerrada.")


if __name__ == "__main__":
    main()
