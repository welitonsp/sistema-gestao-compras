# ver_relatorio_nuvem.py
# Visualizador simples em modo texto dos últimos lançamentos gravados no Neon
# Alinhado ao novo schema:
#   - produtos(ean, nome_original, nome_limpo, marca, categoria, unidade)
#   - historico_precos(id, ean, data_compra, mercado, preco_pago, quantidade)

import os
import psycopg2
from datetime import date
from dotenv import load_dotenv

# -------------------------------------------------------------------
# 1. Carregar .env e ler a DATABASE_URL
# -------------------------------------------------------------------

load_dotenv()

def ler_link_banco() -> str:
    """
    Lê a variável DATABASE_URL do arquivo .env.
    Exemplo:
      DATABASE_URL=postgres://usuario:senha@host.neon.tech:5432/banco
    """
    link_banco = os.getenv("DATABASE_URL")
    if not link_banco:
        print("❌ ERRO: DATABASE_URL não encontrada no .env.")
        print("   Verifique se o arquivo .env está na mesma pasta deste script")
        print("   e contém uma linha como:")
        print('   DATABASE_URL="postgres://usuario:senha@host:5432/banco"')
        raise SystemExit(1)
    return link_banco

# -------------------------------------------------------------------
# 2. Função principal de visualização
# -------------------------------------------------------------------

def mostrar_dados(limit: int = 50) -> None:
    """
    Mostra os últimos lançamentos da tabela historico_precos,
    juntando com produtos para exibir o nome limpo.
    """
    link_banco = ler_link_banco()

    try:
        conn = psycopg2.connect(link_banco)
        cursor = conn.cursor()

        print("\n📊 ÚLTIMOS LANÇAMENTOS REGISTRADOS NO NEON")
        print("─" * 90)
        print("DATA       | MERCADO               | PRODUTO                 | QTD   | PREÇO UNIT")
        print("─" * 90)

        # Consulta alinhada ao NOVO schema criado pelo script de importação (ia_groq_utils/importar_pdf)
        cursor.execute(
            """
            SELECT 
                h.data_compra,
                h.mercado,
                p.nome_limpo,
                h.quantidade,
                h.preco_pago
            FROM historico_precos h
            JOIN produtos p ON h.ean = p.ean
            ORDER BY h.data_compra DESC, h.id DESC
            LIMIT %s;
            """,
            (limit,),
        )

        linhas = cursor.fetchall()

        if not linhas:
            print("⚠️ Nenhum registro encontrado em historico_precos.")
            print("   Dica: rode primeiro o script de importação (ia_groq_utils.py / importar_pdf.py).")
            conn.close()
            return

        for data_compra, mercado, nome_limpo, qtd, preco_unit in linhas:
            # Data em formato YYYY-MM-DD
            if isinstance(data_compra, date):
                data_str = data_compra.strftime("%Y-%m-%d")
            else:
                data_str = str(data_compra)[:10]

            mercado_fmt = (mercado[:22] + "..") if len(mercado) > 22 else mercado
            nome_fmt = (nome_limpo[:24] + "..") if len(nome_limpo) > 24 else nome_limpo

            try:
                qtd_float = float(qtd)
            except (TypeError, ValueError):
                qtd_float = 0.0

            try:
                preco_float = float(preco_unit)
            except (TypeError, ValueError):
                preco_float = 0.0

            print(
                f"{data_str} | "
                f"{mercado_fmt:<24} | "
                f"{nome_fmt:<26} | "
                f"{qtd_float:5.3f} | "
                f"R$ {preco_float:6.2f}"
            )

        conn.close()

    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")

# -------------------------------------------------------------------
# 3. Ponto de entrada
# -------------------------------------------------------------------

if __name__ == "__main__":
    mostrar_dados()
