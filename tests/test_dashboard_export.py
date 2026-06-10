import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import delete
from backend.models.compras import (
    AuditLog,
    NotaFiscal,
    ItemNotaFiscal,
    Fornecedor,
    Produto,
    User,
    UserRole
)
from backend.core.database import SessionLocal
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.api.dependencies import get_current_user
from uuid import uuid4

# Global test data
TEST_DEPT_ID = uuid4()
test_user = User(
    id=uuid4(),
    username="test_export_user",
    email="export@example.com",
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
    # Mock Redis if necessary (some routes might use it)
    from unittest.mock import AsyncMock
    app.state.redis = AsyncMock()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_export_top_produtos_csv(client):
    async with SessionLocal() as db:
        # Cleanup
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        
        # Seed
        forn = Fornecedor(id=uuid4(), razao_social="Forn Export", cnpj="123")
        db.add(forn)
        await db.flush()
        
        prod = Produto(ean="111", nome_limpo="=DANGER PROD", categoria="Cat")
        db.add(prod)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="101",
            chave_acesso="x"*44,
            data_emissao=date.today(),
            valor_total=Decimal("100.00"),
            status="active",
            department_id=TEST_DEPT_ID
        )
        db.add(nota)
        await db.flush()
        
        item = ItemNotaFiscal(
            nota_fiscal_id=nota.id,
            ean="111",
            descricao_original="PROD TESTE ORIGINAL",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("50.00"),
            valor_total=Decimal("100.00")
        )
        db.add(item)
        await db.commit()

    response = await client.get("/api/v1/dashboard/export?dataset=top_produtos")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=dashboard_top_produtos_" in response.headers["content-disposition"]
    
    content = response.text
    # Check for BOM
    assert content.startswith("\ufeff")
    
    assert "Produto;EAN;Quantidade Total;Preço Médio;Total Gasto" in content
    # Check for CSV injection protection (prefix ')
    assert "'=DANGER PROD" in content
    assert "111" in content
    assert "100.0" in content

@pytest.mark.asyncio
async def test_export_top_fornecedores_csv(client):
    async with SessionLocal() as db:
        # Seed
        forn = Fornecedor(id=uuid4(), razao_social="+FORN PLUS", cnpj="789")
        db.add(forn)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="202",
            chave_acesso="z"*44,
            data_emissao=date.today(),
            valor_total=Decimal("250.50"),
            status="active",
            department_id=TEST_DEPT_ID
        )
        db.add(nota)
        await db.commit()

    response = await client.get("/api/v1/dashboard/export?dataset=top_fornecedores")
    assert response.status_code == 200
    content = response.text
    assert "Fornecedor;Quantidade de Notas;Ticket Médio;Total Gasto" in content
    assert "'+FORN PLUS" in content
    assert "250.5" in content

@pytest.mark.asyncio
async def test_export_evolucao_mensal_csv(client):
    response = await client.get("/api/v1/dashboard/export?dataset=evolucao_mensal")
    assert response.status_code == 200
    content = response.text
    assert "Mês;Total Gasto;Quantidade de Notas" in content

@pytest.mark.asyncio
async def test_export_alertas_csv(client):
    response = await client.get("/api/v1/dashboard/export?dataset=alertas")
    assert response.status_code == 200
    content = response.text
    assert "Tipo;Nível;Mensagem" in content

@pytest.mark.asyncio
async def test_export_department_isolation(client):
    other_dept_id = uuid4()
    async with SessionLocal() as db:
        # Seed a note for ANOTHER department
        forn = Fornecedor(id=uuid4(), razao_social="Other Dept Forn", cnpj="456")
        db.add(forn)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="999",
            chave_acesso="y"*44,
            data_emissao=date.today(),
            valor_total=Decimal("500.00"),
            status="active",
            department_id=other_dept_id
        )
        db.add(nota)
        await db.commit()

    response = await client.get("/api/v1/dashboard/export?dataset=top_fornecedores")
    assert response.status_code == 200
    # Should not contain "Other Dept Forn" because it belongs to another dept
    assert "Other Dept Forn" not in response.text

@pytest.mark.asyncio
async def test_export_status_filtering(client):
    async with SessionLocal() as db:
        # Seed a CANCELED note
        forn = Fornecedor(id=uuid4(), razao_social="Canceled Forn", cnpj="000")
        db.add(forn)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="000",
            chave_acesso="0"*44,
            data_emissao=date.today(),
            valor_total=Decimal("1000.00"),
            status="canceled", # Not active
            department_id=TEST_DEPT_ID
        )
        db.add(nota)
        await db.commit()

    response = await client.get("/api/v1/dashboard/export?dataset=top_fornecedores")
    assert "Canceled Forn" not in response.text

@pytest.mark.asyncio
async def test_export_date_filters(client):
    async with SessionLocal() as db:
        # Seed a note far in the past
        forn = Fornecedor(id=uuid4(), razao_social="Past Forn", cnpj="111")
        db.add(forn)
        await db.flush()
        
        past_date = date(2020, 1, 1)
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="001",
            chave_acesso="a"*44,
            data_emissao=past_date,
            valor_total=Decimal("77.00"),
            status="active",
            department_id=TEST_DEPT_ID
        )
        db.add(nota)
        await db.commit()

    # Filter for today only
    today = date.today().isoformat()
    response = await client.get(f"/api/v1/dashboard/export?dataset=top_fornecedores&start_date={today}")
    assert "Past Forn" not in response.text
    
    # Filter including past
    response = await client.get(f"/api/v1/dashboard/export?dataset=top_fornecedores&start_date=2020-01-01")
    assert "Past Forn" in response.text

@pytest.mark.asyncio
async def test_export_invalid_dataset(client):
    response = await client.get("/api/v1/dashboard/export?dataset=invalid_name")
    assert response.status_code == 422 # Pydantic Enum validation

@pytest.mark.asyncio
async def test_export_fornecedor_produtos_csv(client):
    forn_id = uuid4()
    async with SessionLocal() as db:
        forn = Fornecedor(id=forn_id, razao_social="Forn Drill", cnpj="unique-drill-999")
        db.add(forn)
        prod = Produto(ean="888", nome_limpo="-SECURE PROD", categoria="Cat")
        db.add(prod)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="808",
            chave_acesso="s"*44,
            data_emissao=date.today(),
            valor_total=Decimal("200.00"),
            status="active",
            department_id=TEST_DEPT_ID
        )
        db.add(nota)
        await db.flush()
        
        item = ItemNotaFiscal(
            nota_fiscal_id=nota.id,
            ean="888",
            descricao_original="PROD SECURE",
            quantidade=Decimal("4"),
            valor_unitario=Decimal("50.00"),
            valor_total=Decimal("200.00")
        )
        db.add(item)
        await db.commit()

    response = await client.get(f"/api/v1/dashboard/fornecedores/{forn_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert f"attachment; filename=fornecedor_{forn_id}_produtos_" in response.headers["content-disposition"]
    
    content = response.text
    assert content.startswith("\ufeff")
    assert "Produto;EAN;Quantidade Total;Preço Médio;Total Gasto;Frequência Notas" in content
    assert "'-SECURE PROD" in content
    assert "888" in content
    assert "200.0" in content
    assert "1" in content # frequencia

@pytest.mark.asyncio
async def test_export_fornecedor_department_isolation(client):
    other_dept_id = uuid4()
    forn_id = uuid4()
    async with SessionLocal() as db:
        forn = Fornecedor(id=forn_id, razao_social="Secret Forn", cnpj="unique-secret-000")
        db.add(forn)
        await db.flush()
        
        nota = NotaFiscal(
            fornecedor_id=forn.id,
            numero_nota="000",
            chave_acesso="other-dept-key-drill-" + "0" * 28,
            data_emissao=date.today(),
            valor_total=Decimal("1000.00"),
            status="active",
            department_id=other_dept_id
        )

        db.add(nota)
        await db.commit()

    response = await client.get(f"/api/v1/dashboard/fornecedores/{forn_id}/export")
    assert response.status_code == 200
    # Header only, no data
    assert "Secret Forn" not in response.text


@pytest.mark.asyncio
async def test_export_audit_logs_sanitiza_csv_injection_e_isola_departamento(client):
    other_dept_id = uuid4()
    async with SessionLocal() as db:
        db.add(
            AuditLog(
                department_id=TEST_DEPT_ID,
                usuario="=cmd|' /C calc'!A0",
                operacao="+SUM(1,1)",
                entidade="-10+20",
                entidade_id="audit-safe-id",
                detalhes="@SUM(1+1)",
                ip_origem="127.0.0.1",
            )
        )
        db.add(
            AuditLog(
                department_id=other_dept_id,
                usuario="Other Department User",
                operacao="OTHER_DEPT",
                entidade="AuditLog",
                entidade_id="other-safe-id",
                detalhes="Other Department Leak",
                ip_origem="127.0.0.2",
            )
        )
        await db.commit()

    response = await client.get("/api/v1/dashboard/audit-logs/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "auditoria_logs.csv" in response.headers["content-disposition"]

    content = response.text
    assert "Data/Hora;Usuario;Operacao;Entidade;Detalhes;IP de Origem" in content
    assert "'=cmd|' /C calc'!A0" in content
    assert "'+SUM(1,1)" in content
    assert "'-10+20" in content
    assert "'@SUM(1+1)" in content
    assert "Other Department Leak" not in content


@pytest.mark.asyncio
async def test_list_audit_logs_filtra_operacao_busca_e_isola_departamento(client):
    other_dept_id = uuid4()
    async with SessionLocal() as db:
        db.add_all(
            [
                AuditLog(
                    department_id=TEST_DEPT_ID,
                    usuario="audit-h10q-user",
                    operacao="AUDIT_CHAT_BLOCKED",
                    entidade="AuditChat",
                    entidade_id="blocked-h10q-visible",
                    detalhes='{"reason": "blocked-h10q-safe"}',
                    ip_origem="127.0.0.1",
                ),
                AuditLog(
                    department_id=TEST_DEPT_ID,
                    usuario="audit-h10q-user",
                    operacao="LOGIN",
                    entidade="Session",
                    entidade_id="blocked-h10q-login",
                    detalhes="blocked-h10q-safe",
                    ip_origem="127.0.0.1",
                ),
                AuditLog(
                    department_id=other_dept_id,
                    usuario="audit-h10q-other",
                    operacao="AUDIT_CHAT_BLOCKED",
                    entidade="AuditChat",
                    entidade_id="blocked-h10q-other",
                    detalhes="blocked-h10q-safe",
                    ip_origem="127.0.0.2",
                ),
            ]
        )
        await db.commit()

    response = await client.get(
        "/api/v1/dashboard/audit-logs"
        "?operation=AUDIT_CHAT_BLOCKED&q=blocked-h10q-safe&limit=20"
    )

    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["operacao"] == "AUDIT_CHAT_BLOCKED"
    assert logs[0]["entidade_id"] == "blocked-h10q-visible"
    assert "blocked-h10q-other" not in str(logs)
    assert "blocked-h10q-login" not in str(logs)


@pytest.mark.asyncio
async def test_export_audit_logs_respeita_filtros_operacao_e_busca(client):
    other_dept_id = uuid4()
    async with SessionLocal() as db:
        db.add_all(
            [
                AuditLog(
                    department_id=TEST_DEPT_ID,
                    usuario="audit-export-h10q",
                    operacao="AUDIT_CHAT_BLOCKED",
                    entidade="AuditChat",
                    entidade_id="export-h10q-visible",
                    detalhes='{"reason": "export-h10q-safe"}',
                    ip_origem="127.0.0.1",
                ),
                AuditLog(
                    department_id=TEST_DEPT_ID,
                    usuario="audit-export-h10q",
                    operacao="IMPORT",
                    entidade="NotaFiscal",
                    entidade_id="export-h10q-import",
                    detalhes="export-h10q-safe",
                    ip_origem="127.0.0.1",
                ),
                AuditLog(
                    department_id=other_dept_id,
                    usuario="audit-export-h10q-other",
                    operacao="AUDIT_CHAT_BLOCKED",
                    entidade="AuditChat",
                    entidade_id="export-h10q-other",
                    detalhes="export-h10q-safe",
                    ip_origem="127.0.0.2",
                ),
            ]
        )
        await db.commit()

    response = await client.get(
        "/api/v1/dashboard/audit-logs/export"
        "?operation=AUDIT_CHAT_BLOCKED&q=export-h10q-safe"
    )

    assert response.status_code == 200
    content = response.text
    assert "audit-export-h10q;AUDIT_CHAT_BLOCKED;AuditChat" in content
    assert "export-h10q-safe" in content
    assert "export-h10q-import" not in content
    assert "export-h10q-other" not in content


@pytest.mark.asyncio
async def test_list_audit_logs_respeita_limit_offset(client):
    async with SessionLocal() as db:
        db.add_all(
            [
                AuditLog(
                    department_id=TEST_DEPT_ID,
                    usuario="audit-page-h10r",
                    operacao="LOGIN",
                    entidade="Session",
                    entidade_id=f"audit-page-h10r-{idx}",
                    detalhes="pagination-safe",
                    ip_origem="127.0.0.1",
                )
                for idx in range(3)
            ]
        )
        await db.commit()

    first = await client.get("/api/v1/dashboard/audit-logs?q=audit-page-h10r&limit=1&offset=0")
    second = await client.get("/api/v1/dashboard/audit-logs?q=audit-page-h10r&limit=1&offset=1")

    assert first.status_code == 200
    assert second.status_code == 200
    first_logs = first.json()
    second_logs = second.json()
    assert len(first_logs) == 1
    assert len(second_logs) == 1
    assert first_logs[0]["id"] != second_logs[0]["id"]
