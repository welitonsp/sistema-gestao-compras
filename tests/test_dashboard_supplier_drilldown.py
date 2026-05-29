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
async def test_supplier_drilldown_endpoint():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(HistoricoPreco))
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Setup
        f1 = Fornecedor(
            cnpj="11111111111111",
            razao_social="Fornecedor Principal",
            nome_fantasia="Fantasia Principal",
        )
        db_session.add(f1)
        await db_session.flush()

        p1 = Produto(ean="7891", nome_limpo="Produto A", categoria="Cat 1")
        p2 = Produto(ean="7892", nome_limpo="Produto B", categoria="Cat 2")
        db_session.add_all([p1, p2])
        await db_session.flush()

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Nota 1 (Ontem) - Produto A (2 unid a 10.00 = 20.00)
        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="101",
            chave_acesso="1" * 44,
            data_emissao=yesterday,
            valor_total=Decimal("20.00"),
            status="active",
        )
        db_session.add(n1)
        await db_session.flush()

        i1 = ItemNotaFiscal(
            nota_fiscal_id=n1.id,
            ean=p1.ean,
            descricao_original="PROD A",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("10.00"),
            valor_total=Decimal("20.00"),
        )
        db_session.add(i1)

        # Nota 2 (Hoje) - Produto A (1 unid a 16.00) + Produto B (1 unid a 30.00) = 46.00
        n2 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="102",
            chave_acesso="2" * 44,
            data_emissao=today,
            valor_total=Decimal("46.00"),
            status="active",
        )
        db_session.add(n2)
        await db_session.flush()

        i2a = ItemNotaFiscal(
            nota_fiscal_id=n2.id,
            ean=p1.ean,
            descricao_original="PROD A",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("16.00"),
            valor_total=Decimal("16.00"),
        )
        i2b = ItemNotaFiscal(
            nota_fiscal_id=n2.id,
            ean=p2.ean,
            descricao_original="PROD B",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("30.00"),
            valor_total=Decimal("30.00"),
        )
        db_session.add_all([i2a, i2b])

        await db_session.commit()

        service = PriceInsightsService(db_session)
        res = await service.obter_detalhes_fornecedor(str(f1.id))

        assert res is not None
        assert res["fornecedor_id"] == str(f1.id)
        assert res["nome_exibicao"] == "Fantasia Principal"

        resumo = res["resumo"]
        assert resumo["quantidade_notas"] == 2
        assert resumo["total_gasto"] == 66.0
        assert resumo["ticket_medio"] == 33.0
        assert resumo["primeira_compra"] == yesterday.isoformat()
        assert resumo["ultima_compra"] == today.isoformat()

        # Verificar Top Produtos
        top_produtos = res["top_produtos"]
        assert len(top_produtos) == 2

        # Produto A deve vir primeiro (Total: 20 + 16 = 36) vs Produto B (30)
        prod_a = top_produtos[0]
        assert prod_a["nome_produto"] == "Produto A"
        assert prod_a["quantidade_total"] == 3.0
        assert prod_a["total_gasto"] == 36.0
        # Preço Médio Ponderado: 36 / 3 = 12.0
        assert prod_a["preco_medio"] == 12.0
        assert prod_a["quantidade_notas"] == 2

        prod_b = top_produtos[1]
        assert prod_b["nome_produto"] == "Produto B"
        assert prod_b["total_gasto"] == 30.0
        assert prod_b["quantidade_notas"] == 1

        notas = res["notas"]
        assert len(notas) == 2
        # Order should be descending by date
        assert notas[0]["data_emissao"] == today.isoformat()
        assert notas[0]["numero_nota"] == "102"
        assert notas[0]["valor_total"] == 46.0

        assert notas[1]["data_emissao"] == yesterday.isoformat()
        assert notas[1]["numero_nota"] == "101"
        assert notas[1]["valor_total"] == 20.0


@pytest.mark.asyncio
async def test_supplier_drilldown_not_found():
    async with SessionLocal() as db_session:
        service = PriceInsightsService(db_session)
        import uuid

        res = await service.obter_detalhes_fornecedor(str(uuid.uuid4()))
        assert res is None


@pytest.mark.asyncio
async def test_supplier_drilldown_filters():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(HistoricoPreco))
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.commit()

        # Setup
        f1 = Fornecedor(cnpj="22222222222222", razao_social="Fornecedor Secundário")
        db_session.add(f1)
        await db_session.flush()

        today = date.today()
        old_date = today - timedelta(days=60)

        # Nota Recente
        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="201",
            chave_acesso="3" * 44,
            data_emissao=today,
            valor_total=Decimal("100.00"),
            status="active",
        )
        db_session.add(n1)

        # Nota Antiga
        n2 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="202",
            chave_acesso="4" * 44,
            data_emissao=old_date,
            valor_total=Decimal("200.00"),
            status="active",
        )
        db_session.add(n2)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        res = await service.obter_detalhes_fornecedor(str(f1.id), start_date=today)

        assert res is not None
        resumo = res["resumo"]
        assert resumo["quantidade_notas"] == 1
        assert resumo["total_gasto"] == 100.0

        notas = res["notas"]
        assert len(notas) == 1
        assert notas[0]["numero_nota"] == "201"
