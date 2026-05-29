import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import delete
from backend.models.compras import (
    NotaFiscal,
    ItemNotaFiscal,
    Fornecedor,
    Produto,
)
from backend.services.insights_processor import PriceInsightsService
from backend.core.database import SessionLocal


@pytest.mark.asyncio
async def test_alert_concentration_high():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.commit()

        # Setup 2 Fornecedores
        f1 = Fornecedor(cnpj="11111111111111", razao_social="Dominante")
        f2 = Fornecedor(cnpj="22222222222222", razao_social="Minoratario")
        db_session.add_all([f1, f2])
        await db_session.flush()

        # Nota 1: 80% do gasto (80.00)
        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="1",
            chave_acesso="1" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("80.00"),
            status="active",
        )
        # Nota 2: 20% do gasto (20.00)
        n2 = NotaFiscal(
            fornecedor_id=f2.id,
            numero_nota="2",
            chave_acesso="2" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("20.00"),
            status="active",
        )
        db_session.add_all([n1, n2])
        await db_session.commit()

        service = PriceInsightsService(db_session)
        alertas = await service.obter_alertas_risco_basicos()
        
        concentration_alerts = [a for a in alertas if a['tipo'] == 'concentration']
        assert len(concentration_alerts) == 1
        assert "80.0%" in concentration_alerts[0]['mensagem']
        assert "Dominante" in concentration_alerts[0]['mensagem']
        assert concentration_alerts[0]['severidade'] == "warning"

@pytest.mark.asyncio
async def test_alert_concentration_low():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.commit()

        f1 = Fornecedor(cnpj="11111111111111", razao_social="F1")
        f2 = Fornecedor(cnpj="22222222222222", razao_social="F2")
        db_session.add_all([f1, f2])
        await db_session.flush()

        # 50% / 50%
        n1 = NotaFiscal(fornecedor_id=f1.id, numero_nota="1", chave_acesso="1"*44, valor_total=Decimal("50.00"), status="active", data_emissao=date.today())
        n2 = NotaFiscal(fornecedor_id=f2.id, numero_nota="2", chave_acesso="2"*44, valor_total=Decimal("50.00"), status="active", data_emissao=date.today())
        db_session.add_all([n1, n2])
        await db_session.commit()

        service = PriceInsightsService(db_session)
        alertas = await service.obter_alertas_risco_basicos()
        assert not any(a['tipo'] == 'concentration' for a in alertas)

@pytest.mark.asyncio
async def test_alert_catalog_health():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Criar nota para o produto ser contabilizado se houver filtro
        f1 = Fornecedor(cnpj="33333333333333", razao_social="F1")
        db_session.add(f1)
        await db_session.flush()
        
        n1 = NotaFiscal(fornecedor_id=f1.id, numero_nota="1", chave_acesso="1"*44, valor_total=Decimal("10.00"), status="active", data_emissao=date.today())
        db_session.add(n1)
        await db_session.flush()

        p1 = Produto(ean="123", nome_limpo="Sem Categoria", categoria=None)
        p2 = Produto(ean="456", nome_limpo="Com Categoria", categoria="Limpeza")
        db_session.add_all([p1, p2])
        await db_session.flush()
        
        i1 = ItemNotaFiscal(nota_fiscal_id=n1.id, ean=p1.ean, descricao_original="X", quantidade=1, valor_unitario=10, valor_total=10)
        db_session.add(i1)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        alertas = await service.obter_alertas_risco_basicos()
        
        catalog_alerts = [a for a in alertas if a['tipo'] == 'catalog_health']
        assert len(catalog_alerts) == 1
        assert "1 produtos" in catalog_alerts[0]['mensagem']
        assert catalog_alerts[0]['severidade'] == "info"

@pytest.mark.asyncio
async def test_alert_mismatch():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.commit()

        f1 = Fornecedor(cnpj="44444444444444", razao_social="F1")
        db_session.add(f1)
        await db_session.flush()

        n1 = NotaFiscal(
            fornecedor_id=f1.id,
            numero_nota="1",
            chave_acesso="1" * 44,
            valor_total=Decimal("100.00"),
            status="active",
            data_emissao=date.today(),
            extraction_total_mismatch=True
        )
        db_session.add(n1)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        alertas = await service.obter_alertas_risco_basicos()
        
        mismatch_alerts = [a for a in alertas if a['tipo'] == 'mismatch']
        assert len(mismatch_alerts) == 1
        assert "1 nota(s)" in mismatch_alerts[0]['mensagem']
        assert mismatch_alerts[0]['severidade'] == "danger"
