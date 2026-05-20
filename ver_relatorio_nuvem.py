import asyncio
import os
from datetime import date
from sqlalchemy import select, desc
from backend.core.database import SessionLocal
from backend.models.compras import Produto, HistoricoPreco
from dotenv import load_dotenv

async def mostrar_dados(limit: int = 50) -> None:
    """
    Mostra os últimos lançamentos da tabela historico_precos,
    juntando com produtos para exibir o nome limpo.
    """
    print("\n📊 ÚLTIMOS LANÇAMENTOS REGISTRADOS (ESTRUTURA UNIFICADA)")
    print("─" * 90)
    print("DATA       | LOCAL                 | PRODUTO                 | QTD   | PREÇO UNIT")
    print("─" * 90)

    async with SessionLocal() as session:
        stmt = (
            select(
                HistoricoPreco.data_compra,
                HistoricoPreco.local,
                Produto.nome_limpo,
                HistoricoPreco.quantidade,
                HistoricoPreco.preco_pago
            )
            .join(Produto, HistoricoPreco.ean == Produto.ean)
            .order_by(desc(HistoricoPreco.data_compra), desc(HistoricoPreco.id))
            .limit(limit)
        )
        result = await session.execute(stmt)
        linhas = result.all()

        if not linhas:
            print("⚠️ Nenhum registro encontrado.")
            return

        for row in linhas:
            data_str = row.data_compra.strftime("%Y-%m-%d")
            local_fmt = (row.local[:22] + "..") if len(row.local) > 22 else row.local
            nome_fmt = (row.nome_limpo[:24] + "..") if len(row.nome_limpo) > 24 else row.nome_limpo

            print(
                f"{data_str} | "
                f"{local_fmt:<24} | "
                f"{nome_fmt:<26} | "
                f"{float(row.quantidade):5.3f} | "
                f"R$ {float(row.preco_pago):6.2f}"
            )

async def main():
    load_dotenv()
    try:
        await mostrar_dados()
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")

if __name__ == "__main__":
    asyncio.run(main())
