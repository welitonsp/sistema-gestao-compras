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
        await db_session.commit()

        # Setup
        f1 = Fornecedor(
            cnpj="11111111111111",
            razao_social="Fornecedor Principal",
            nome_fantasia="Fantasia Principal",
        )
        db_session.add(f1)
        await db_session.flush()

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Nota 1
        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="101",
            chave_acesso="1" * 44,
            data_emissao=yesterday,
            valor_total=Decimal("150.00"),
            status="active",
        )
        db_session.add(n1)

        # Nota 2
        n2 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="102",
            chave_acesso="2" * 44,
            data_emissao=today,
            valor_total=Decimal("250.00"),
            status="active",
        )
        db_session.add(n2)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        res = await service.obter_detalhes_fornecedor(str(f1.id))

        assert res is not None
        assert res["fornecedor_id"] == str(f1.id)
        assert res["nome_exibicao"] == "Fantasia Principal"

        resumo = res["resumo"]
        assert resumo["quantidade_notas"] == 2
        assert resumo["total_gasto"] == 400.0
        assert resumo["ticket_medio"] == 200.0
        assert resumo["primeira_compra"] == yesterday.isoformat()
        assert resumo["ultima_compra"] == today.isoformat()

        notas = res["notas"]
        assert len(notas) == 2
        # Order should be descending by date
        assert notas[0]["data_emissao"] == today.isoformat()
        assert notas[0]["numero_nota"] == "102"
        assert notas[0]["valor_total"] == 250.0

        assert notas[1]["data_emissao"] == yesterday.isoformat()
        assert notas[1]["numero_nota"] == "101"
        assert notas[1]["valor_total"] == 150.0


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
