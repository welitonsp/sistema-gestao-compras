from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import (
    AuditLog,
    ClassificacaoCache,
    Fornecedor,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
    UserRole,
)
from backend.services import product_categorization


TEST_DEPT_ID = uuid4()
OTHER_DEPT_ID = uuid4()

test_user = User(
    id=uuid4(),
    username="ai_preview_user",
    email="ai-preview@example.com",
    role=UserRole.MANAGER,
    department_id=TEST_DEPT_ID,
    is_active=True,
)


async def mock_get_current_user() -> User:
    return test_user


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user

    from unittest.mock import AsyncMock

    app.state.redis = AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(AuditLog))
        await db.execute(delete(ClassificacaoCache))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        await db.commit()


def _access_key(seed: str) -> str:
    return (seed + ("0" * 44))[:44]


async def _add_product_purchase(
    *,
    ean: str,
    name: str,
    note_seed: str,
    current_category: str | None = "Outros",
    department_id: UUID | None = TEST_DEPT_ID,
    status: str = "active",
    item_category: str | None = None,
    item_confidence: Decimal | None = None,
) -> None:
    async with SessionLocal() as db:
        product = Produto(
            ean=ean,
            nome_limpo=name,
            categoria=current_category,
            unidade="un",
        )
        supplier = Fornecedor(
            id=uuid4(),
            razao_social=f"Fornecedor {note_seed}",
            cnpj=(note_seed[-14:] + "9" * 14)[:14],
        )
        db.add_all([product, supplier])
        await db.flush()

        invoice = NotaFiscal(
            fornecedor_id=supplier.id,
            numero_nota=f"N-{note_seed}",
            chave_acesso=_access_key(f"key-{note_seed}"),
            data_emissao=date(2026, 5, 26),
            valor_total=Decimal("10.00"),
            status=status,
            department_id=department_id,
        )
        db.add(invoice)
        await db.flush()

        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=invoice.id,
                ean=ean,
                descricao_original=f"Descricao {note_seed}",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("10.00"),
                valor_total=Decimal("10.00"),
                categoria_sugerida=item_category,
                categoria_sugerida_confidence=item_confidence,
            )
        )
        await db.commit()


def _mock_provider(monkeypatch, calls: list[dict], response: dict | None = None):
    async def provider(payload: dict) -> dict | None:
        calls.append(payload)
        return response or {
            "suggested_category": "Alimentos",
            "confidence": 0.82,
            "reason": "Nome canônico compatível com categoria permitida.",
        }

    monkeypatch.setattr(
        product_categorization,
        "get_ai_category_suggestion_preview",
        provider,
    )


@pytest.mark.asyncio
async def test_enable_ai_default_false_nao_chama_provider(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001001",
        name="PRODUTO SEM REGRA DEFAULT",
        note_seed="default-off",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    assert calls == []
    assert response.json()["candidates"][0]["source"] == "none"


@pytest.mark.asyncio
async def test_enable_ai_false_mantem_comportamento_atual(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001002",
        name="PRODUTO SEM REGRA FALSE",
        note_seed="false-a",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    default_response = await client.get("/api/v1/produtos/categorization/candidates")
    explicit_response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=false"
    )

    assert calls == []
    assert default_response.json() == explicit_response.json()


@pytest.mark.asyncio
async def test_enable_ai_chama_provider_apenas_para_source_none(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001003",
        name="PRODUTO SEM REGRA OPTIN",
        note_seed="none-source",
    )
    await _add_product_purchase(
        ean="7891000001004",
        name="PRODUTO COM ITEM SUGERIDO",
        note_seed="item-source",
        item_category="Limpeza",
        item_confidence=Decimal("0.80"),
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert len(calls) == 1
    sources = {item["ean"]: item["source"] for item in response.json()["candidates"]}
    assert sources["7891000001003"] == "ai_fallback"
    assert sources["7891000001004"] == "item_suggestion"


@pytest.mark.asyncio
async def test_ai_limit_limita_quantidade_de_chamadas(client, monkeypatch):
    await _cleanup()
    for index in range(3):
        await _add_product_purchase(
            ean=f"78910000010{10 + index}",
            name=f"PRODUTO SEM REGRA LIMIT {index}",
            note_seed=f"limit-{index}",
        )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true&ai_limit=2"
    )

    assert response.status_code == 200
    assert len(calls) == 2
    assert sum(
        1 for item in response.json()["candidates"] if item["source"] == "ai_fallback"
    ) == 2


@pytest.mark.asyncio
async def test_produto_com_sanitizacao_falha_nao_chama_provider(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001014",
        name="5" * 44,
        note_seed="unsafe-name",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert calls == []
    assert response.json()["candidates"][0]["source"] == "none"


@pytest.mark.asyncio
async def test_provider_recebe_apenas_nome_sanitizado_e_categorias(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001015",
        name="  Produto   Seguro  ",
        note_seed="safe-provider",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert calls == [
        {
            "sanitized_product_name": "Produto Seguro",
            "allowed_categories": product_categorization.ALLOWED_AI_CATEGORIES,
        }
    ]
    rendered = json.dumps(calls[0], ensure_ascii=False).lower()
    for forbidden in (
        "ean",
        "fornecedor",
        "cpf",
        "cnpj",
        "chave",
        "numero",
        "sefaz",
        "qr",
        "xml",
        "json bruto",
        "payload bruto",
    ):
        assert forbidden not in rendered


@pytest.mark.asyncio
async def test_resposta_valida_gera_ai_fallback_e_can_confirm(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001016",
        name="PRODUTO BEBIDA FUTURA",
        note_seed="valid-ai",
    )
    calls: list[dict] = []
    _mock_provider(
        monkeypatch,
        calls,
        {
            "suggested_category": "Bebidas",
            "confidence": 0.7,
            "reason": "Nome canônico sugere bebida.",
        },
    )

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    candidate = response.json()["candidates"][0]
    assert candidate["source"] == "ai_fallback"
    assert candidate["suggested_category"] == "Bebidas"
    assert candidate["confidence"] == 0.7
    assert candidate["confidence_level"] == "medium"
    assert candidate["can_confirm"] is True


@pytest.mark.asyncio
async def test_categoria_fora_da_allowlist_mantem_source_none(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001017",
        name="PRODUTO CATEGORIA LIVRE",
        note_seed="outside-ai",
    )
    calls: list[dict] = []
    _mock_provider(
        monkeypatch,
        calls,
        {
            "suggested_category": "Categoria Livre",
            "confidence": 0.99,
            "reason": "Tentativa fora da lista.",
        },
    )

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    candidate = response.json()["candidates"][0]
    assert len(calls) == 1
    assert candidate["source"] == "none"
    assert candidate["suggested_category"] is None
    assert candidate["can_confirm"] is False


@pytest.mark.asyncio
async def test_provider_exception_mantem_source_none_sem_quebrar(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001018",
        name="PRODUTO EXCEPTION AI",
        note_seed="exception-ai",
    )
    calls: list[dict] = []

    async def provider(payload: dict) -> dict:
        calls.append(payload)
        raise TimeoutError("provider unavailable")

    monkeypatch.setattr(
        product_categorization,
        "get_ai_category_suggestion_preview",
        provider,
    )

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()["candidates"][0]["source"] == "none"


@pytest.mark.asyncio
async def test_endpoint_enable_ai_nao_escreve_banco_cache_ou_auditlog(
    client, monkeypatch
):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001019",
        name="PRODUTO READ ONLY AI",
        note_seed="read-only-ai",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    async with SessionLocal() as db:
        cache_before = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_before = await db.scalar(select(func.count()).select_from(AuditLog))

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    async with SessionLocal() as db:
        product = await db.get(Produto, "7891000001019")
        item = await db.scalar(
            select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7891000001019")
        )
        invoice = await db.scalar(
            select(NotaFiscal).where(NotaFiscal.id == item.nota_fiscal_id)
        )
        cache_after = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_after = await db.scalar(select(func.count()).select_from(AuditLog))

    assert product.categoria == "Outros"
    assert product.categoria_confirmada is None
    assert item.categoria_sugerida is None
    assert invoice.status == "active"
    assert cache_after == cache_before
    assert audit_after == audit_before


@pytest.mark.asyncio
async def test_enable_ai_respeita_department_isolation(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001020",
        name="PRODUTO OUTRO DEPARTAMENTO AI",
        note_seed="other-dept-ai",
        department_id=OTHER_DEPT_ID,
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert calls == []
    assert response.json()["candidates"] == []


@pytest.mark.asyncio
async def test_enable_ai_ignora_notas_inativas(client, monkeypatch):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000001021",
        name="PRODUTO INATIVO AI",
        note_seed="inactive-ai",
        status="archived",
    )
    calls: list[dict] = []
    _mock_provider(monkeypatch, calls)

    response = await client.get(
        "/api/v1/produtos/categorization/candidates?enable_ai=true"
    )

    assert response.status_code == 200
    assert calls == []
    assert response.json()["candidates"] == []
