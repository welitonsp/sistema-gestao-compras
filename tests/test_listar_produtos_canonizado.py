from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import CanonizacaoProduto, Department, Produto, User, UserRole


TEST_DEPT_ID = uuid4()
OTHER_DEPT_ID = uuid4()

current_user = User(
    id=uuid4(),
    username="catalog_canon_user",
    email="catalog-canon@example.com",
    role=UserRole.MANAGER,
    department_id=TEST_DEPT_ID,
    is_active=True,
)


async def mock_get_current_user() -> User:
    return current_user


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(Produto))
        await db.execute(delete(Department))
        await db.commit()


async def _create_department(department_id, name: str) -> None:
    async with SessionLocal() as db:
        db.add(Department(id=department_id, name=name))
        await db.commit()


async def _create_products(*eans: str) -> None:
    async with SessionLocal() as db:
        for ean in eans:
            db.add(
                Produto(
                    ean=ean,
                    nome_limpo=f"Produto {ean}",
                    marca="Marca Teste",
                    categoria="Categoria Teste",
                    unidade="un",
                )
            )
        await db.commit()


async def _create_mapping(
    *,
    department_id,
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
                reason="mesmo produto",
                confidence_score=Decimal("0.9500"),
            )
        )
        await db.commit()


def _set_user(*, department_id=TEST_DEPT_ID, role=UserRole.MANAGER) -> None:
    current_user.id = uuid4()
    current_user.username = f"catalog_canon_{uuid4().hex[:8]}"
    current_user.email = f"{current_user.username}@example.com"
    current_user.role = role
    current_user.department_id = department_id


def _by_ean(items):
    return {item["ean"]: item for item in items}


@pytest.mark.asyncio
async def test_listar_produtos_sem_mapeamento_retorna_canonizacao_null(client):
    await _cleanup()
    _set_user()
    await _create_department(TEST_DEPT_ID, "Catalog Canon Sem Mapa")
    await _create_products("7899100000001")

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    product = _by_ean(response.json())["7899100000001"]
    assert product["canonizacao"] is None


@pytest.mark.asyncio
async def test_listar_produtos_original_mapeado_retorna_metadados_e_permanece_listado(client):
    await _cleanup()
    _set_user()
    original = "7899100000011"
    canonical = "7899100000012"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Mesmo Dept")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    products = _by_ean(response.json())
    assert original in products
    assert canonical in products
    assert products[original]["canonizacao"] == {
        "status": "active",
        "ean_original": original,
        "ean_canonico": canonical,
        "reason": "mesmo produto",
        "confidence_score": 0.95,
    }


@pytest.mark.asyncio
async def test_listar_produtos_canonico_aparece_como_produto_normal(client):
    await _cleanup()
    _set_user()
    original = "7899100000021"
    canonical = "7899100000022"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Produto Canonico")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    canonical_product = _by_ean(response.json())[canonical]
    assert canonical_product["ean"] == canonical
    assert canonical_product["canonizacao"] is None


@pytest.mark.asyncio
async def test_listar_produtos_mapeamento_de_outro_tenant_nao_aparece(client):
    await _cleanup()
    _set_user(department_id=OTHER_DEPT_ID)
    original = "7899100000031"
    canonical = "7899100000032"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Tenant A")
    await _create_department(OTHER_DEPT_ID, "Catalog Canon Tenant B")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    assert _by_ean(response.json())[original]["canonizacao"] is None


@pytest.mark.asyncio
async def test_listar_produtos_admin_global_sem_department_id_nao_aplica_mapeamento(client):
    await _cleanup()
    _set_user(department_id=None, role=UserRole.ADMIN)
    original = "7899100000041"
    canonical = "7899100000042"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Global")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    assert _by_ean(response.json())[original]["canonizacao"] is None


@pytest.mark.asyncio
async def test_listar_produtos_busca_por_ean_original_mapeado_encontra_produto(client):
    await _cleanup()
    _set_user()
    original = "7899100000051"
    canonical = "7899100000052"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Busca EAN")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get(f"/api/v1/produtos?search={original}")

    assert response.status_code == 200
    payload = response.json()
    assert [product["ean"] for product in payload] == [original]
    assert payload[0]["canonizacao"]["ean_original"] == original
    assert payload[0]["canonizacao"]["ean_canonico"] == canonical


@pytest.mark.asyncio
async def test_listar_produtos_busca_por_nome_continua_funcionando(client):
    await _cleanup()
    _set_user()
    await _create_department(TEST_DEPT_ID, "Catalog Canon Busca Nome")
    await _create_products("7899100000061", "7899100000062")

    response = await client.get("/api/v1/produtos?search=0000061")

    assert response.status_code == 200
    assert [product["ean"] for product in response.json()] == ["7899100000061"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["inactive", "reverted"])
async def test_listar_produtos_status_nao_active_retorna_canonizacao_null(client, status):
    await _cleanup()
    _set_user()
    original = "7899100000071"
    canonical = "7899100000072"
    await _create_department(TEST_DEPT_ID, f"Catalog Canon {status}")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
        status=status,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    assert _by_ean(response.json())[original]["canonizacao"] is None


@pytest.mark.asyncio
async def test_listar_produtos_response_nao_contem_campos_sensiveis(client):
    await _cleanup()
    _set_user()
    original = "7899100000081"
    canonical = "7899100000082"
    await _create_department(TEST_DEPT_ID, "Catalog Canon Seguranca")
    await _create_products(original, canonical)
    await _create_mapping(
        department_id=TEST_DEPT_ID,
        original=original,
        canonical=canonical,
    )

    response = await client.get("/api/v1/produtos")

    assert response.status_code == 200
    body = response.text.lower()
    for forbidden in (
        "c" + "pf",
        "c" + "npj",
        "chave" + "_acesso",
        "url_" + "sefaz",
        "qr_" + "code",
        "x" + "ml",
        "json_" + "bruto",
        "payload_" + "bruto",
    ):
        assert forbidden not in body
