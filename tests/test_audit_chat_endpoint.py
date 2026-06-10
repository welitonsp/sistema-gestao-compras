"""Authorization tests for the AI audit chat endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user
from backend.main import app
from backend.models.compras import User, UserRole
from backend.services.chat_service import AuditChatService


def _user(role: UserRole, department_id=None) -> User:
    return User(
        id=uuid4(),
        username=f"h10h_{role.value}_{uuid4().hex[:8]}",
        email=f"h10h-{uuid4().hex[:8]}@example.com",
        role=role,
        department_id=department_id,
        is_active=True,
    )


async def _post_chat_as(user: User, monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def mock_current_user() -> User:
        return user

    async def mock_chat(self, message: str, department_id=None):
        calls.append({"message": message, "department_id": department_id})
        return {"answer": "ok", "department_id": str(department_id) if department_id else None}

    app.dependency_overrides[get_current_user] = mock_current_user
    monkeypatch.setattr(AuditChatService, "chat", mock_chat)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"message": "Qual o total de compras?"},
            )
    finally:
        app.dependency_overrides.clear()

    return response, calls


@pytest.mark.asyncio
async def test_audit_chat_endpoint_allows_manager_with_department(monkeypatch):
    department_id = uuid4()

    response, calls = await _post_chat_as(
        _user(UserRole.MANAGER, department_id=department_id),
        monkeypatch,
    )

    assert response.status_code == 200
    assert calls == [
        {"message": "Qual o total de compras?", "department_id": department_id}
    ]


@pytest.mark.asyncio
async def test_audit_chat_endpoint_allows_auditor_with_department(monkeypatch):
    department_id = uuid4()

    response, calls = await _post_chat_as(
        _user(UserRole.AUDITOR, department_id=department_id),
        monkeypatch,
    )

    assert response.status_code == 200
    assert calls == [
        {"message": "Qual o total de compras?", "department_id": department_id}
    ]


@pytest.mark.asyncio
async def test_audit_chat_endpoint_allows_admin_without_department(monkeypatch):
    response, calls = await _post_chat_as(
        _user(UserRole.ADMIN, department_id=None),
        monkeypatch,
    )

    assert response.status_code == 200
    assert calls == [
        {"message": "Qual o total de compras?", "department_id": None}
    ]


@pytest.mark.asyncio
async def test_audit_chat_endpoint_blocks_operator(monkeypatch):
    response, calls = await _post_chat_as(
        _user(UserRole.OPERATOR, department_id=uuid4()),
        monkeypatch,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Voce nao tem permissao para realizar esta operacao."
    assert calls == []


@pytest.mark.asyncio
async def test_audit_chat_endpoint_blocks_non_admin_without_department(monkeypatch):
    response, calls = await _post_chat_as(
        _user(UserRole.MANAGER, department_id=None),
        monkeypatch,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Usuario sem departamento nao pode usar o chat de auditoria."
    assert calls == []
