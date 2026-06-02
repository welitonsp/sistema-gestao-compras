import json
import re
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import Fornecedor, ItemNotaFiscal, NotaFiscal, User, UserRole
from backend.services import webhook_service as webhook_module


TEST_DEPT_ID = uuid4()
test_user = User(
    id=uuid4(),
    username="test_duplicate_security_user",
    email="duplicate-security@example.com",
    role=UserRole.MANAGER,
    department_id=TEST_DEPT_ID,
    is_active=True,
)


async def mock_get_current_user():
    return test_user


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.state.redis = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _string_values(nested)


@pytest.mark.asyncio
async def test_dashboard_duplicidade_nao_expoe_chaves_nfce(client, monkeypatch):
    trigger_event = AsyncMock()
    monkeypatch.setattr(webhook_module.webhook_service, "trigger_event", trigger_event)

    async with SessionLocal() as db:
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))

        fornecedor = Fornecedor(
            id=uuid4(),
            razao_social="Fornecedor Duplicado Seguro",
            cnpj="dup-sec-001",
        )
        db.add(fornecedor)
        await db.flush()

        duplicate_date = date(2026, 1, 15)
        db.add_all(
            [
                NotaFiscal(
                    fornecedor_id=fornecedor.id,
                    numero_nota="101",
                    chave_acesso="1" * 44,
                    data_emissao=duplicate_date,
                    valor_total=Decimal("123.45"),
                    status="active",
                    department_id=TEST_DEPT_ID,
                ),
                NotaFiscal(
                    fornecedor_id=fornecedor.id,
                    numero_nota="102",
                    chave_acesso="2" * 44,
                    data_emissao=duplicate_date,
                    valor_total=Decimal("123.45"),
                    status="active",
                    department_id=TEST_DEPT_ID,
                ),
            ]
        )
        await db.commit()

    response = await client.get("/api/v1/dashboard/alertas/duplicidade")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "fornecedor": "Fornecedor Duplicado Seguro",
            "data": "2026-01-15",
            "valor": 123.45,
            "quantidade_notas": 2,
        }
    ]

    response_text = response.text
    assert "chaves" not in response_text
    assert "chave_acesso" not in response_text
    assert not re.search(r"\d{44}", response_text)
    assert all(not re.search(r"\d{44}", value) for value in _string_values(body))

    trigger_event.assert_awaited_once()
    event_type, department_id, payload = trigger_event.await_args.args
    assert event_type == "invoice.duplicate_detected"
    assert department_id == TEST_DEPT_ID
    assert "chaves" not in payload
    assert "chave_acesso" not in payload
    assert not re.search(r"\d{44}", json.dumps(payload))
