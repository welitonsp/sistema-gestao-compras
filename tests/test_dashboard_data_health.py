import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import delete
from backend.models.compras import (
    NotaFiscal,
    Fornecedor,
    User,
    UserRole
)
from backend.core.database import SessionLocal
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.api.dependencies import get_current_user
from uuid import uuid4, UUID

# Global test data
TEST_DEPT_ID = uuid4()
test_user = User(
    id=uuid4(),
    username="test_health_user",
    email="health@example.com",
    role=UserRole.MANAGER,
    department_id=TEST_DEPT_ID,
    is_active=True
)

async def mock_get_current_user():
    return test_user

import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    from unittest.mock import AsyncMock
    app.state.redis = AsyncMock()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_dashboard_data_health_aggregation(client):
    async with SessionLocal() as db:
        # Cleanup
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        
        # Seed
        forn = Fornecedor(id=uuid4(), razao_social="Forn Health", cnpj="health-123")
        db.add(forn)
        await db.flush()
        
        # 1. Nota OK
        nota_ok = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="101",
            chave_acesso="1" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("100.00"),
            status="active",
            department_id=TEST_DEPT_ID,
            extraction_quality_status="ok",
            extraction_item_count=2,
            extraction_missing_ean_count=0,
            extraction_total_mismatch=False
        )
        db.add(nota_ok)

        # 2. Nota Warning (Mismatch)
        nota_warn = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="102",
            chave_acesso="2" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("200.00"),
            status="active",
            department_id=TEST_DEPT_ID,
            extraction_quality_status="warning",
            extraction_item_count=3,
            extraction_missing_ean_count=1,
            extraction_total_mismatch=True
        )
        db.add(nota_warn)

        # 3. Nota Failed
        nota_fail = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="103",
            chave_acesso="3" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("300.00"),
            status="active",
            department_id=TEST_DEPT_ID,
            extraction_quality_status="failed",
            extraction_item_count=0,
            extraction_missing_ean_count=0,
            extraction_total_mismatch=False
        )
        db.add(nota_fail)

        # 4. Nota de outro departamento (Deve ser ignorada)
        nota_other = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="104",
            chave_acesso="4" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("400.00"),
            status="active",
            department_id=uuid4(),
            extraction_quality_status="ok",
            extraction_item_count=10,
            extraction_missing_ean_count=0,
            extraction_total_mismatch=False
        )
        db.add(nota_other)

        # 5. Nota Inativa (Deve ser ignorada)
        nota_inactive = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="105",
            chave_acesso="5" * 44,
            data_emissao=date.today(),
            valor_total=Decimal("500.00"),
            status="inactive",
            department_id=TEST_DEPT_ID,
            extraction_quality_status="ok",
            extraction_item_count=10,
            extraction_missing_ean_count=0,
            extraction_total_mismatch=False
        )
        db.add(nota_inactive)

        await db.commit()

    response = await client.get("/api/v1/dashboard/resumo")
    assert response.status_code == 200
    res = response.json()
    
    assert "saude_dados" in res
    health = res["saude_dados"]
    
    assert health["total_notas"] == 3
    assert health["notas_ok"] == 1
    assert health["notas_warning"] == 1
    assert health["notas_failed"] == 1
    assert health["total_itens"] == 5 # 2 + 3 + 0
    assert health["itens_sem_ean"] == 1
    assert health["total_mismatches"] == 1
    
    # saúde = (1.0 + 0.5 + 0.0) / 3 = 1.5 / 3 = 50%
    assert health["percentual_saude"] == 50.0
    assert health["nivel"] == "danger"

@pytest.mark.asyncio
async def test_dashboard_data_health_empty(client):
    async with SessionLocal() as db:
        await db.execute(delete(NotaFiscal))
        await db.commit()

    response = await client.get("/api/v1/dashboard/resumo")
    assert response.status_code == 200
    health = response.json()["saude_dados"]
    assert health["total_notas"] == 0
    assert health["percentual_saude"] == 100.0
    assert health["nivel"] == "ok"

@pytest.mark.asyncio
async def test_dashboard_data_health_date_filter(client):
    async with SessionLocal() as db:
        await db.execute(delete(NotaFiscal))
        forn = Fornecedor(id=uuid4(), razao_social="Forn Date", cnpj="health-date")
        db.add(forn)
        await db.flush()

        # Nota Antiga
        db.add(NotaFiscal(
            fornecedor_id=forn.id, numero_nota="O1", chave_acesso="o" * 44,
            data_emissao=date(2020, 1, 1), valor_total=Decimal("10"),
            status="active", department_id=TEST_DEPT_ID, extraction_quality_status="failed"
        ))
        # Nota Nova
        db.add(NotaFiscal(
            fornecedor_id=forn.id, numero_nota="N1", chave_acesso="n" * 44,
            data_emissao=date.today(), valor_total=Decimal("10"),
            status="active", department_id=TEST_DEPT_ID, extraction_quality_status="ok"
        ))
        await db.commit()

    # Filtro hoje
    today = date.today().isoformat()
    response = await client.get(f"/api/v1/dashboard/resumo?start_date={today}")
    health = response.json()["saude_dados"]
    assert health["total_notas"] == 1
    assert health["notas_ok"] == 1
    assert health["percentual_saude"] == 100.0
