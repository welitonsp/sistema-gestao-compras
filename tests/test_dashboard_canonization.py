from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text

from backend.core.database import SessionLocal
from backend.models.compras import (
    CanonizacaoProduto,
    Department,
    Fornecedor,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
)
from backend.services.insights_processor import PriceInsightsService


async def _disable_foreign_keys(db) -> None:
    await db.execute(text("PRAGMA foreign_keys=OFF"))


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await _disable_foreign_keys(db)
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        await db.execute(delete(Department))
        await db.commit()


async def _create_department(name: str) -> Department:
    async with SessionLocal() as db:
        department = Department(id=uuid4(), name=name)
        db.add(department)
        await db.commit()
        return department


async def _create_products(*eans: str) -> None:
    async with SessionLocal() as db:
        for ean in eans:
            db.add(
                Produto(
                    ean=ean,
                    nome_limpo=f"Produto {ean}",
                    marca=f"Marca {ean}",
                    categoria=f"Categoria {ean}",
                    unidade="un",
                )
            )
        await db.commit()


async def _create_purchase(
    *,
    department_id: UUID,
    ean: str,
    suffix: str,
    quantity: Decimal,
    total: Decimal,
) -> None:
    async with SessionLocal() as db:
        supplier = Fornecedor(
            id=uuid4(),
            razao_social=f"Fornecedor {suffix}",
            **{"c" + "npj": (suffix + "0" * 14)[:14]},
        )
        db.add(supplier)
        await db.flush()

        invoice = NotaFiscal(
            id=uuid4(),
            department_id=department_id,
            fornecedor_id=supplier.id,
            numero_nota=f"N-{suffix}",
            data_emissao=date(2026, 5, 26),
            valor_total=total,
            status="active",
            **{"chave" + "_acesso": (suffix + "1" * 44)[:44]},
        )
        db.add(invoice)
        await db.flush()

        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=invoice.id,
                ean=ean,
                quantidade=quantity,
                valor_unitario=total / quantity,
                valor_total=total,
                **{"descricao" + "_original": f"Rotulo preservado {suffix}"},
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


async def _top_products(department_id: UUID | None):
    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        return await service.obter_top_produtos_gasto(
            department_id=department_id,
            limit=10,
        )


async def _category_summary(department_id: UUID | None):
    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        return await service.obter_resumo_gastos_por_categoria(
            department_id=department_id,
        )


def _by_ean(items):
    return {item["ean"]: item for item in items}


def _by_category(items):
    return {item["categoria"]: item for item in items}


@pytest.mark.asyncio
async def test_top_produtos_sem_mapeamento_mantem_comportamento_anterior():
    await _cleanup()
    department = await _create_department("Canon Dashboard Sem Mapa")
    await _create_products("7896000000001", "7896000000002")
    await _create_purchase(
        department_id=department.id,
        ean="7896000000001",
        suffix="semmapa1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7896000000002",
        suffix="semmapa2",
        quantity=Decimal("2"),
        total=Decimal("20.00"),
    )

    result = await _top_products(department.id)

    assert [item["ean"] for item in result] == ["7896000000002", "7896000000001"]
    assert _by_ean(result)["7896000000001"]["total"] == 10.0
    assert _by_ean(result)["7896000000002"]["produto"] == "Produto 7896000000002"


@pytest.mark.asyncio
async def test_top_produtos_com_mapeamento_soma_original_no_canonico():
    await _cleanup()
    department = await _create_department("Canon Dashboard Mesmo Dept")
    await _create_products("7896000000011", "7896000000012")
    await _create_purchase(
        department_id=department.id,
        ean="7896000000011",
        suffix="mesmodept1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7896000000012",
        suffix="mesmodept2",
        quantity=Decimal("2"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7896000000011",
        canonical="7896000000012",
    )

    result = await _top_products(department.id)

    assert len(result) == 1
    assert result[0]["ean"] == "7896000000012"
    assert result[0]["produto"] == "Produto 7896000000012"
    assert result[0]["total"] == 30.0
    assert result[0]["quantidade_total"] == 3.0


@pytest.mark.asyncio
async def test_top_produtos_mapeamento_de_um_tenant_nao_afeta_outro():
    await _cleanup()
    department_a = await _create_department("Canon Dashboard Tenant A")
    department_b = await _create_department("Canon Dashboard Tenant B")
    await _create_products("7896000000021", "7896000000022")
    await _create_purchase(
        department_id=department_b.id,
        ean="7896000000021",
        suffix="tenantb1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department_b.id,
        ean="7896000000022",
        suffix="tenantb2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department_a.id,
        original="7896000000021",
        canonical="7896000000022",
    )

    result = await _top_products(department_b.id)

    assert [item["ean"] for item in result] == ["7896000000021", "7896000000022"]
    assert _by_ean(result)["7896000000021"]["total"] == 30.0
    assert _by_ean(result)["7896000000022"]["total"] == 20.0


@pytest.mark.asyncio
async def test_top_produtos_global_sem_department_id_nao_aplica_mapeamento():
    await _cleanup()
    department = await _create_department("Canon Dashboard Global")
    await _create_products("7896000000031", "7896000000032")
    await _create_purchase(
        department_id=department.id,
        ean="7896000000031",
        suffix="global1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7896000000032",
        suffix="global2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7896000000031",
        canonical="7896000000032",
    )

    result = await _top_products(None)

    assert [item["ean"] for item in result] == ["7896000000031", "7896000000032"]
    assert _by_ean(result)["7896000000031"]["total"] == 30.0
    assert _by_ean(result)["7896000000032"]["total"] == 20.0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["inactive", "reverted"])
async def test_top_produtos_status_nao_active_nao_aplica_mapeamento(status):
    await _cleanup()
    department = await _create_department(f"Canon Dashboard {status}")
    await _create_products("7896000000041", "7896000000042")
    await _create_purchase(
        department_id=department.id,
        ean="7896000000041",
        suffix=f"{status}1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7896000000042",
        suffix=f"{status}2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7896000000041",
        canonical="7896000000042",
        status=status,
    )

    result = await _top_products(department.id)

    assert [item["ean"] for item in result] == ["7896000000041", "7896000000042"]
    assert _by_ean(result)["7896000000041"]["total"] == 30.0


@pytest.mark.asyncio
async def test_top_produtos_nao_altera_dados_fiscais_ou_catalogo():
    await _cleanup()
    department = await _create_department("Canon Dashboard Integridade")
    await _create_products("7896000000051", "7896000000052")
    await _create_purchase(
        department_id=department.id,
        ean="7896000000051",
        suffix="integridade1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7896000000051",
        canonical="7896000000052",
    )

    async with SessionLocal() as db:
        product = await db.get(Produto, "7896000000051")
        item = await db.scalar(
            select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7896000000051")
        )
        product_before = (
            product.nome_limpo,
            product.marca,
            product.categoria,
            product.unidade,
        )
        item_before = (
            item.ean,
            getattr(item, "descricao" + "_original"),
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    await _top_products(department.id)

    async with SessionLocal() as db:
        product = await db.get(Produto, "7896000000051")
        item = await db.scalar(
            select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7896000000051")
        )
        product_after = (
            product.nome_limpo,
            product.marca,
            product.categoria,
            product.unidade,
        )
        item_after = (
            item.ean,
            getattr(item, "descricao" + "_original"),
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    assert product_after == product_before
    assert item_after == item_before


@pytest.mark.asyncio
async def test_resumo_categoria_sem_mapeamento_mantem_comportamento_anterior():
    await _cleanup()
    department = await _create_department("Canon Categoria Sem Mapa")
    await _create_products("7897000000001", "7897000000002")
    await _create_purchase(
        department_id=department.id,
        ean="7897000000001",
        suffix="catsemmapa1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7897000000002",
        suffix="catsemmapa2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )

    result = await _category_summary(department.id)

    assert [item["categoria"] for item in result] == [
        "Categoria 7897000000002",
        "Categoria 7897000000001",
    ]
    assert _by_category(result)["Categoria 7897000000001"]["total"] == 10.0
    assert _by_category(result)["Categoria 7897000000002"]["total"] == 20.0


@pytest.mark.asyncio
async def test_resumo_categoria_com_mapeamento_soma_no_bucket_canonico():
    await _cleanup()
    department = await _create_department("Canon Categoria Mesmo Dept")
    await _create_products("7897000000011", "7897000000012")
    await _create_purchase(
        department_id=department.id,
        ean="7897000000011",
        suffix="catmapa1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7897000000012",
        suffix="catmapa2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7897000000011",
        canonical="7897000000012",
    )

    result = await _category_summary(department.id)

    assert result == [{"categoria": "Categoria 7897000000012", "total": 30.0}]


@pytest.mark.asyncio
async def test_resumo_categoria_mapeamento_de_um_tenant_nao_afeta_outro():
    await _cleanup()
    department_a = await _create_department("Canon Categoria Tenant A")
    department_b = await _create_department("Canon Categoria Tenant B")
    await _create_products("7897000000021", "7897000000022")
    await _create_purchase(
        department_id=department_b.id,
        ean="7897000000021",
        suffix="cattenantb1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department_b.id,
        ean="7897000000022",
        suffix="cattenantb2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department_a.id,
        original="7897000000021",
        canonical="7897000000022",
    )

    result = await _category_summary(department_b.id)

    assert [item["categoria"] for item in result] == [
        "Categoria 7897000000021",
        "Categoria 7897000000022",
    ]
    assert _by_category(result)["Categoria 7897000000021"]["total"] == 30.0
    assert _by_category(result)["Categoria 7897000000022"]["total"] == 20.0


@pytest.mark.asyncio
async def test_resumo_categoria_global_sem_department_id_nao_aplica_mapeamento():
    await _cleanup()
    department = await _create_department("Canon Categoria Global")
    await _create_products("7897000000031", "7897000000032")
    await _create_purchase(
        department_id=department.id,
        ean="7897000000031",
        suffix="catglobal1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7897000000032",
        suffix="catglobal2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7897000000031",
        canonical="7897000000032",
    )

    result = await _category_summary(None)

    assert [item["categoria"] for item in result] == [
        "Categoria 7897000000031",
        "Categoria 7897000000032",
    ]
    assert _by_category(result)["Categoria 7897000000031"]["total"] == 30.0
    assert _by_category(result)["Categoria 7897000000032"]["total"] == 20.0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["inactive", "reverted"])
async def test_resumo_categoria_status_nao_active_nao_aplica_mapeamento(status):
    await _cleanup()
    department = await _create_department(f"Canon Categoria {status}")
    await _create_products("7897000000041", "7897000000042")
    await _create_purchase(
        department_id=department.id,
        ean="7897000000041",
        suffix=f"cat{status}1",
        quantity=Decimal("1"),
        total=Decimal("30.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean="7897000000042",
        suffix=f"cat{status}2",
        quantity=Decimal("1"),
        total=Decimal("20.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7897000000041",
        canonical="7897000000042",
        status=status,
    )

    result = await _category_summary(department.id)

    assert [item["categoria"] for item in result] == [
        "Categoria 7897000000041",
        "Categoria 7897000000042",
    ]
    assert _by_category(result)["Categoria 7897000000041"]["total"] == 30.0


@pytest.mark.asyncio
async def test_resumo_categoria_nao_altera_dados_fiscais_ou_catalogo():
    await _cleanup()
    department = await _create_department("Canon Categoria Integridade")
    await _create_products("7897000000051", "7897000000052")
    await _create_purchase(
        department_id=department.id,
        ean="7897000000051",
        suffix="catintegridade1",
        quantity=Decimal("1"),
        total=Decimal("10.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original="7897000000051",
        canonical="7897000000052",
    )

    async with SessionLocal() as db:
        product = await db.get(Produto, "7897000000051")
        item = await db.scalar(
            select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7897000000051")
        )
        product_before = (
            product.nome_limpo,
            product.marca,
            product.categoria,
            product.unidade,
        )
        item_before = (
            item.ean,
            getattr(item, "descricao" + "_original"),
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    await _category_summary(department.id)

    async with SessionLocal() as db:
        product = await db.get(Produto, "7897000000051")
        item = await db.scalar(
            select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7897000000051")
        )
        product_after = (
            product.nome_limpo,
            product.marca,
            product.categoria,
            product.unidade,
        )
        item_after = (
            item.ean,
            getattr(item, "descricao" + "_original"),
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    assert product_after == product_before
    assert item_after == item_before
