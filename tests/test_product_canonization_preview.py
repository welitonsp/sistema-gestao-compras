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


TEST_DEPT_ID = uuid4()
OTHER_DEPT_ID = uuid4()

test_user = User(
    id=uuid4(),
    username="canonization_preview_user",
    email="canonization-preview@example.com",
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
    category: str | None = "MERCEARIA",
    department_id: UUID | None = TEST_DEPT_ID,
    status: str = "active",
    description: str | None = None,
) -> None:
    async with SessionLocal() as db:
        product = await db.get(Produto, ean)
        if product is None:
            product = Produto(
                ean=ean,
                nome_limpo=name,
                categoria=category,
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
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_endpoint_retorna_200_e_grupos_esperados(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000001",
        name="ARROZ TIO JOAO TIPO 1 5KG",
        note_seed="canon-a",
    )
    await _add_product_purchase(
        ean="7892000000002",
        name="Arroz Tio Joao Tp1 5 KG",
        note_seed="canon-b",
    )

    response = await client.get("/api/v1/produtos/canonization/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["threshold"] == 0.90
    assert payload["limit"] == 100
    assert payload["total_groups"] == 1
    assert payload["groups"] == [
        {
            "primary": {
                "ean": "7892000000001",
                "name": "ARROZ TIO JOAO TIPO 1 5KG",
                "category": "MERCEARIA",
            },
            "matches": [
                {
                    "ean": "7892000000002",
                    "name": "Arroz Tio Joao Tp1 5 KG",
                    "category": "MERCEARIA",
                    "similarity": 1.0,
                    "reason": "Nome normalizado similar",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_endpoint_nao_retorna_candidatos_de_outro_department_id(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000003",
        name="LEITE UHT INTEGRAL 1L",
        note_seed="dept-a",
    )
    await _add_product_purchase(
        ean="7892000000004",
        name="LEITE UHT INTEGRAL 1 LT",
        note_seed="dept-b",
        department_id=OTHER_DEPT_ID,
    )

    response = await client.get("/api/v1/produtos/canonization/candidates")

    assert response.status_code == 200
    assert response.json()["groups"] == []


@pytest.mark.asyncio
async def test_endpoint_usuario_sem_department_id_nao_faz_matching_global(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000013",
        name="LEITE UHT INTEGRAL 1L",
        note_seed="no-dept-a",
    )
    await _add_product_purchase(
        ean="7892000000014",
        name="LEITE UHT INTEGRAL 1 LT",
        note_seed="no-dept-b",
    )

    previous_department_id = test_user.department_id
    test_user.department_id = None
    try:
        response = await client.get("/api/v1/produtos/canonization/candidates")
    finally:
        test_user.department_id = previous_department_id

    assert response.status_code == 200
    assert response.json()["groups"] == []


@pytest.mark.asyncio
async def test_endpoint_limit_threshold_e_category_respeitam_bounds(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000005",
        name="ARROZ A 5KG",
        note_seed="bounds-a",
        category="MERCEARIA",
    )
    await _add_product_purchase(
        ean="7892000000006",
        name="ARROZ A 5 KG",
        note_seed="bounds-b",
        category="MERCEARIA",
    )
    await _add_product_purchase(
        ean="7892000000007",
        name="LEITE UHT INTEGRAL 1L",
        note_seed="bounds-c",
        category="FRIOS",
    )
    await _add_product_purchase(
        ean="7892000000008",
        name="LEITE UHT INTEGRAL 1 LT",
        note_seed="bounds-d",
        category="FRIOS",
    )

    response = await client.get(
        "/api/v1/produtos/canonization/candidates"
        "?limit=1&threshold=0.95&category=MERCEARIA"
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["threshold"] == 0.95
    assert payload["limit"] == 1
    assert payload["total_groups"] == 1
    assert len(payload["groups"]) == 1
    assert payload["groups"][0]["primary"]["category"] == "MERCEARIA"

    invalid_limit = await client.get(
        "/api/v1/produtos/canonization/candidates?limit=101"
    )
    invalid_threshold = await client.get(
        "/api/v1/produtos/canonization/candidates?threshold=0.5"
    )

    assert invalid_limit.status_code == 422
    assert invalid_threshold.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_nao_realiza_writes(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000009",
        name="CAFE PCT 500G",
        note_seed="read-only-a",
    )
    await _add_product_purchase(
        ean="7892000000010",
        name="CAFE pacote 500 gr",
        note_seed="read-only-b",
    )

    async with SessionLocal() as db:
        cache_before = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_before = await db.scalar(select(func.count()).select_from(AuditLog))
        products_before = await db.scalar(select(func.count()).select_from(Produto))
        items_before = await db.scalar(select(func.count()).select_from(ItemNotaFiscal))

    response = await client.get("/api/v1/produtos/canonization/candidates")

    assert response.status_code == 200
    async with SessionLocal() as db:
        cache_after = await db.scalar(select(func.count()).select_from(ClassificacaoCache))
        audit_after = await db.scalar(select(func.count()).select_from(AuditLog))
        products_after = await db.scalar(select(func.count()).select_from(Produto))
        items_after = await db.scalar(select(func.count()).select_from(ItemNotaFiscal))

    assert cache_after == cache_before
    assert audit_after == audit_before
    assert products_after == products_before
    assert items_after == items_before


@pytest.mark.asyncio
async def test_endpoint_nao_retorna_campos_sensiveis(client):
    await _cleanup()
    await _add_product_purchase(
        ean="7892000000011",
        name="BISCOITO CX C/10 UND",
        note_seed="privacy-secret-a",
        description="Descricao fiscal privacy-secret-a",
    )
    await _add_product_purchase(
        ean="7892000000012",
        name="BISCOITO caixa com 10 unidades",
        note_seed="privacy-secret-b",
        description="Descricao fiscal privacy-secret-b",
    )

    response = await client.get("/api/v1/produtos/canonization/candidates")

    assert response.status_code == 200
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
        "descricao fiscal",
    ):
        assert forbidden not in text
