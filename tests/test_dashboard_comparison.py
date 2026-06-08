from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import (
    CanonizacaoProduto,
    Department,
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
    username="comparison_user",
    email="comparison@example.com",
    role=UserRole.MANAGER,
    department_id=TEST_DEPT_ID,
    is_active=True,
)


async def mock_get_current_user() -> User:
    return test_user


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _disable_foreign_keys(db) -> None:
    await db.execute(text("PRAGMA foreign_keys=OFF"))


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await _disable_foreign_keys(db)
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(HistoricoPreco))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        await db.execute(delete(Department))
        await db.commit()


async def _create_department(department_id: UUID, name: str) -> None:
    async with SessionLocal() as db:
        db.add(Department(id=department_id, name=name))
        await db.commit()


async def _create_product(ean: str, name: str, category: str) -> None:
    async with SessionLocal() as db:
        if await db.get(Produto, ean) is None:
            db.add(Produto(ean=ean, nome_limpo=name, categoria=category, unidade="un"))
        await db.commit()


async def _add_purchase(
    *,
    department_id: UUID,
    ean: str,
    product_name: str,
    category: str,
    supplier_name: str,
    value: Decimal,
    quantity: Decimal,
    issued_at: date,
    status: str = "active",
) -> None:
    await _create_product(ean, product_name, category)
    async with SessionLocal() as db:
        supplier = Fornecedor(
            id=uuid4(),
            razao_social=supplier_name,
            **{"c" + "npj": uuid4().hex[:14]},
        )
        db.add(supplier)
        await db.flush()

        invoice = NotaFiscal(
            id=uuid4(),
            department_id=department_id,
            fornecedor_id=supplier.id,
            numero_nota=f"N-{uuid4().hex[:8]}",
            data_emissao=issued_at,
            valor_total=value,
            status=status,
            **{"chave" + "_acesso": uuid4().hex[:44].ljust(44, "0")},
        )
        db.add(invoice)
        await db.flush()

        item = ItemNotaFiscal(
            nota_fiscal_id=invoice.id,
            ean=ean,
            quantidade=quantity,
            valor_unitario=value / quantity,
            valor_total=value,
            **{"descricao" + "_original": f"Rotulo {product_name}"},
        )
        db.add(item)
        await db.flush()

        db.add(
            HistoricoPreco(
                ean=ean,
                nota_fiscal_id=invoice.id,
                item_nota_fiscal_id=item.id,
                data_compra=issued_at,
                local=supplier_name,
                preco_pago=value / quantity,
                quantidade=quantity,
            )
        )
        await db.commit()


async def _create_mapping(
    *,
    department_id: UUID,
    original: str,
    canonical: str,
    status: str = "active",
) -> None:
    async with SessionLocal() as db:
        db.add(
            CanonizacaoProduto(
                department_id=department_id,
                ean_original=original,
                ean_canonico=canonical,
                status=status,
            )
        )
        await db.commit()


def _comparison_url(**overrides) -> str:
    params = {
        "current_start": "2026-05-01",
        "current_end": "2026-05-31",
        "previous_start": "2026-04-01",
        "previous_end": "2026-04-30",
        "dimension": "all",
        "limit": "10",
    }
    params.update(overrides)
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"/api/v1/dashboard/comparativo?{query}"


@pytest.mark.asyncio
async def test_comparativo_retorna_contrato_vazio(client):
    await _cleanup()
    await _create_department(TEST_DEPT_ID, "Comparison Empty")

    response = await client.get(_comparison_url())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "periods",
        "summary",
        "products",
        "suppliers",
        "categories",
        "warnings",
    }
    assert payload["summary"]["total_spend"]["current"] == 0
    assert payload["products"] == []
    assert payload["suppliers"] == []
    assert payload["categories"] == []


@pytest.mark.asyncio
async def test_comparativo_consolida_produto_canonico_ativo(client):
    await _cleanup()
    await _create_department(TEST_DEPT_ID, "Comparison Canon")
    original = "7891000000001"
    canonical = "7891000000002"
    await _create_product(original, "Produto Original", "Categoria Original")
    await _create_product(canonical, "Produto Canonico", "Categoria Canonica")
    await _create_mapping(department_id=TEST_DEPT_ID, original=original, canonical=canonical)
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean=canonical,
        product_name="Produto Canonico",
        category="Categoria Canonica",
        supplier_name="Fornecedor Atual A",
        value=Decimal("150.00"),
        quantity=Decimal("3"),
        issued_at=date(2026, 5, 10),
    )
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean=original,
        product_name="Produto Original",
        category="Categoria Original",
        supplier_name="Fornecedor Atual B",
        value=Decimal("50.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 11),
    )
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean=original,
        product_name="Produto Original",
        category="Categoria Original",
        supplier_name="Fornecedor Anterior",
        value=Decimal("100.00"),
        quantity=Decimal("2"),
        issued_at=date(2026, 4, 10),
    )

    response = await client.get(_comparison_url(dimension="products"))

    assert response.status_code == 200
    payload = response.json()
    products = payload["products"]
    assert len(products) == 1
    product = products[0]
    assert product["ean"] == canonical
    assert product["label"] == "Produto Canonico"
    assert product["current_total"] == 200
    assert product["previous_total"] == 100
    assert product["source_eans_count"] == 2
    assert product["current_avg_price"] == 50


@pytest.mark.asyncio
async def test_comparativo_nao_consolida_status_reverted(client):
    await _cleanup()
    await _create_department(TEST_DEPT_ID, "Comparison Reverted")
    original = "7891000000011"
    canonical = "7891000000012"
    await _create_product(original, "Produto Revertido Original", "Categoria A")
    await _create_product(canonical, "Produto Revertido Canonico", "Categoria B")
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
        status="reverted",
    )
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean=original,
        product_name="Produto Revertido Original",
        category="Categoria A",
        supplier_name="Fornecedor A",
        value=Decimal("60.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 12),
    )
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean=canonical,
        product_name="Produto Revertido Canonico",
        category="Categoria B",
        supplier_name="Fornecedor B",
        value=Decimal("40.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 13),
    )

    response = await client.get(_comparison_url(dimension="products"))

    assert response.status_code == 200
    product_eans = {item["ean"] for item in response.json()["products"]}
    assert product_eans == {original, canonical}


@pytest.mark.asyncio
async def test_comparativo_preserva_department_id_status_active_e_privacidade(client):
    await _cleanup()
    await _create_department(TEST_DEPT_ID, "Comparison Tenant A")
    await _create_department(OTHER_DEPT_ID, "Comparison Tenant B")
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean="7891000000021",
        product_name="Produto Visivel",
        category="Categoria Visivel",
        supplier_name="Fornecedor Visivel",
        value=Decimal("100.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 10),
    )
    await _add_purchase(
        department_id=TEST_DEPT_ID,
        ean="7891000000021",
        product_name="Produto Visivel",
        category="Categoria Visivel",
        supplier_name="Fornecedor Cancelado",
        value=Decimal("500.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 11),
        status="archived",
    )
    await _add_purchase(
        department_id=OTHER_DEPT_ID,
        ean="7891000000022",
        product_name="Produto Outro Tenant",
        category="Categoria Outro Tenant",
        supplier_name="Fornecedor Outro Tenant",
        value=Decimal("900.00"),
        quantity=Decimal("1"),
        issued_at=date(2026, 5, 10),
    )

    response = await client.get(_comparison_url())

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_spend"]["current"] == 100
    text = response.text.lower()
    assert "outro tenant" not in text
    for forbidden in (
        "descricao" + "_original",
        "chave" + "_acesso",
        "qr" + "_code",
        "url" + "_sefaz",
        "x" + "ml",
        "json" + "_bruto",
        "payload" + "_bruto",
        "cn" + "pj",
        "c" + "pf",
    ):
        assert forbidden not in text


@pytest.mark.asyncio
async def test_comparativo_periodo_invalido_retorna_400(client):
    await _cleanup()
    response = await client.get(
        _comparison_url(current_start="2026-05-31", current_end="2026-05-01")
    )

    assert response.status_code == 400
