import pytest
import json
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.models.compras import User, UserRole, Department
from backend.core.security import get_password_hash, create_access_token
from backend.core.database import SessionLocal
from sqlalchemy import delete
from uuid import uuid4

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def test_data():
    """Cria dados de teste: departamento e vários usuários."""
    async with SessionLocal() as db:
        # Cleanup
        await db.execute(delete(User))
        await db.execute(delete(Department))
        await db.commit()

        # 1. Departamento
        dept = Department(id=uuid4(), name="Depto Teste")
        db.add(dept)
        await db.flush()

        # 2. Admin
        admin = User(
            username="admin_user",
            hashed_password=get_password_hash("password"),
            role=UserRole.ADMIN,
            is_active=True
        )

        # 3. Manager com Depto
        manager_with_dept = User(
            username="manager_with_dept",
            hashed_password=get_password_hash("password"),
            role=UserRole.MANAGER,
            department_id=dept.id,
            is_active=True
        )

        # 4. Manager sem Depto
        manager_no_dept = User(
            username="manager_no_dept",
            hashed_password=get_password_hash("password"),
            role=UserRole.MANAGER,
            is_active=True
        )

        # 5. Auditor com Depto
        auditor_with_dept = User(
            username="auditor_with_dept",
            hashed_password=get_password_hash("password"),
            role=UserRole.AUDITOR,
            department_id=dept.id,
            is_active=True
        )

        # 6. Auditor sem Depto
        auditor_no_dept = User(
            username="auditor_no_dept",
            hashed_password=get_password_hash("password"),
            role=UserRole.AUDITOR,
            is_active=True
        )

        # 7. Operator
        operator = User(
            username="operator_user",
            hashed_password=get_password_hash("password"),
            role=UserRole.OPERATOR,
            is_active=True
        )

        db.add_all([
            admin,
            manager_with_dept,
            manager_no_dept,
            auditor_with_dept,
            auditor_no_dept,
            operator
        ])
        await db.commit()

        return {
            "admin": admin,
            "manager_with_dept": manager_with_dept,
            "manager_no_dept": manager_no_dept,
            "auditor_with_dept": auditor_with_dept,
            "auditor_no_dept": auditor_no_dept,
            "operator": operator,
            "dept_id": dept.id
        }

async def get_headers(user: User):
    token = create_access_token({"sub": user.username})
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.anyio
async def test_agent_query_stub_admin(client, test_data):
    headers = await get_headers(test_data["admin"])
    payload = {"message": "Olá agente"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "implantação" in data["answer"]
    assert data["intent"] == "UNSUPPORTED"
    assert data["status"] == "insufficient_data"
    assert data["metadata"]["row_count"] == 0
    assert data["recommendations"] == []
    # Segurança: Não deve ter campos proibidos
    assert "query_hash" not in data["metadata"]
    assert "cpf" not in data
    assert "cnpj" not in data

@pytest.mark.anyio
async def test_agent_query_stub_manager_with_dept(client, test_data):
    headers = await get_headers(test_data["manager_with_dept"])
    payload = {"message": "Como manager com depto"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 200
    assert "implantação" in response.json()["answer"]

@pytest.mark.anyio
async def test_agent_query_stub_manager_no_dept(client, test_data):
    headers = await get_headers(test_data["manager_no_dept"])
    payload = {"message": "Como manager sem depto"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 403
    assert "departamento associado" in response.json()["detail"]

@pytest.mark.anyio
async def test_agent_query_stub_auditor_with_dept(client, test_data):
    headers = await get_headers(test_data["auditor_with_dept"])
    payload = {"message": "Como auditor com depto"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 200
    assert "implantação" in response.json()["answer"]

@pytest.mark.anyio
async def test_agent_query_stub_auditor_no_dept(client, test_data):
    headers = await get_headers(test_data["auditor_no_dept"])
    payload = {"message": "Como auditor sem depto"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 403
    assert "departamento associado" in response.json()["detail"]

@pytest.mark.anyio
async def test_agent_query_stub_operator_denied(client, test_data):
    headers = await get_headers(test_data["operator"])
    payload = {"message": "Como operador"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)

    assert response.status_code == 403
    # Mensagem padrão do RoleChecker
    assert "permissao" in response.json()["detail"].lower()

@pytest.mark.anyio
async def test_agent_query_invalid_payload(client, test_data):
    headers = await get_headers(test_data["admin"])
    # Mensagem vazia (validada pelo schema AgentQueryRequest)
    payload = {"message": ""}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)
    assert response.status_code == 422

@pytest.mark.anyio
async def test_agent_query_no_sensitive_fields_in_serialization(client, test_data):
    headers = await get_headers(test_data["admin"])
    payload = {"message": "Teste de segurança"}

    response = await client.post("/api/v1/agent/query", json=payload, headers=headers)
    assert response.status_code == 200

    raw_text = response.text.lower()
    forbidden_terms = [
        "query_hash",
        "cpf",
        "cnpj",
        "chave_acesso",
        "qr_code",
        "url_sefaz",
        "xml",
        "json_bruto",
        "payload_fiscal",
        "raw_payload"
    ]

    for term in forbidden_terms:
        assert term not in raw_text, f"Termo proibido '{term}' encontrado na resposta serializada."
