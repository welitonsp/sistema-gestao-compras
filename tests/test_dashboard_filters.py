import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, delete
from backend.models.compras import (
    NotaFiscal,
    ItemNotaFiscal,
    Fornecedor,
    Produto,
)
from backend.services.insights_processor import PriceInsightsService
from backend.core.database import SessionLocal


@pytest.mark.asyncio
async def test_dashboard_period_filters():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.execute(delete(Produto))
        await db_session.commit()

        # Setup
        fornecedor = Fornecedor(cnpj="12345678901234", razao_social="Forn Teste")
        db_session.add(fornecedor)
        await db_session.flush()

        produto = Produto(ean="789000", nome_limpo="Prod Teste", categoria="Teste")
        db_session.add(produto)
        await db_session.flush()

        # Create notes in different periods
        today = date.today()
        last_month = today - timedelta(days=45)
        
        # Nota dentro do período (Hoje)
        nota_recente = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="1",
            chave_acesso="1" * 44,
            data_emissao=today,
            valor_total=Decimal("100.00"),
            status="active",
        )
        
        # Nota fora do período (Mês passado)
        nota_antiga = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="2",
            chave_acesso="2" * 44,
            data_emissao=last_month,
            valor_total=Decimal("200.00"),
            status="active",
        )
        db_session.add_all([nota_recente, nota_antiga])
        await db_session.flush()

        # Adicionar itens para as agregações
        item1 = ItemNotaFiscal(
            nota_fiscal_id=nota_recente.id,
            ean=produto.ean,
            descricao_original="Desc 1",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("100.00"),
            valor_total=Decimal("100.00")
        )
        item2 = ItemNotaFiscal(
            nota_fiscal_id=nota_antiga.id,
            ean=produto.ean,
            descricao_original="Desc 2",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("100.00"),
            valor_total=Decimal("200.00")
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        service = PriceInsightsService(db_session)

        # 1. Testar sem filtro (deve trazer tudo)
        res_total = await service.obter_resumo_gastos_por_categoria()
        assert any(item['total'] == 300.0 for item in res_total)

        # 2. Testar com filtro (Apenas hoje)
        res_filtrado = await service.obter_resumo_gastos_por_categoria(start_date=today)
        # Deve somar apenas a nota_recente (100.00)
        assert len(res_filtrado) == 1
        assert res_filtrado[0]['total'] == 100.0

        # 3. Testar top produtos com filtro
        top_prod = await service.obter_top_produtos_gasto(start_date=today)
        assert top_prod[0]['total'] == 100.0

        # 4. Testar período sem dados
        future_date = today + timedelta(days=10)
        res_vazio = await service.obter_resumo_gastos_por_categoria(start_date=future_date)
        assert len(res_vazio) == 0

@pytest.mark.asyncio
async def test_dashboard_evolution_filter():
    async with SessionLocal() as db_session:
        # Cleanup
        await db_session.execute(delete(ItemNotaFiscal))
        await db_session.execute(delete(NotaFiscal))
        await db_session.execute(delete(Fornecedor))
        await db_session.commit()

        # Setup Fornecedor (necessário para NOT NULL)
        fornecedor = Fornecedor(cnpj="00000000000000", razao_social="Forn Mock")
        db_session.add(fornecedor)
        await db_session.flush()

        today = date.today()
        # Garantir nota no mês atual
        nota = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="999",
            chave_acesso="9" * 44,
            data_emissao=today,
            valor_total=Decimal("50.00"),
            status="active",
        )
        db_session.add(nota)
        await db_session.commit()

        service = PriceInsightsService(db_session)
        
        # Filtro que inclui a nota
        evol = await service.obter_evolucao_gastos_mensal(start_date=today - timedelta(days=1))
        assert len(evol) >= 1
        assert any(item['total'] == 50.0 for item in evol)

        # Filtro que exclui a nota
        evol_vazia = await service.obter_evolucao_gastos_mensal(start_date=today + timedelta(days=1))
        assert len(evol_vazia) == 0
