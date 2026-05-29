import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import select, delete
from backend.models.compras import (
    NotaFiscal,
    ItemNotaFiscal,
    Fornecedor,
    Produto,
    HistoricoPreco,
)
from backend.services.insights_processor import PriceInsightsService
from backend.core.database import SessionLocal


@pytest.mark.asyncio
async def test_obter_evolucao_gastos_mensal():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Setup: Create a supplier and a product
        fornecedor = Fornecedor(cnpj="12345678901234", razao_social="Forn Teste")
        db_session.add(fornecedor)
        await db_session.flush()

        produto = Produto(ean="789000", nome_limpo="Prod Teste", categoria="Teste")
        db_session.add(produto)
        await db_session.flush()

        # Create notes in different months
        data1 = date(2026, 1, 10)
        data2 = date(2026, 2, 10)

        nota1 = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="1",
            chave_acesso="1" * 44,
            data_emissao=data1,
            valor_total=Decimal("100.00"),
            status="active",
        )
        nota2 = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="2",
            chave_acesso="2" * 44,
            data_emissao=data2,
            valor_total=Decimal("200.00"),
            status="active",
        )
        db_session.add_all([nota1, nota2])
        await db_session.commit()

        service = PriceInsightsService(db_session)
        evolucao = await service.obter_evolucao_gastos_mensal()

        # We expect at least these two months
        meses = {item["mes"] for item in evolucao}
        assert any("Jan" in m and "26" in m for m in meses)
        assert any("Feb" in m and "26" in m for m in meses)

        item_jan = next(item for item in evolucao if "Jan" in item["mes"])
        assert item_jan["total"] == 100.0


@pytest.mark.asyncio
async def test_obter_top_produtos_e_fornecedores():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Setup
        fornecedor1 = Fornecedor(cnpj="11111111111111", razao_social="Forn 1")
        fornecedor2 = Fornecedor(cnpj="22222222222222", razao_social="Forn 2")
        db_session.add_all([fornecedor1, fornecedor2])
        await db_session.flush()

        prod1 = Produto(ean="111", nome_limpo="Prod 1", categoria="Cat 1")
        prod2 = Produto(ean="222", nome_limpo="Prod 2", categoria="Cat 2")
        db_session.add_all([prod1, prod2])
        await db_session.flush()

        nota1 = NotaFiscal(
            fornecedor_id=fornecedor1.id,
            numero_nota="101",
            chave_acesso="3" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("1000.00"),
            status="active",
        )
        db_session.add(nota1)
        await db_session.flush()

        item1 = ItemNotaFiscal(
            nota_fiscal_id=nota1.id,
            ean=prod1.ean,
            descricao_original="Desc 1",
            quantidade=Decimal("10"),
            valor_unitario=Decimal("100.00"),
            valor_total=Decimal("1000.00"),
        )
        db_session.add(item1)
        await db_session.commit()

        service = PriceInsightsService(db_session)

        top_prod = await service.obter_top_produtos_gasto()
        assert top_prod[0]["produto"] == "Prod 1"
        assert top_prod[0]["total"] == 1000.0

        top_forn = await service.obter_top_fornecedores_gasto()
        assert top_forn[0]["fornecedor"] == "Forn 1"
        assert top_forn[0]["total"] == 1000.0
