"""Safety tests for the AI audit chat service."""

from __future__ import annotations

import asyncio
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
        == "SELECT * FROM (SELECT 12.30 AS total FROM notas_fiscais "
        "WHERE department_id = 'dept-a') AS audit_chat_limited LIMIT 50"
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


@pytest.mark.anyio
async def test_audit_chat_executes_wrapped_limited_query_without_generated_limit() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT valor_total FROM notas_fiscais WHERE department_id = 'dept-a'"

    async def fake_explain_data(question: str, data: list[dict]) -> str:
        return "Consulta limitada."

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql
    service._explain_data = fake_explain_data
    service.db.execute.return_value = SimpleNamespace(fetchall=lambda: [])

    result = await service.chat("Liste notas", department_id="dept-a")

    assert (
        result["query_used"]
        == "SELECT * FROM (SELECT valor_total FROM notas_fiscais "
        "WHERE department_id = 'dept-a') AS audit_chat_limited LIMIT 50"
    )
    executed = service.db.execute.await_args.args[0]
    assert str(executed) == result["query_used"]


@pytest.mark.anyio
async def test_audit_chat_timeout_returns_stable_error() -> None:
    service = _service()
    service.QUERY_TIMEOUT_SECONDS = 0.001

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT valor_total FROM notas_fiscais WHERE department_id = 'dept-a'"

    async def slow_execute(sql):
        await asyncio.sleep(1)

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql
    service.db.execute = slow_execute

    result = await service.chat("Liste notas", department_id="dept-a")

    assert result["error"] == "query_timeout"
    assert result["answer"] == "A consulta demorou demais e foi interrompida. Tente uma pergunta mais específica."


@pytest.mark.anyio
async def test_audit_chat_blocks_unknown_table_even_for_select() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT detalhes FROM audit_logs LIMIT 50"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste auditoria", department_id=None)

    assert result["error"] == "table_not_allowed"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_blocks_disallowed_qualified_column() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT p.created_at FROM produtos p LIMIT 50"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste criacao", department_id=None)

    assert result["error"] == "column_not_allowed"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_blocks_select_wildcard() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT * FROM produtos LIMIT 50"

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql

    result = await service.chat("Liste produtos", department_id=None)

    assert result["error"] == "wildcard_sql_blocked"
    service.db.execute.assert_not_called()


@pytest.mark.anyio
async def test_audit_chat_sanitizes_summary_and_explanation_payload() -> None:
    service = _service()

    async def fake_identify_intent(message: str) -> dict:
        return {"action": "QUERY"}

    async def fake_generate_sql(message: str, department_id: str | None) -> str:
        return "SELECT f.razao_social FROM fornecedores f LIMIT 50"

    async def fake_explain_data(question: str, data: list[dict]) -> str:
        assert data == [
            {
                "razao_social": "Fornecedor [redacted]",
                "valor_total": 10.5,
            }
        ]
        return (
            "Fornecedor 12.345.678/0001-99 com chave "
            "12345678901234567890123456789012345678901234"
        )

    fake_result = SimpleNamespace(
        fetchall=lambda: [
            SimpleNamespace(
                _mapping={
                    "razao_social": "Fornecedor 12.345.678/0001-99",
                    "cnpj": "12345678000199",
                    "chave_acesso": "12345678901234567890123456789012345678901234",
                    "valor_total": Decimal("10.50"),
                }
            )
        ]
    )

    service._identify_intent = fake_identify_intent
    service._generate_sql = fake_generate_sql
    service._explain_data = fake_explain_data
    service.db.execute.return_value = fake_result

    result = await service.chat("Liste fornecedores", department_id=None)

    assert result["data_summary"] == [
        {
            "razao_social": "Fornecedor [redacted]",
            "valor_total": 10.5,
        }
    ]
    assert "12.345.678/0001-99" not in result["answer"]
    assert "12345678901234567890123456789012345678901234" not in result["answer"]
    assert result["answer"] == "Fornecedor [redacted] com chave [redacted]"


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


def test_sql_allowlist_accepts_known_tables_columns_and_aliases() -> None:
    sql = (
        "SELECT nf.valor_total, f.razao_social "
        "FROM notas_fiscais nf "
        "JOIN fornecedores f ON f.id = nf.fornecedor_id "
        "WHERE nf.department_id = 'dept-a' "
        "LIMIT 50"
    )

    assert AuditChatService._get_allowlist_error(sql) is None


def test_sql_allowlist_allows_count_star_aggregate() -> None:
    sql = (
        "SELECT COUNT(*) AS total "
        "FROM notas_fiscais nf "
        "WHERE nf.department_id = 'dept-a'"
    )

    assert AuditChatService._get_allowlist_error(sql) is None


def test_sql_allowlist_allows_cte_over_allowed_tables() -> None:
    sql = (
        "WITH totais AS ("
        "SELECT nf.department_id, SUM(nf.valor_total) AS total "
        "FROM notas_fiscais nf "
        "WHERE nf.department_id = 'dept-a' "
        "GROUP BY nf.department_id"
        ") "
        "SELECT totais.total FROM totais"
    )

    assert AuditChatService._get_allowlist_error(sql) is None


def test_execution_sql_wrapper_enforces_outer_limit() -> None:
    sql = "SELECT valor_total FROM notas_fiscais LIMIT 1000;"

    assert (
        AuditChatService._limit_sql_for_execution(sql)
        == "SELECT * FROM (SELECT valor_total FROM notas_fiscais LIMIT 1000) "
        "AS audit_chat_limited LIMIT 50"
    )


@pytest.mark.parametrize(
    ("sql", "error"),
    [
        ("SELECT * FROM produtos", "wildcard_sql_blocked"),
        ("SELECT p.* FROM produtos p", "wildcard_sql_blocked"),
        ("SELECT detalhes FROM audit_logs", "table_not_allowed"),
        ("SELECT p.created_at FROM produtos p", "column_not_allowed"),
        ("SELECT u.username FROM users u", "sensitive_sql_blocked"),
    ],
)
def test_sql_safety_validator_blocks_queries_outside_allowlist(sql: str, error: str) -> None:
    assert AuditChatService._get_sql_safety_error(sql, department_id=None) == error


def test_chat_row_sanitizer_drops_sensitive_keys_and_redacts_values() -> None:
    rows = [
        {
            "produto": "Item seguro",
            "cnpj_fornecedor": "12345678000199",
            "chave_nfe": "12345678901234567890123456789012345678901234",
            "url_sefaz": "https://nfe.sefaz.go.gov.br/consulta",
            "observacao": "CPF 123.456.789-00",
            "total": 12.3,
        }
    ]

    assert AuditChatService._sanitize_chat_rows(rows) == [
        {
            "produto": "Item seguro",
            "observacao": "CPF [redacted]",
            "total": 12.3,
        }
    ]
