from __future__ import annotations

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
from backend.services.product_categorization import normalizar_descricao_produto


TEST_DEPT_ID = uuid4()
OTHER_DEPT_ID = uuid4()

test_user = User(
    id=uuid4(),
    username="category_candidates_user",
    email="category-candidates@example.com",
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
    current_category: str | None = "Outros",
    confirmed_category: str | None = None,
    note_seed: str,
    department_id: UUID | None = TEST_DEPT_ID,
    status: str = "active",
    item_category: str | None = None,
    item_confidence: Decimal | None = None,
    description: str | None = None,
) -> None:
    async with SessionLocal() as db:
        product = await db.get(Produto, ean)
        if product is None:
            product = Produto(
                ean=ean,
                nome_limpo=name,
                categoria=current_category,
                categoria_confirmada=confirmed_category,
                unidade="un",
            )
            db.add(product)

        supplier = Fornecedor(
            id=uuid4(),
            razao_social=f"Fornecedor {note_seed}",
            cnpj=(note_seed[-14:] + "9" * 14)[:14],
        )
        db.add(supplier)
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
                descricao_original=description or name,
                quantidade=Decimal("1"),
                valor_unitario=Decimal("10.00"),
                valor_total=Decimal("10.00"),
                categoria_sugerida=item_category,
                categoria_sugerida_confidence=item_confidence,
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_endpoint_retorna_200_e_schema_esperado(client):
    await _cleanup()

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    assert response.json() == {
        "total_candidates": 0,
        "returned_count": 0,
        "candidates": [],
    }


@pytest.mark.asyncio
async def test_produto_com_categoria_confirmada_nao_aparece(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000001",
        name="ARROZ CONFIRMADO",
        current_category="MERCEARIA",
        confirmed_category="MERCEARIA",
        note_seed="confirmed",
        item_category="MERCEARIA",
        item_confidence=Decimal("0.90"),
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    assert response.json()["candidates"] == []


@pytest.mark.asyncio
async def test_produto_sem_categoria_ou_outros_aparece(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000002",
        name="ARROZ TIPO 1",
        current_category="Outros",
        note_seed="uncategorized",
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["ean"] == "7891000000002"
    assert candidates[0]["current_category"] == "Outros"


@pytest.mark.asyncio
async def test_sugestao_por_item_nota_fiscal_e_usada(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000003",
        name="PRODUTO COM SUGESTAO",
        current_category="Sem Categoria",
        note_seed="item-suggestion-a",
        item_category="LIMPEZA",
        item_confidence=Decimal("0.70"),
    )
    await _add_product_purchase(
        ean="7891000000003",
        name="PRODUTO COM SUGESTAO",
        current_category="Sem Categoria",
        note_seed="item-suggestion-b",
        item_category="LIMPEZA",
        item_confidence=Decimal("0.90"),
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    candidate = response.json()["candidates"][0]
    assert candidate["suggested_category"] == "LIMPEZA"
    assert candidate["source"] == "item_suggestion"
    assert candidate["confidence"] == 0.8
    assert candidate["confidence_level"] == "high"
    assert candidate["can_confirm"] is True


@pytest.mark.asyncio
async def test_sugestao_por_classificacao_cache_e_usada(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000004",
        name="PRODUTO CACHE TESTE",
        current_category=None,
        note_seed="cache",
    )

    async with SessionLocal() as db:
        db.add(
            ClassificacaoCache(
                descricao_original=normalizar_descricao_produto("PRODUTO CACHE TESTE"),
                produto_canonico="PRODUTO CACHE TESTE",
                categoria="BEBIDAS",
                unidade="un",
                verificado_usuario=True,
            )
        )
        await db.commit()

    response = await client.get("/api/v1/produtos/categorization/candidates")

    candidate = response.json()["candidates"][0]
    assert candidate["suggested_category"] == "BEBIDAS"
    assert candidate["source"] == "classification_cache"
    assert candidate["confidence"] == 0.85


@pytest.mark.asyncio
async def test_sem_sugestao_retorna_insufficient_data_sem_inventar_categoria(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000005",
        name="PRODUTO SINTETICO SEM REGRA",
        current_category="Outros",
        note_seed="no-suggestion",
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    candidate = response.json()["candidates"][0]
    assert candidate["suggested_category"] is None
    assert candidate["confidence"] == 0
    assert candidate["confidence_level"] == "insufficient_data"
    assert candidate["source"] == "none"
    assert candidate["can_confirm"] is False


@pytest.mark.asyncio
async def test_respeita_department_isolation(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000006",
        name="ARROZ OUTRO DEPARTAMENTO",
        current_category="Outros",
        note_seed="other-dept",
        department_id=OTHER_DEPT_ID,
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    assert response.json()["candidates"] == []


@pytest.mark.asyncio
async def test_ignora_notas_inativas(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000007",
        name="ARROZ INATIVO",
        current_category="Outros",
        note_seed="inactive",
        status="archived",
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    assert response.json()["candidates"] == []


@pytest.mark.asyncio
async def test_limit_limita_quantidade_retornada(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000008",
        name="ARROZ LIMIT A",
        current_category="Outros",
        note_seed="limit-a",
    )
    await _add_product_purchase(
        ean="7891000000009",
        name="FEIJAO LIMIT B",
        current_category="Outros",
        note_seed="limit-b",
    )

    response = await client.get("/api/v1/produtos/categorization/candidates?limit=1")

    payload = response.json()
    assert payload["total_candidates"] == 2
    assert payload["returned_count"] == 1
    assert len(payload["candidates"]) == 1


@pytest.mark.asyncio
async def test_nao_retorna_campos_sensiveis(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000010",
        name="ARROZ PRIVACIDADE",
        current_category="Outros",
        note_seed="privacy-secret",
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    text = response.text.lower()
    for forbidden in (
        "cnpj",
        "cpf",
        "chave_acesso",
        "numero_nota",
        "sefaz",
        "qr_code",
        "xml",
        "payload",
        "privacy-secret",
    ):
        assert forbidden not in text


@pytest.mark.asyncio
async def test_endpoint_nao_escreve_no_banco(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000011",
        name="PRODUTO READ ONLY",
        current_category="Outros",
        note_seed="read-only",
    )

    async with SessionLocal() as db:
        cache_before = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_before = await db.scalar(select(func.count()).select_from(AuditLog))

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    async with SessionLocal() as db:
        product = await db.get(Produto, "7891000000011")
        cache_after = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_after = await db.scalar(select(func.count()).select_from(AuditLog))

    assert product.categoria_confirmada is None
    assert product.categoria == "Outros"
    assert cache_after == cache_before
    assert audit_after == audit_before


@pytest.mark.asyncio
async def test_confianca_fica_entre_zero_e_um(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7891000000012",
        name="PRODUTO CONFIANCA ALTA",
        current_category="Outros",
        note_seed="confidence-high",
        item_category="MERCEARIA",
        item_confidence=Decimal("1.5000"),
    )

    response = await client.get("/api/v1/produtos/categorization/candidates")

    assert response.status_code == 200
    for candidate in response.json()["candidates"]:
        assert 0 <= candidate["confidence"] <= 1
