import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.security import create_access_token, get_password_hash
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
