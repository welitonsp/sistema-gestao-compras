from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.compras import Department, Fornecedor, ItemNotaFiscal, NotaFiscal, Produto, User, UserRole
from backend.services.catalog_healer import CatalogHealerService


async def _seed_healer_product(
    *,
    department_id,
    ean: str,
    name: str,
    category: str,
    brand: str,
    note_suffix: str,
    status: str = "active",
) -> None:
    async with SessionLocal() as db:
        supplier = Fornecedor(
            cnpj=(note_suffix[-14:] + "8" * 14)[:14],
            razao_social=f"H10E Fornecedor {note_suffix}",
        )
        product = Produto(
            ean=ean,
            nome_limpo=name,
            categoria=category,
            marca=brand,
            unidade="un",
        )
        db.add_all([supplier, product])
        await db.flush()

        invoice = NotaFiscal(
            fornecedor_id=supplier.id,
            department_id=department_id,
            numero_nota=f"H10E-{note_suffix}",
            chave_acesso=f"H10E-{note_suffix}-{uuid4().hex}",
            data_emissao=date(2026, 6, 9),
            valor_total=Decimal("10.00"),
            status=status,
        )
        db.add(invoice)
        await db.flush()

        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=invoice.id,
                ean=ean,
                descricao_original=f"ITEM {name}",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("10.00"),
                valor_total=Decimal("10.00"),
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_catalog_healer_suggestions_respeitam_department_id():
    dept_a = uuid4()
    dept_b = uuid4()
    async with SessionLocal() as db:
        db.add_all(
            [
                Department(id=dept_a, name=f"H10E Dept A {dept_a}", is_active=True),
                Department(id=dept_b, name=f"H10E Dept B {dept_b}", is_active=True),
            ]
        )
        await db.commit()

    await _seed_healer_product(
        department_id=dept_a,
        ean=f"H10E-A1-{dept_a.hex[:8]}",
        name="H10E ARROZ TESTE A",
        category="ALIMENTOS",
        brand="MARCA A",
        note_suffix=f"A1-{dept_a.hex[:8]}",
    )
    await _seed_healer_product(
        department_id=dept_a,
        ean=f"H10E-A2-{dept_a.hex[:8]}",
        name="H10E ARROZ TESTE B",
        category="MERCEARIA",
        brand="MARCA A",
        note_suffix=f"A2-{dept_a.hex[:8]}",
    )
    await _seed_healer_product(
        department_id=dept_b,
        ean=f"H10E-B1-{dept_b.hex[:8]}",
        name="H10E FEIJAO TESTE A",
        category="ALIMENTOS",
        brand="MARCA B",
        note_suffix=f"B1-{dept_b.hex[:8]}",
    )
    await _seed_healer_product(
        department_id=dept_b,
        ean=f"H10E-B2-{dept_b.hex[:8]}",
        name="H10E FEIJAO TESTE B",
        category="MERCEARIA",
        brand="MARCA B",
        note_suffix=f"B2-{dept_b.hex[:8]}",
    )

    async with SessionLocal() as db:
        service = CatalogHealerService(db)
        scoped = await service.get_maintenance_suggestions(department_id=dept_a)
        global_suggestions = await service.get_maintenance_suggestions()

    scoped_eans = {
        suggestion["primary"]["ean"]
        for suggestion in scoped
    } | {
        suggestion["suggestion"]["ean"]
        for suggestion in scoped
    }
    global_eans = {
        suggestion["primary"]["ean"]
        for suggestion in global_suggestions
    } | {
        suggestion["suggestion"]["ean"]
        for suggestion in global_suggestions
    }

    assert f"H10E-A1-{dept_a.hex[:8]}" in scoped_eans
    assert f"H10E-A2-{dept_a.hex[:8]}" in scoped_eans
    assert f"H10E-B1-{dept_b.hex[:8]}" not in scoped_eans
    assert f"H10E-B2-{dept_b.hex[:8]}" not in scoped_eans
    assert f"H10E-B1-{dept_b.hex[:8]}" in global_eans
    assert f"H10E-B2-{dept_b.hex[:8]}" in global_eans


@pytest.mark.asyncio
async def test_catalog_healer_endpoint_bloqueia_manager_sem_departamento():
    async def mock_user() -> User:
        return User(
            id=uuid4(),
            username="h10e_manager_sem_departamento",
            email="h10e-manager@example.com",
            role=UserRole.MANAGER,
            department_id=None,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = mock_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/produtos/maintenance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Usuario sem departamento nao pode consultar manutencao do catalogo."
