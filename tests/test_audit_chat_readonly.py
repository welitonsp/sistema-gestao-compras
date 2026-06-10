"""Safety tests for the AI audit chat service."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.chat_service import AuditChatService


def _service() -> AuditChatService:
    service = AuditChatService.__new__(AuditChatService)
    service.db = AsyncMock()
    service.client = None
    service.model_name = "test-model"
    return service


@pytest.mark.anyio
async def test_audit_chat_blocks_category_mutation_intent() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {
            "action": "UPDATE_CATEGORY",
            "ean": "7890000000001",
            "nova_categoria": "LIMPEZA",
        }

    service._identify_intent = fake_identify_intent

    result = await service.chat(
        "Corrija o produto 7890000000001 para LIMPEZA",
        department_id="dept-a",
    )

    assert result["blocked_reason"] == "audit_chat_is_read_only"
    assert result["action_performed"] is None
    service.db.execute.assert_not_called()
    service.db.commit.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_blocks_non_read_only_sql() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "UPDATE produtos SET categoria = 'LIMPEZA'"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Atualize categorias", department_id="dept-a")

    assert result["error"] == "unsafe_sql_blocked"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_executes_single_select_query() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT 12.30 AS total FROM notas_fiscais WHERE department_id = 'dept-a'"

    async def fake_explain_data(question: str, data: list[dict]) -> str:
        assert data == [{"total": 12.3}]
        return "Total encontrado: 12,30."

    fake_result = SimpleNamespace(
        fetchall=lambda: [SimpleNamespace(_mapping={"total": Decimal("12.30")})]
    )

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql
    service._explain_data = fake_explain_data
    service.db.execute.return_value = fake_result

    result = await service.chat("Qual o total?", department_id="dept-a")

    assert result["answer"] == "Total encontrado: 12,30."
    assert (
        result["query_used"]
        == "SELECT 12.30 AS total FROM notas_fiscais WHERE department_id = 'dept-a'"
    )
    service.db.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_audit_chat_blocks_tenant_query_without_department_filter() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT valor_total FROM notas_fiscais LIMIT 50"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste notas", department_id="dept-a")

    assert result["error"] == "tenant_scope_missing"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_blocks_query_with_different_department_filter() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT valor_total FROM notas_fiscais WHERE department_id = 'dept-b'"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste notas", department_id="dept-a")

    assert result["error"] == "tenant_scope_missing"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_blocks_sensitive_sql_fields() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT cnpj FROM fornecedores LIMIT 50"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste CNPJ", department_id=None)

    assert result["error"] == "sensitive_sql_blocked"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_allows_admin_select_without_department_filter() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT valor_total FROM notas_fiscais LIMIT 50"

    async def fake_explain_data(question: str, data: list[dict]) -> str:
        return "Resultado administrativo."

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql
    service._explain_data = fake_explain_data
    service.db.execute.return_value = SimpleNamespace(fetchall=lambda: [])

    result = await service.chat("Liste notas", department_id=None)

    assert result["answer"] == "Resultado administrativo."
    service.db.execute.assert_awaited_once()


def test_read_only_sql_validator_accepts_select_and_with() -> None:
    assert AuditChatService._is_read_only_sql("SELECT * FROM produtos;")
    assert AuditChatService._is_read_only_sql(
        "WITH totais AS (SELECT 1 AS total) SELECT total FROM totais"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "UPDATE produtos SET categoria = 'X'",
        "DELETE FROM produtos",
        "SELECT * FROM produtos; DROP TABLE produtos",
        "INSERT INTO produtos(ean) VALUES ('1')",
        "WITH deleted AS (DELETE FROM produtos RETURNING *) SELECT * FROM deleted",
    ],
)
def test_read_only_sql_validator_rejects_writes_and_multi_statement(sql: str) -> None:
    assert not AuditChatService._is_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT cnpj FROM fornecedores",
        "SELECT chave_acesso FROM notas_fiscais",
        "SELECT * FROM users",
        "SELECT payload_bruto FROM audit_logs",
        "SELECT email FROM users",
    ],
)
def test_sensitive_sql_validator_rejects_private_identifiers(sql: str) -> None:
    assert AuditChatService._contains_sensitive_sql(sql)


def test_tenant_scope_validator_requires_exact_department_filter() -> None:
    assert AuditChatService._is_tenant_scoped_sql(
        "SELECT valor_total FROM notas_fiscais WHERE nf.department_id = 'dept-a'",
        "dept-a",
    )
    assert not AuditChatService._is_tenant_scoped_sql(
        "SELECT valor_total FROM notas_fiscais WHERE department_id = 'dept-b'",
        "dept-a",
    )
