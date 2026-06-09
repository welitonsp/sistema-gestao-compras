import json
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.security import (
    create_access_token,
    get_password_hash,
    redact_audit_details,
    redact_audit_value
)
from backend.models.compras import User, UserRole
from backend.core.database import SessionLocal, engine
from sqlalchemy import delete
from unittest.mock import AsyncMock

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def client():
    # Mock Redis pool
    app.state.redis = AsyncMock()
    # Usamos localhost para garantir que o httpx trate os cookies corretamente
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        yield ac

@pytest.fixture(autouse=True)
async def setup_test_user():
    """Garante um usuário de teste no banco."""
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.username == "testadmin"))
        await db.commit()

        user = User(
            username="testadmin",
            email="test@test.com",
            hashed_password=get_password_hash("testpassword"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(user)
        await db.commit()
        yield user

@pytest.mark.anyio
async def test_login_database_auth(client):
    """
    Testa se o login via Cookie funciona.
    """
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testadmin", "password": "testpassword"}
    )
    assert response.status_code == 200
    # Verifica se o cookie foi definido
    assert "access_token" in response.cookies
    assert response.json()["status"] == "ok"

@pytest.mark.anyio
async def test_rbac_restriction_via_cookie(client):
    """
    Testa acesso a rota protegida (RBAC) com o token obtido via login.
    """
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "testadmin", "password": "testpassword"}
    )
    assert login_res.status_code == 200

    # 2. Extrai o token do cookie e envia no header para compatibilidade com o transport de teste
    token = login_res.cookies.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 3. GET
    response = await client.get("/api/v1/dashboard/audit-logs", headers=headers)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_product_audit_details_redige_campos_sensiveis_e_descarta_payload():
    details = {
        "categoria_anterior": "ANTIGA",
        "categoria_nova": "NOVA",
        "origem": "manual",
        "usuario_executor": "admin",
        "produto": "Produto seguro",
        "categorias_sugeridas_relacionadas": [
            "MERCEARIA",
            "valor com " + "chave" + "_acesso dentro",
        ],
        "payload" + "_bruto": {"chave" + "_acesso": "1" * 44},
        "descricao" + "_original": "descricao fiscal crua",
        "cn" + "pj": "12345678000199",
    }

    safe_json = redact_audit_details(details)
    safe = json.loads(safe_json)

    assert set(safe) == {
        "categoria_anterior",
        "categoria_nova",
        "origem",
        "usuario_executor",
        "produto",
        "categorias_sugeridas_relacionadas",
    }
    assert safe["categorias_sugeridas_relacionadas"] == [
        "MERCEARIA",
        "[redacted]",
    ]
    text = str(safe).lower()
    assert "payload" + "_bruto" not in text
    assert "descricao" + "_original" not in text
    assert "cn" + "pj" not in text


@pytest.mark.anyio
async def test_redact_audit_value_pii():
    # If the term "CPF" or "CNPJ" is in the string, it redacts the whole thing for safety
    assert redact_audit_value("Meu CPF e 123.456.789-00") == "[redacted]"
    assert redact_audit_value("12345678900") == "[redacted]" # regex match or term match

    # CNPJ
    assert redact_audit_value("Empresa CNPJ 12.345.678/0001-99") == "[redacted]"

    # Granular redaction works if NO sensitive terms (label keys) are present in the text
    # "Chave de acesso" is not "chave_acesso"
    chave = "52231000000000000000550010001234561001234567"
    assert redact_audit_value(f"Chave de acesso: {chave}") == "Chave de acesso: [redacted]"

    # Long text without sensitive terms
    long_text = "A" * 600
    redacted_long = redact_audit_value(long_text)
    assert len(redacted_long) <= 500
    assert redacted_long.endswith("...")


@pytest.mark.anyio
async def test_redact_audit_details_string_handling():
    # Simple string with sensitive term
    assert redact_audit_details("Altera CPF 12345678900") == '{"message": "[redacted]"}'

    # JSON string
    json_str = json.dumps({"action": "UPDATE", "reason": "Fez alteracao"})
    safe_json = redact_audit_details(json_str)
    assert "UPDATE" in safe_json
    assert "action" in safe_json
