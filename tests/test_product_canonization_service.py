from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import SessionLocal
from backend.models.compras import (
    AuditLog,
    CanonizacaoProduto,
    Department,
    Fornecedor,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
)
from backend.services.product_canonization import (
    ProductCanonizationConflictError,
    ProductCanonizationNotFoundError,
    ProductCanonizationService,
    ProductCanonizationValidationError,
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


async def _seed_products(*eans: str) -> Department:
    async with SessionLocal() as db:
        department = Department(id=uuid4(), name=f"Canonizacao {uuid4()}")
        db.add(department)
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
        return department


async def _create_item_for_product(department_id, ean: str) -> None:
    async with SessionLocal() as db:
        supplier = Fornecedor(
            id=uuid4(),
            cnpj="12345678000195",
            razao_social="Fornecedor Canonizacao",
        )
        db.add(supplier)
        await db.flush()
        invoice = NotaFiscal(
            id=uuid4(),
            department_id=department_id,
            fornecedor_id=supplier.id,
            numero_nota="CAN-1",
            chave_acesso="1" * 44,
            data_emissao=date(2026, 5, 26),
            valor_total=Decimal("10.00"),
        )
        db.add(invoice)
        await db.flush()
        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=invoice.id,
                ean=ean,
                descricao_original="Descricao fiscal preservada",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("10.00"),
                valor_total=Decimal("10.00"),
            )
        )
        await db.commit()


async def _confirm(
    department_id,
    canonical: str = "7894000000002",
    originals: list[str] | None = None,
    reason: str | None = "Produtos equivalentes",
):
    async with SessionLocal() as db:
        service = ProductCanonizationService(db)
        return await service.confirm_canonization(
            ean_canonico=canonical,
            eans_originais=originals or ["7894000000001"],
            department_id=department_id,
            usuario_executor="service_user",
            reason=reason,
        )


@pytest.mark.asyncio
async def test_service_cria_mapeamento_valido():
    await _cleanup()
    department = await _seed_products("7894000000001", "7894000000002")

    result = await _confirm(department.id)

    assert result.created_count == 1
    async with SessionLocal() as db:
        mapping = await db.get(CanonizacaoProduto, (department.id, "7894000000001"))
        audit = await db.scalar(
            select(AuditLog).where(AuditLog.operacao == "PRODUCT_CANONIZED")
        )

    assert mapping is not None
    assert mapping.ean_canonico == "7894000000002"
    assert mapping.status == "active"
    assert mapping.confirmado_por == "service_user"
    assert audit is not None
    assert "7894000000001" in audit.detalhes


@pytest.mark.asyncio
async def test_service_cria_multiplos_mapeamentos_em_uma_transacao():
    await _cleanup()
    department = await _seed_products("7894000000011", "7894000000012", "7894000000013")

    result = await _confirm(
        department.id,
        canonical="7894000000013",
        originals=["7894000000011", "7894000000012"],
    )

    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(CanonizacaoProduto))
        audit_count = await db.scalar(select(func.count()).select_from(AuditLog))

    assert result.created_count == 2
    assert count == 2
    assert audit_count == 2


@pytest.mark.asyncio
async def test_service_bloqueia_ean_original_igual_ean_canonico():
    await _cleanup()
    department = await _seed_products("7894000000021")

    with pytest.raises(ProductCanonizationValidationError):
        await _confirm(
            department.id,
            canonical="7894000000021",
            originals=["7894000000021"],
        )


@pytest.mark.asyncio
async def test_service_bloqueia_ean_canonico_dentro_de_eans_originais():
    await _cleanup()
    department = await _seed_products("7894000000031", "7894000000032")

    with pytest.raises(ProductCanonizationValidationError):
        await _confirm(
            department.id,
            canonical="7894000000032",
            originals=["7894000000031", "7894000000032"],
        )


@pytest.mark.asyncio
async def test_service_bloqueia_ean_inexistente():
    await _cleanup()
    department = await _seed_products("7894000000042")

    with pytest.raises(ProductCanonizationNotFoundError):
        await _confirm(
            department.id,
            canonical="7894000000042",
            originals=["7894000000041"],
        )


@pytest.mark.asyncio
async def test_service_bloqueia_duplicado_em_eans_originais():
    await _cleanup()
    department = await _seed_products("7894000000051", "7894000000052")

    with pytest.raises(ProductCanonizationValidationError):
        await _confirm(
            department.id,
            canonical="7894000000052",
            originals=["7894000000051", "7894000000051"],
        )


@pytest.mark.asyncio
async def test_service_bloqueia_mapeamento_active_ja_existente():
    await _cleanup()
    department = await _seed_products("7894000000061", "7894000000062")
    await _confirm(
        department.id,
        canonical="7894000000062",
        originals=["7894000000061"],
    )

    with pytest.raises(ProductCanonizationConflictError):
        await _confirm(
            department.id,
            canonical="7894000000062",
            originals=["7894000000061"],
        )


@pytest.mark.asyncio
async def test_service_bloqueia_cadeia_profundidade():
    await _cleanup()
    department = await _seed_products("7894000000071", "7894000000072", "7894000000073")
    await _confirm(
        department.id,
        canonical="7894000000072",
        originals=["7894000000071"],
    )

    with pytest.raises(ProductCanonizationConflictError):
        await _confirm(
            department.id,
            canonical="7894000000073",
            originals=["7894000000072"],
        )


@pytest.mark.asyncio
async def test_service_erro_parcial_faz_rollback_total(monkeypatch):
    await _cleanup()
    department = await _seed_products("7894000000081", "7894000000082")

    async def fail_commit(self):
        raise RuntimeError("falha simulada no commit")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)

    with pytest.raises(RuntimeError):
        await _confirm(
            department.id,
            canonical="7894000000082",
            originals=["7894000000081"],
        )

    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(CanonizacaoProduto))
        audit_count = await db.scalar(select(func.count()).select_from(AuditLog))

    assert count == 0
    assert audit_count == 0


@pytest.mark.asyncio
async def test_service_nao_altera_produto():
    await _cleanup()
    department = await _seed_products("7894000000091", "7894000000092")

    async with SessionLocal() as db:
        before = await db.get(Produto, "7894000000091")
        before_values = (before.nome_limpo, before.marca, before.categoria, before.unidade)

    await _confirm(
        department.id,
        canonical="7894000000092",
        originals=["7894000000091"],
    )

    async with SessionLocal() as db:
        after = await db.get(Produto, "7894000000091")
        after_values = (after.nome_limpo, after.marca, after.categoria, after.unidade)

    assert after_values == before_values


@pytest.mark.asyncio
async def test_service_nao_altera_item_nota_fiscal():
    await _cleanup()
    department = await _seed_products("7894000000101", "7894000000102")
    await _create_item_for_product(department.id, "7894000000101")

    async with SessionLocal() as db:
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7894000000101"))
        before = (
            item.ean,
            item.descricao_original,
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    await _confirm(
        department.id,
        canonical="7894000000102",
        originals=["7894000000101"],
    )

    async with SessionLocal() as db:
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.ean == "7894000000101"))
        after = (
            item.ean,
            item.descricao_original,
            item.quantidade,
            item.valor_unitario,
            item.valor_total,
        )

    assert after == before
