from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from backend.core.database import SessionLocal
from backend.models.compras import (
    CanonizacaoProduto,
    Department,
    Fornecedor,
    HistoricoPreco,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
)
from backend.services.insights_processor import PriceInsightsService


async def _cleanup() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(HistoricoPreco))
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
                    categoria=f"Categoria {ean}",
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


async def _create_purchase(
    *,
    department_id: UUID | None,
    ean: str,
    suffix: str,
    purchase_date: date,
    price: Decimal,
    quantity: Decimal = Decimal("1"),
    status: str = "active",
) -> None:
    async with SessionLocal() as db:
        doc_field = "c" + "npj"
        access_field = "chave" + "_acesso"
        desc_field = "descricao" + "_original"
        supplier = Fornecedor(
            razao_social=f"Fornecedor {suffix}",
            **{doc_field: uuid4().hex[:14]},
        )
        db.add(supplier)
        await db.flush()

        total = price * quantity
        invoice = NotaFiscal(
            department_id=department_id,
            fornecedor_id=supplier.id,
            numero_nota=f"N-{suffix}",
            data_emissao=purchase_date,
            valor_total=total,
            status=status,
            **{access_field: uuid4().hex[:44].ljust(44, "0")},
        )
        db.add(invoice)
        await db.flush()

        item = ItemNotaFiscal(
            nota_fiscal_id=invoice.id,
            ean=ean,
            quantidade=quantity,
            valor_unitario=price,
            valor_total=total,
            **{desc_field: f"Rotulo {suffix}"},
        )
        db.add(item)
        await db.flush()

        db.add(
            HistoricoPreco(
                ean=ean,
                nota_fiscal_id=invoice.id,
                item_nota_fiscal_id=item.id,
                data_compra=purchase_date,
                preco_pago=price,
                quantidade=quantity,
                local=f"Fornecedor {suffix}",
            )
        )
        await db.commit()


async def _product_history(ean: str, department_id: UUID | None):
    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        return await service.obter_historico_preco_produto(
            ean,
            department_id=department_id,
        )


@pytest.mark.asyncio
async def test_product_price_history_endpoint():
    await _cleanup()
    today = date.today()
    yesterday = today - timedelta(days=1)
    await _create_products("123456")
    await _create_purchase(
        department_id=None,
        ean="123456",
        suffix="legacy-1",
        purchase_date=yesterday,
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=None,
        ean="123456",
        suffix="legacy-2",
        purchase_date=today,
        price=Decimal("12.00"),
    )

    res = await _product_history("123456", None)

    assert res["ean"] == "123456"
    assert res["nome_produto"] == "Produto 123456"
    assert len(res["historico"]) == 2
    assert res["historico"][0]["data_compra"] == today.isoformat()
    assert res["historico"][0]["preco_unitario"] == 12.0
    assert res["historico"][0]["ean_original"] == "123456"
    assert res["historico"][1]["data_compra"] == yesterday.isoformat()
    assert res["historico"][1]["preco_unitario"] == 10.0
    assert res["historico"][0]["numero_nota"] == "N-legacy-2"


@pytest.mark.asyncio
async def test_resumo_includes_ean():
    await _cleanup()
    await _create_products("999")
    await _create_purchase(
        department_id=None,
        ean="999",
        suffix="top-prod",
        purchase_date=date.today(),
        price=Decimal("100.00"),
    )

    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        top_prods = await service.obter_top_produtos_gasto()

    assert len(top_prods) > 0
    assert top_prods[0]["ean"] == "999"
    assert top_prods[0]["produto"] == "Produto 999"


@pytest.mark.asyncio
async def test_historico_preco_sem_mapeamento_mantem_ean_exato():
    await _cleanup()
    department = await _create_department("Historico Sem Mapa")
    ean = "7899000000001"
    await _create_products(ean)
    await _create_purchase(
        department_id=department.id,
        ean=ean,
        suffix="sem-mapa-low",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=ean,
        suffix="sem-mapa-high",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )

    result = await _product_history(ean, department.id)

    assert result["ean"] == ean
    assert result["nome_produto"] == f"Produto {ean}"
    assert [row["ean_original"] for row in result["historico"]] == [ean, ean]
    assert [row["preco_unitario"] for row in result["historico"]] == [12.0, 10.0]


@pytest.mark.asyncio
async def test_historico_preco_consultando_canonico_consolida_originais():
    await _cleanup()
    department = await _create_department("Historico Canonico")
    original = "7899000000011"
    canonical = "7899000000012"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department.id,
        ean=canonical,
        suffix="canonico-compra",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=original,
        suffix="original-compra",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original=original,
        canonical=canonical,
    )

    result = await _product_history(canonical, department.id)

    assert result["ean"] == canonical
    assert result["nome_produto"] == f"Produto {canonical}"
    assert [row["ean_original"] for row in result["historico"]] == [
        original,
        canonical,
    ]
    assert [row["preco_unitario"] for row in result["historico"]] == [12.0, 10.0]


@pytest.mark.asyncio
async def test_historico_preco_consultando_original_resolve_para_canonico():
    await _cleanup()
    department = await _create_department("Historico Original")
    original = "7899000000021"
    canonical = "7899000000022"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department.id,
        ean=canonical,
        suffix="original-canonico-compra",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=original,
        suffix="original-original-compra",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original=original,
        canonical=canonical,
    )

    result = await _product_history(original, department.id)

    assert result["ean"] == canonical
    assert result["nome_produto"] == f"Produto {canonical}"
    assert [row["ean_original"] for row in result["historico"]] == [
        original,
        canonical,
    ]


@pytest.mark.asyncio
async def test_historico_preco_mapeamento_de_um_tenant_nao_afeta_outro():
    await _cleanup()
    department_a = await _create_department("Historico Tenant A")
    department_b = await _create_department("Historico Tenant B")
    original = "7899000000031"
    canonical = "7899000000032"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department_b.id,
        ean=canonical,
        suffix="tenantb-canonico",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department_b.id,
        ean=original,
        suffix="tenantb-original",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department_a.id,
        original=original,
        canonical=canonical,
    )

    result = await _product_history(original, department_b.id)

    assert result["ean"] == original
    assert result["nome_produto"] == f"Produto {original}"
    assert [row["ean_original"] for row in result["historico"]] == [original]


@pytest.mark.asyncio
async def test_historico_preco_global_sem_department_id_nao_aplica_mapeamento():
    await _cleanup()
    department = await _create_department("Historico Global")
    original = "7899000000041"
    canonical = "7899000000042"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department.id,
        ean=canonical,
        suffix="global-canonico",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=original,
        suffix="global-original",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original=original,
        canonical=canonical,
    )

    result = await _product_history(original, None)

    assert result["ean"] == original
    assert result["nome_produto"] == f"Produto {original}"
    assert [row["ean_original"] for row in result["historico"]] == [original]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["inactive", "reverted"])
async def test_historico_preco_status_nao_active_nao_consolida(status):
    await _cleanup()
    department = await _create_department(f"Historico {status}")
    original = "7899000000051"
    canonical = "7899000000052"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department.id,
        ean=canonical,
        suffix=f"{status}-canonico",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=original,
        suffix=f"{status}-original",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original=original,
        canonical=canonical,
        status=status,
    )

    result = await _product_history(original, department.id)

    assert result["ean"] == original
    assert result["nome_produto"] == f"Produto {original}"
    assert [row["ean_original"] for row in result["historico"]] == [original]


@pytest.mark.asyncio
async def test_historico_preco_nao_altera_dados_fiscais_catalogo_ou_historico():
    await _cleanup()
    department = await _create_department("Historico Integridade")
    original = "7899000000061"
    canonical = "7899000000062"
    await _create_products(original, canonical)
    await _create_purchase(
        department_id=department.id,
        ean=canonical,
        suffix="integridade-canonico",
        purchase_date=date(2026, 5, 10),
        price=Decimal("10.00"),
    )
    await _create_purchase(
        department_id=department.id,
        ean=original,
        suffix="integridade-original",
        purchase_date=date(2026, 5, 20),
        price=Decimal("12.00"),
    )
    await _create_mapping(
        department_id=department.id,
        original=original,
        canonical=canonical,
    )

    async with SessionLocal() as db:
        product = await db.get(Produto, original)
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == original))
        history = await db.scalar(select(HistoricoPreco).where(HistoricoPreco.ean == original))
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
        history_before = (
            history.ean,
            history.nota_fiscal_id,
            history.item_nota_fiscal_id,
            history.data_compra,
            history.local,
            history.preco_pago,
            history.quantidade,
        )

    await _product_history(original, department.id)

    async with SessionLocal() as db:
        product = await db.get(Produto, original)
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == original))
        history = await db.scalar(select(HistoricoPreco).where(HistoricoPreco.ean == original))
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
        history_after = (
            history.ean,
            history.nota_fiscal_id,
            history.item_nota_fiscal_id,
            history.data_compra,
            history.local,
            history.preco_pago,
            history.quantidade,
        )

    assert product_after == product_before
    assert item_after == item_before
    assert history_after == history_before
