import asyncio
import os
import sys
from decimal import Decimal
from sqlalchemy import select, func
from backend.core.database import SessionLocal
from backend.models.compras import Produto, HistoricoPreco
from dotenv import load_dotenv

def formatar_moeda(valor):
    """Formata Decimal como R$ 1.234,56"""
    if valor is None:
        valor = Decimal("0.00")
    valor = Decimal(valor).quantize(Decimal("0.01"))
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

async def obter_dados_relatorio():
    async with SessionLocal() as session:
        # 1. Total Geral
        stmt_total = select(func.sum(HistoricoPreco.preco_pago * HistoricoPreco.quantidade))
        total_geral = await session.scalar(stmt_total) or Decimal("0.00")

        # 2. Resumo por Categoria
        stmt_cat = (
            select(
                func.coalesce(Produto.categoria, "Sem Categoria").label("categoria"),
                func.sum(HistoricoPreco.preco_pago * HistoricoPreco.quantidade).label("total_gasto")
            )
            .join(Produto, Produto.ean == HistoricoPreco.ean)
            .group_by("categoria")
            .order_by(func.sum(HistoricoPreco.preco_pago * HistoricoPreco.quantidade).desc())
        )
        result = await session.execute(stmt_cat)
        resumo = result.all()

        return total_geral, resumo

def exibir_relatorio(total_geral, resumo):
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO – GASTOS POR CATEGORIA (ESTRUTURA UNIFICADA)")
    print("=" * 60)
    
    if total_geral == 0:
        print("⚠️ Nenhum dado encontrado para gerar o relatório.")
        return

    print(f"{'CATEGORIA':<30} | {'TOTAL GASTO':>15} | {'% DO TOTAL':>10}")
    print("-" * 60)

    for row in resumo:
        perc = (row.total_gasto / total_geral * 100) if total_geral > 0 else 0
        print(f"{row.categoria:<30} | {formatar_moeda(row.total_gasto):>15} | {perc:6.2f}%")

    print("-" * 60)
    print(f"{'TOTAL GERAL':<30} | {formatar_moeda(total_geral):>15} | 100.00%")
    print("=" * 60 + "\n")

async def main():
    load_dotenv()
    try:
        total, resumo = await obter_dados_relatorio()
        exibir_relatorio(total, resumo)
    except Exception as e:
        print(f"❌ Erro ao gerar relatório: {e}")

if __name__ == "__main__":
    asyncio.run(main())
