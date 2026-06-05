from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

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


async def _enable_foreign_keys(db) -> None:
    await db.execute(text("PRAGMA foreign_keys=ON"))


async def _disable_foreign_keys(db) -> None:
    await db.execute(text("PRAGMA foreign_keys=OFF"))


async def _cleanup() -> None:
    async with SessionLocal() as db:
        # Existing tests may create rows with department_id values that do not
        # exist in departments. Keep FK checks off only while cleaning tables.
        await _disable_foreign_keys(db)
        await db.execute(delete(CanonizacaoProduto))
        await db.execute(delete(HistoricoPreco))
        await db.execute(delete(ItemNotaFiscal))
        await db.execute(delete(NotaFiscal))
        await db.execute(delete(Fornecedor))
        await db.execute(delete(Produto))
        await db.execute(delete(Department))
        await db.commit()


async def _add_department_and_products(
    *,
    department_name: str = "Departamento Canonizacao",
    original_ean: str = "7893000000001",
    canonical_ean: str = "7893000000002",
) -> tuple[Department, Produto, Produto]:
    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            department = Department(
                id=uuid4(),
                name=department_name,
                description="Departamento de teste",
            )
            original = Produto(
                ean=original_ean,
                nome_limpo=f"Produto Original {original_ean}",
                categoria="MERCEARIA",
                unidade="un",
            )
            canonical = Produto(
                ean=canonical_ean,
                nome_limpo=f"Produto Canonico {canonical_ean}",
                categoria="MERCEARIA",
                unidade="un",
            )
            db.add_all([department, original, canonical])
            await db.commit()
            return department, original, canonical
        finally:
            # PRAGMA foreign_keys is connection-scoped in SQLite. Leave it off
            # after this helper so the shared test pool does not affect suites
            # that intentionally use synthetic department_id values.
            await _disable_foreign_keys(db)


@pytest.mark.asyncio
async def test_cria_mapeamento_valido_com_status_default_active():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            mapping = CanonizacaoProduto(
                department_id=department.id,
                ean_original=original.ean,
                ean_canonico=canonical.ean,
                confidence_score=Decimal("0.9500"),
                reason="Produtos similares em preview deterministico.",
            )
            db.add(mapping)
            await db.commit()

            stored = await db.scalar(select(CanonizacaoProduto))
        finally:
            await _disable_foreign_keys(db)

    assert stored is not None
    assert stored.department_id == department.id
    assert stored.ean_original == original.ean
    assert stored.ean_canonico == canonical.ean
    assert stored.status == "active"
    assert stored.revertido_por is None
    assert stored.revertido_em is None
    assert stored.revert_reason is None
    assert stored.created_at is not None
    assert stored.updated_at is not None


@pytest.mark.asyncio
async def test_cria_mapeamento_reverted_com_campos_de_reversao():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()
    reverted_at = datetime(2026, 6, 5, 12, 30, tzinfo=timezone.utc)

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            mapping = CanonizacaoProduto(
                department_id=department.id,
                ean_original=original.ean,
                ean_canonico=canonical.ean,
                status="reverted",
                revertido_por="auditor@sgc.local",
                revertido_em=reverted_at,
                revert_reason="Canonizacao revertida apos revisao operacional.",
            )
            db.add(mapping)
            await db.commit()

            stored = await db.scalar(select(CanonizacaoProduto))
        finally:
            await _disable_foreign_keys(db)

    assert stored is not None
    assert stored.status == "reverted"
    assert stored.revertido_por == "auditor@sgc.local"
    assert stored.revertido_em in {reverted_at, reverted_at.replace(tzinfo=None)}
    assert stored.revert_reason == "Canonizacao revertida apos revisao operacional."


@pytest.mark.asyncio
async def test_campos_de_reversao_sao_opcionais():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                    status="reverted",
                )
            )
            await db.commit()

            stored = await db.scalar(select(CanonizacaoProduto))
        finally:
            await _disable_foreign_keys(db)

    assert stored is not None
    assert stored.status == "reverted"
    assert stored.revertido_por is None
    assert stored.revertido_em is None
    assert stored.revert_reason is None


@pytest.mark.asyncio
async def test_pk_composta_nao_permite_mesmo_department_e_ean_original():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                )
            )
            await db.commit()
        finally:
            await _disable_foreign_keys(db)

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await _disable_foreign_keys(db)


@pytest.mark.asyncio
async def test_check_status_invalido_bloqueado():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                    status="archived",
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await _disable_foreign_keys(db)


@pytest.mark.asyncio
async def test_multi_tenant_permite_mesmo_ean_original_em_departamentos_diferentes():
    await _cleanup()
    department_a, original, canonical = await _add_department_and_products(
        department_name="Departamento Canonizacao A"
    )
    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            department_b = Department(
                id=uuid4(),
                name="Departamento Canonizacao B",
                description="Outro departamento de teste",
            )
            db.add(department_b)
            await db.commit()

            db.add_all(
                [
                    CanonizacaoProduto(
                        department_id=department_a.id,
                        ean_original=original.ean,
                        ean_canonico=canonical.ean,
                    ),
                    CanonizacaoProduto(
                        department_id=department_b.id,
                        ean_original=original.ean,
                        ean_canonico=canonical.ean,
                    ),
                ]
            )
            await db.commit()

            count = len((await db.execute(select(CanonizacaoProduto))).scalars().all())
        finally:
            await _disable_foreign_keys(db)

    assert count == 2


@pytest.mark.asyncio
async def test_restrict_nao_permite_deletar_produto_original_ou_canonico_usado():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                )
            )
            await db.commit()

            original_db = await db.get(Produto, original.ean)
            assert original_db is not None
            await db.delete(original_db)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

            canonical_db = await db.get(Produto, canonical.ean)
            assert canonical_db is not None
            await db.delete(canonical_db)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await _disable_foreign_keys(db)


@pytest.mark.asyncio
async def test_cascade_department_remove_mapeamento():
    await _cleanup()
    department, original, canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                )
            )
            await db.commit()

            department_db = await db.get(Department, department.id)
            assert department_db is not None
            await db.delete(department_db)
            await db.commit()

            remaining = await db.scalar(select(CanonizacaoProduto))
        finally:
            await _disable_foreign_keys(db)

    assert remaining is None


@pytest.mark.asyncio
async def test_check_nao_permite_ean_original_igual_ean_canonico():
    await _cleanup()
    department, original, _canonical = await _add_department_and_products()

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=original.ean,
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await _disable_foreign_keys(db)


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [Decimal("-0.0001"), Decimal("1.0001")])
async def test_check_confidence_score_deve_ficar_entre_zero_e_um(score):
    await _cleanup()
    department, original, canonical = await _add_department_and_products(
        original_ean=f"78930000000{str(abs(hash(score)))[:2]}",
        canonical_ean=f"78930000001{str(abs(hash(score)))[:2]}",
    )

    async with SessionLocal() as db:
        await _enable_foreign_keys(db)
        try:
            db.add(
                CanonizacaoProduto(
                    department_id=department.id,
                    ean_original=original.ean,
                    ean_canonico=canonical.ean,
                    confidence_score=score,
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await _disable_foreign_keys(db)
