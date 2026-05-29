import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import delete
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
async def test_product_price_history_endpoint():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(HistoricoPreco))
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Setup
        f1 = Fornecedor(cnpj="11111111111111", razao_social="Forn A")
        db_session.add(f1)
        await db_session.flush()

        p1 = Produto(ean="123456", nome_limpo="Produto Teste", categoria="Teste")
        db_session.add(p1)
        await db_session.flush()

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Nota 1
        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="101",
            chave_acesso="1" * 44,
            data_emissao=yesterday,
            valor_total=Decimal("10.00"),
            status="active",
        )
        db_session.add(n1)
        await db_session.flush()

        hp1 = HistoricoPreco(
            ean=p1.ean,
            nota_fiscal_id=n1.id,
            data_compra=yesterday,
            preco_pago=Decimal("10.00"),
            quantidade=Decimal("1"),
            local="Forn A",
        )
        db_session.add(hp1)

        # Nota 2
        n2 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="102",
            chave_acesso="2" * 44,
            data_emissao=today,
            valor_total=Decimal("12.00"),
            status="active",
        )
        db_session.add(n2)
        await db_session.flush()

        hp2 = HistoricoPreco(
            ean=p1.ean,
            nota_fiscal_id=n2.id,
            data_compra=today,
            preco_pago=Decimal("12.00"),
            quantidade=Decimal("1"),
            local="Forn A",
        )
        db_session.add(hp2)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        res = await service.obter_historico_preco_produto(p1.ean)

        assert res["ean"] == "123456"
        assert res["nome_produto"] == "Produto Teste"
        assert len(res["historico"]) == 2
        # Order should be descending by date
        assert res["historico"][0]["data_compra"] == today.isoformat()
        assert res["historico"][0]["preco_unitario"] == 12.0
        assert res["historico"][1]["data_compra"] == yesterday.isoformat()
        assert res["historico"][1]["preco_unitario"] == 10.0
        assert res["historico"][0]["numero_nota"] == "102"


@pytest.mark.asyncio
async def test_resumo_includes_ean():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(HistoricoPreco))
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        f1 = Fornecedor(cnpj="00000000000000", razao_social="F1")
        db_session.add(f1)
        await db_session.flush()

        p1 = Produto(ean="999", nome_limpo="P999", categoria="C")
        db_session.add(p1)
        await db_session.flush()

        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="1",
            chave_acesso="3" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("100.00"),
            status="active",
        )
        db_session.add(n1)
        await db_session.flush()

        i1 = ItemNotaFiscal(
            nota_fiscal_id=n1.id,
            ean=p1.ean,
            descricao_original="D",
            quantidade=1,
            valor_unitario=100,
            valor_total=100,
        )
        db_session.add(i1)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        top_prods = await service.obter_top_produtos_gasto()

        assert len(top_prods) > 0
        assert top_prods[0]["ean"] == "999"
        assert top_prods[0]["produto"] == "P999"
