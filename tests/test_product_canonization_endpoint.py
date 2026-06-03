from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import (
    AuditLog,
    CanonizacaoProduto,
    Department,
    Fornecedor,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
    UserRole,
)


async def _disable_foreign_keys(db) -> None:
    await db.execute(text("PRAGMA foreign_keys=OFF"))


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await _disable_foreign_keys(db)
        await db.execute(delete(AuditLog))
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(User))
        await db.execute(delete(Produto))
        await db.execute(delete(Department))
        await db.commit()


async def _create_department(name: str | None = None) -> Department:
    async with SessionLocal() as db:
        department = Department(id=uuid4(), name=name or f"Dept {uuid4()}")
        db.add(department)
        await db.commit()
        return department


async def _create_user(username: str, role: str, department_id: UUID | None = None) -> str:
    async with SessionLocal() as db:
        db.add(
            User(
                username=username,
                email=f"{username}@test.local",
                hashed_password="unused",
                role=role,
                department_id=department_id,
                is_active=True,
            )
        )
        await db.commit()
    return create_access_token({"sub": username, "role": role})


async def _seed_products(*eans: str) -> None:
    async with SessionLocal() as db:
        for ean in eans:
            db.add(
                Produto(
                    ean=ean,
                    nome_limpo=f"Produto {ean}",
                    marca="TESTE",
                    categoria="MERCEARIA",
                    unidade="un",
                )
            )
        await db.commit()


async def _create_item(department_id: UUID, ean: str) -> None:
    async with SessionLocal() as db:
        supplier = Fornecedor(
            id=uuid4(),
            cnpj="98765432000199",
            razao_social="Fornecedor Endpoint",
        )
        db.add(supplier)
        await db.flush()
        invoice = NotaFiscal(
            id=uuid4(),
            department_id=department_id,
            fornecedor_id=supplier.id,
            numero_nota="END-1",
            chave_acesso="2" * 44,
            data_emissao=date(2026, 5, 26),
            valor_total=Decimal("12.00"),
        )
        db.add(invoice)
        await db.flush()
        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=invoice.id,
                ean=ean,
                descricao_original="Descricao fiscal sensivel preservada",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("12.00"),
                valor_total=Decimal("12.00"),
            )
        )
        await db.commit()


async def _post_confirm(token: str, payload: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/v1/produtos/canonization/confirm",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )


def _payload(department_id: UUID | None, **overrides):
    payload = {
        "ean_canonico": "7895000000002",
        "eans_originais": ["7895000000001"],
        "department_id": str(department_id) if department_id else None,
        "reason": "confirmacao manual",
        "confirmed": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_endpoint_cria_mapeamento_valido_com_confirmed_true():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_manager_ok", UserRole.MANAGER, department.id)

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 201
    body = response.json()
    assert body["created_count"] == 1
    assert body["department_id"] == str(department.id)
    assert body["created_mappings"] == [
        {
            "ean_original": "7895000000001",
            "ean_canonico": "7895000000002",
            "status": "active",
        }
    ]


@pytest.mark.asyncio
async def test_endpoint_bloqueia_confirmed_false_ou_ausente():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_manager_confirmed", UserRole.MANAGER, department.id)

    false_response = await _post_confirm(token, _payload(department.id, confirmed=False))
    missing_payload = _payload(department.id)
    missing_payload.pop("confirmed")
    missing_response = await _post_confirm(token, missing_payload)

    assert false_response.status_code == 400
    assert missing_response.status_code == 400


@pytest.mark.asyncio
async def test_endpoint_bloqueia_operator():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_operator", UserRole.OPERATOR, department.id)

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_endpoint_manager_nao_consegue_usar_department_id_alheio():
    await _cleanup()
    own_department = await _create_department("Dept Proprio")
    other_department = await _create_department("Dept Alheio")
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_manager_other", UserRole.MANAGER, own_department.id)

    response = await _post_confirm(token, _payload(other_department.id))

    assert response.status_code == 403
    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(CanonizacaoProduto))
    assert count == 0


@pytest.mark.asyncio
async def test_endpoint_admin_consegue_especificar_department_id_valido():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_admin", UserRole.ADMIN)

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 201
    assert response.json()["department_id"] == str(department.id)


@pytest.mark.asyncio
async def test_endpoint_produto_inexistente_retorna_erro_adequado():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000002")
    token = await _create_user("canon_manager_missing_product", UserRole.MANAGER, department.id)

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 404
    assert "Produto" in response.json()["detail"]


@pytest.mark.asyncio
async def test_endpoint_conflito_retorna_409():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    token = await _create_user("canon_manager_conflict", UserRole.MANAGER, department.id)
    first = await _post_confirm(token, _payload(department.id))

    second = await _post_confirm(token, _payload(department.id))

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_endpoint_resposta_nao_contem_dados_fiscais_sensiveis():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    await _create_item(department.id, "7895000000001")
    token = await _create_user("canon_manager_privacy", UserRole.MANAGER, department.id)

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 201
    text = response.text.lower()
    for forbidden in (
        "descricao_original",
        "descricao fiscal",
        "chave_acesso",
        "qr_code",
        "url_sefaz",
        "xml",
        "json_bruto",
        "payload_bruto",
        "cnpj",
        "cpf",
    ):
        assert forbidden not in text


@pytest.mark.asyncio
async def test_endpoint_nao_expoe_outros_metodos_mutantes_de_canonizacao():
    unsafe_routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if path.startswith("/api/v1/produtos/canonization") and path != "/api/v1/produtos/canonization/confirm":
            unsafe_routes.extend(sorted(methods & {"POST", "PATCH", "PUT", "DELETE"}))

    assert unsafe_routes == []


@pytest.mark.asyncio
async def test_endpoint_nao_altera_produto_ou_item_nota_fiscal():
    await _cleanup()
    department = await _create_department()
    await _seed_products("7895000000001", "7895000000002")
    await _create_item(department.id, "7895000000001")
    token = await _create_user("canon_manager_preserve", UserRole.MANAGER, department.id)

    async with SessionLocal() as db:
        product = await db.get(Produto, "7895000000001")
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7895000000001"))
        product_before = (product.nome_limpo, product.marca, product.categoria, product.unidade)
        item_before = (
            item.ean,
            item.descricao_original,
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    response = await _post_confirm(token, _payload(department.id))

    assert response.status_code == 201
    async with SessionLocal() as db:
        product = await db.get(Produto, "7895000000001")
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7895000000001"))
        product_after = (product.nome_limpo, product.marca, product.categoria, product.unidade)
        item_after = (
            item.ean,
            item.descricao_original,
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    assert product_after == product_before
    assert item_after == item_before
