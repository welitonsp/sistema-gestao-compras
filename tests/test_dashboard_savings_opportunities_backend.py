from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import (
    Fornecedor,
    HistoricoPreco,
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
    username="savings_user",
    email="savings@example.com",
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
        await db.execute(delete(HistoricoPreco))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        await db.commit()


def _key(seed: str) -> str:
    return (seed + ("0" * 44))[:44]


async def _add_purchase(
    *,
    ean: str,
    price: Decimal,
    quantity: Decimal,
    purchase_date: date,
    note_seed: str,
    product_name: str = "Produto Teste",
    category: str = "Categoria Teste",
    department_id: UUID | None = TEST_DEPT_ID,
    status: str = "active",
) -> None:
    async with SessionLocal() as db:
        produto = await db.get(Produto, ean)
        if produto is None:
            produto = Produto(ean=ean, nome_limpo=product_name, categoria=category)
            db.add(produto)

        fornecedor = Fornecedor(
            id=uuid4(),
            razao_social=f"Fornecedor {note_seed}",
            cnpj=(note_seed[-14:] + "9" * 14)[:14],
        )
        db.add(fornecedor)
        await db.flush()

        total = price * quantity
        nota = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota=f"NOTA-{note_seed}",
            chave_acesso=_key(f"secret-{note_seed}"),
            data_emissao=purchase_date,
            valor_total=total,
            status=status,
            department_id=department_id,
        )
        db.add(nota)
        await db.flush()

        item = ItemNotaFiscal(
            nota_fiscal_id=nota.id,
            ean=ean,
            descricao_original=f"Item {note_seed}",
            quantidade=quantity,
            valor_unitario=price,
            valor_total=total,
        )
        db.add(item)
        await db.flush()

        db.add(
            HistoricoPreco(
                ean=ean,
                nota_fiscal_id=nota.id,
                item_nota_fiscal_id=item.id,
                data_compra=purchase_date,
                local=f"Fornecedor {note_seed}",
                preco_pago=price,
                quantidade=quantity,
            )
        )
        await db.commit()


async def _seed_price_gap(
    ean: str = "7890000000001",
    *,
    department_id: UUID | None = TEST_DEPT_ID,
    quantity: Decimal = Decimal("2"),
) -> None:
    today = date.today()
    await _add_purchase(
        ean=ean,
        price=Decimal("10.00"),
        quantity=Decimal("1"),
        purchase_date=today - timedelta(days=10),
        note_seed=f"{ean}-low",
        department_id=department_id,
    )
    await _add_purchase(
        ean=ean,
        price=Decimal("20.00"),
        quantity=quantity,
        purchase_date=today,
        note_seed=f"{ean}-high",
        department_id=department_id,
    )


def _money(value: Any) -> Decimal:
    return Decimal(str(value))


def _assert_no_negative_money(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if "saving" in key or "price" in key:
                assert _money(value) >= 0
            else:
                _assert_no_negative_money(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_negative_money(item)


@pytest.mark.asyncio
async def test_endpoint_returns_200_and_summary_payload(client):
    await _cleanup()

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "period_start",
        "period_end",
        "total_estimated_savings",
        "opportunity_count",
        "high_confidence_count",
        "medium_confidence_count",
        "low_confidence_count",
        "insufficient_data_count",
        "opportunities",
    }
    assert payload["opportunities"] == []


@pytest.mark.asyncio
async def test_sem_dados_suficientes_nao_inventa_economia(client):
    await _cleanup()
    await _add_purchase(
        ean="7890000000002",
        price=Decimal("20.00"),
        quantity=Decimal("2"),
        purchase_date=date.today(),
        note_seed="single-observation",
    )

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    payload = response.json()
    assert payload["opportunities"] == []
    assert _money(payload["total_estimated_savings"]) == Decimal("0")


@pytest.mark.asyncio
async def test_price_gap_valido_por_ean(client):
    await _cleanup()
    await _seed_price_gap()

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    opportunity = response.json()["opportunities"][0]
    assert opportunity["type"] == "price_gap"
    assert _money(opportunity["estimated_savings"]) > 0
    assert 0 <= opportunity["score"]["total_score"] <= 100
    assert opportunity["confidence"] != "insufficient_data"


@pytest.mark.asyncio
async def test_item_sem_ean_valido_nao_gera_oportunidade_financeira(client):
    await _cleanup()
    await _add_purchase(
        ean="SEM-EAN",
        price=Decimal("10.00"),
        quantity=Decimal("1"),
        purchase_date=date.today() - timedelta(days=1),
        note_seed="internal-low",
    )
    await _add_purchase(
        ean="SEM-EAN",
        price=Decimal("25.00"),
        quantity=Decimal("2"),
        purchase_date=date.today(),
        note_seed="internal-high",
    )

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    assert response.json()["opportunities"] == []


@pytest.mark.asyncio
async def test_resposta_nao_contem_campos_sensiveis(client):
    await _cleanup()
    await _seed_price_gap("7890000000003")

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

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
        "secret",
    ):
        assert forbidden not in text


@pytest.mark.asyncio
async def test_respeita_status_active(client):
    await _cleanup()
    today = date.today()
    await _add_purchase(
        ean="7890000000004",
        price=Decimal("10.00"),
        quantity=Decimal("1"),
        purchase_date=today - timedelta(days=1),
        note_seed="active-low",
        status="active",
    )
    await _add_purchase(
        ean="7890000000004",
        price=Decimal("30.00"),
        quantity=Decimal("1"),
        purchase_date=today,
        note_seed="inactive-high",
        status="inactive",
    )

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    assert response.json()["opportunities"] == []


@pytest.mark.asyncio
async def test_respeita_department_isolation(client):
    await _cleanup()
    await _seed_price_gap("7890000000005", department_id=OTHER_DEPT_ID)

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    assert response.json()["opportunities"] == []


@pytest.mark.asyncio
async def test_start_date_e_end_date_filtram_por_data_fiscal(client):
    await _cleanup()
    today = date.today()
    await _add_purchase(
        ean="7890000000006",
        price=Decimal("10.00"),
        quantity=Decimal("1"),
        purchase_date=today - timedelta(days=30),
        note_seed="old-low",
    )
    await _add_purchase(
        ean="7890000000006",
        price=Decimal("20.00"),
        quantity=Decimal("2"),
        purchase_date=today,
        note_seed="today-high",
    )

    filtered = await client.get(
        f"/api/v1/dashboard/oportunidades/economia?start_date={today.isoformat()}"
    )
    full_window = await client.get(
        "/api/v1/dashboard/oportunidades/economia"
    )

    assert filtered.status_code == 200
    assert filtered.json()["opportunities"] == []
    assert full_window.status_code == 200
    assert len(full_window.json()["opportunities"]) == 1


@pytest.mark.asyncio
async def test_limit_limita_quantidade_de_opportunities(client):
    await _cleanup()
    await _seed_price_gap("7890000000007")
    await _seed_price_gap("7890000000008", quantity=Decimal("3"))

    response = await client.get("/api/v1/dashboard/oportunidades/economia?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["opportunities"]) == 1
    assert payload["opportunity_count"] == 1


@pytest.mark.asyncio
async def test_nao_ha_valores_monetarios_negativos_na_resposta(client):
    await _cleanup()
    await _seed_price_gap("7890000000009")

    response = await client.get("/api/v1/dashboard/oportunidades/economia")

    assert response.status_code == 200
    _assert_no_negative_money(response.json())


@pytest.mark.asyncio
async def test_end_date_anterior_a_start_date_rejeitado(client):
    await _cleanup()

    response = await client.get(
        "/api/v1/dashboard/oportunidades/economia"
        "?start_date=2026-05-02&end_date=2026-05-01"
    )

    assert response.status_code == 400
