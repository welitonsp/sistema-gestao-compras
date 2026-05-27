from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.core.database import SessionLocal
from backend.models.compras import Fornecedor, HistoricoPreco, ItemNotaFiscal, NotaFiscal, Produto
from scripts.cleanup_empty_imports import (
    ARCHIVE_REASON,
    ARCHIVED_BY,
    archive_empty_import_candidates,
    find_empty_import_candidates,
    format_candidates,
)


def _access_key(seed: int) -> str:
    return f"9{seed:043d}"[-44:]


async def _create_fornecedor(db, suffix: str) -> Fornecedor:
    fornecedor = Fornecedor(
        cnpj=f"93000000{suffix.zfill(6)}",
        razao_social=f"FORNECEDOR CLEANUP {suffix}",
    )
    db.add(fornecedor)
    await db.flush()
    return fornecedor


async def _create_empty_note(
    db,
    *,
    suffix: str,
    status: str = "active",
    numero_nota: str = "",
    quality_status: str = "failed",
    parser_source: str = "ai_fallback",
    item_count: int | None = 0,
) -> NotaFiscal:
    fornecedor = await _create_fornecedor(db, suffix)
    nota = NotaFiscal(
        fornecedor_id=fornecedor.id,
        numero_nota=numero_nota,
        chave_acesso=_access_key(int(suffix)),
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("0.00"),
        status=status,
        extraction_quality_status=quality_status,
        extraction_parser_source=parser_source,
        extraction_item_count=item_count,
    )
    db.add(nota)
    await db.flush()
    return nota


async def _add_item_and_history(db, nota: NotaFiscal, suffix: str) -> None:
    produto = Produto(
        ean=f"7899{suffix.zfill(9)}",
        nome_limpo=f"PRODUTO CLEANUP {suffix}",
        categoria="OUTROS",
        unidade="un",
    )
    db.add(produto)
    await db.flush()
    item = ItemNotaFiscal(
        nota_fiscal_id=nota.id,
        ean=produto.ean,
        descricao_original=f"ITEM CLEANUP {suffix}",
        quantidade=Decimal("1"),
        valor_unitario=Decimal("10.00"),
        valor_total=Decimal("10.00"),
    )
    db.add(item)
    await db.flush()
    db.add(
        HistoricoPreco(
            ean=produto.ean,
            nota_fiscal_id=nota.id,
            item_nota_fiscal_id=item.id,
            data_compra=nota.data_emissao,
            local="FORNECEDOR CLEANUP",
            preco_pago=Decimal("10.00"),
            quantidade=Decimal("1"),
        )
    )
    await db.flush()


@pytest.mark.anyio
async def test_cleanup_empty_imports_dry_run_identifica_candidatas_sem_alterar():
    async with SessionLocal() as db:
        candidate = await _create_empty_note(db, suffix="810001")
        valid = await _create_empty_note(
            db,
            suffix="810002",
            numero_nota="VALIDA",
            quality_status="ok",
            parser_source="deterministic",
            item_count=1,
        )
        await _add_item_and_history(db, valid, "810002")

        candidates = await find_empty_import_candidates(db)
        candidate_ids = {item.id for item in candidates}
        report = format_candidates(candidates)

        assert candidate.id in candidate_ids
        assert valid.id not in candidate_ids
        assert candidate.chave_acesso not in report
        assert f"{candidate.chave_acesso[:4]}...{candidate.chave_acesso[-4:]}" in report

        await db.refresh(candidate)
        assert candidate.status == "active"
        assert candidate.archived_at is None
        assert candidate.archived_by is None

        await db.rollback()


@pytest.mark.anyio
async def test_cleanup_empty_imports_apply_arquiva_apenas_candidatas():
    async with SessionLocal() as db:
        candidate = await _create_empty_note(db, suffix="820001")
        valid_with_items = await _create_empty_note(
            db,
            suffix="820002",
            numero_nota="VALIDA",
            quality_status="ok",
            parser_source="deterministic",
            item_count=1,
        )
        await _add_item_and_history(db, valid_with_items, "820002")

        archived_note = await _create_empty_note(db, suffix="820003", status="archived")
        archived_note.archived_at = datetime(2026, 5, 26, tzinfo=timezone.utc)
        archived_note.archived_by = "manual"
        archived_note.archive_reason = "ja arquivada antes"

        failed_with_item = await _create_empty_note(db, suffix="820004")
        await _add_item_and_history(db, failed_with_item, "820004")

        candidates = await archive_empty_import_candidates(db)
        candidate_ids = {item.id for item in candidates}
        report = format_candidates(candidates, archived=True)

        assert candidate.id in candidate_ids
        assert valid_with_items.id not in candidate_ids
        assert archived_note.id not in candidate_ids
        assert failed_with_item.id not in candidate_ids
        assert candidate.chave_acesso not in report

        await db.refresh(candidate)
        await db.refresh(valid_with_items)
        await db.refresh(archived_note)
        await db.refresh(failed_with_item)

        assert candidate.status == "archived"
        assert candidate.archived_at is not None
        assert candidate.archived_by == ARCHIVED_BY
        assert candidate.archive_reason == ARCHIVE_REASON
        assert valid_with_items.status == "active"
        assert archived_note.status == "archived"
        assert archived_note.archived_by == "manual"
        assert archived_note.archive_reason == "ja arquivada antes"
        assert failed_with_item.status == "active"
        assert failed_with_item.archived_at is None

        await db.rollback()
