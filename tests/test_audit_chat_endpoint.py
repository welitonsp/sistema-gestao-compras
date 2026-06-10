"""Authorization tests for the AI audit chat endpoint."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import AuditLog, User, UserRole
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


async def _post_chat_with_result(
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    result: dict,
    message: str = "Qual o total de compras?",
):
    calls = []

    async def mock_current_user() -> User:
        return user

    async def mock_chat(self, chat_message: str, department_id=None):
        calls.append({"message": chat_message, "department_id": department_id})
        return result

    app.dependency_overrides[get_current_user] = mock_current_user
    monkeypatch.setattr(AuditChatService, "chat", mock_chat)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/chat", json={"message": message})
    finally:
        app.dependency_overrides.clear()

    return response, calls


async def _clear_chat_audit_logs() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(AuditLog).where(AuditLog.operacao == "AUDIT_CHAT_BLOCKED"))
        await db.commit()


async def _fetch_chat_audit_logs() -> list[AuditLog]:
    async with SessionLocal() as db:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.operacao == "AUDIT_CHAT_BLOCKED")
            .order_by(AuditLog.created_at)
        )
        return list(result.scalars().all())


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


@pytest.mark.asyncio
async def test_audit_chat_endpoint_logs_blocked_result_without_raw_payload(monkeypatch):
    await _clear_chat_audit_logs()
    department_id = uuid4()
    user = _user(UserRole.MANAGER, department_id=department_id)

    response, calls = await _post_chat_with_result(
        user,
        monkeypatch,
        {
            "answer": "bloqueado",
            "blocked_reason": "audit_chat_is_read_only",
            "query_used": "SELECT cnpj FROM fornecedores",
        },
        message="Corrija categoria do CPF 123.456.789-00",
    )

    assert response.status_code == 200
    assert calls == [
        {"message": "Corrija categoria do CPF 123.456.789-00", "department_id": department_id}
    ]

    logs = await _fetch_chat_audit_logs()
    assert len(logs) == 1
    log = logs[0]
    assert log.department_id == department_id
    assert log.usuario == user.username
    assert log.entidade == "AuditChat"
    assert log.entidade_id == "audit_chat_is_read_only"

    details = json.loads(log.detalhes)
    assert details == {
        "action": "audit_chat_blocked",
        "department_id": str(department_id),
        "origem": "audit_chat",
        "reason": "audit_chat_is_read_only",
        "usuario_executor": user.username,
    }
    serialized = json.dumps(details, ensure_ascii=False)
    assert "123.456.789-00" not in serialized
    assert "cnpj" not in serialized.lower()
    assert "SELECT" not in serialized


@pytest.mark.asyncio
async def test_audit_chat_endpoint_does_not_log_successful_result(monkeypatch):
    await _clear_chat_audit_logs()

    response, calls = await _post_chat_with_result(
        _user(UserRole.AUDITOR, department_id=uuid4()),
        monkeypatch,
        {"answer": "ok", "data_summary": []},
    )

    assert response.status_code == 200
    assert calls
    assert await _fetch_chat_audit_logs() == []
