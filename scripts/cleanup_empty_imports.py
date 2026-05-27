"""Local controlled cleanup for empty invoice imports created before the zero-item hotfix.

This script is intentionally manual. By default it only lists candidates and never
modifies the database. To archive candidates locally, run with both
``--apply-local`` and ``--confirm-local-cleanup``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.compras import HistoricoPreco, ItemNotaFiscal, NotaFiscal


ARCHIVED_BY = "local-cleanup"
ARCHIVE_REASON = "Nota vazia gerada antes do hotfix de bloqueio de importações sem produtos"


@dataclass(frozen=True)
class EmptyImportCandidate:
    id: UUID
    chave_acesso: str
    status: str
    quality_status: str | None
    parser_source: str | None
    item_count: int | None
    itens_salvos: int
    historicos_vinculados: int
    created_at: datetime

    @property
    def chave_mascarada(self) -> str:
        return mask_access_key(self.chave_acesso)


def mask_access_key(chave_acesso: str | None) -> str:
    digits = "".join(char for char in str(chave_acesso or "") if char.isdigit())
    if len(digits) < 8:
        return "<chave-redigida>"
    return f"{digits[:4]}...{digits[-4:]}"


def _item_counts_subquery():
    return (
        select(
            ItemNotaFiscal.nota_fiscal_id.label("nota_fiscal_id"),
            func.count(ItemNotaFiscal.id).label("itens_salvos"),
        )
        .group_by(ItemNotaFiscal.nota_fiscal_id)
        .subquery()
    )


def _history_counts_subquery():
    return (
        select(
            HistoricoPreco.nota_fiscal_id.label("nota_fiscal_id"),
            func.count(HistoricoPreco.id).label("historicos_vinculados"),
        )
        .where(HistoricoPreco.nota_fiscal_id.is_not(None))
        .group_by(HistoricoPreco.nota_fiscal_id)
        .subquery()
    )


def _candidate_filters(item_count_column, history_count_column):
    return (
        NotaFiscal.status == "active",
        or_(NotaFiscal.numero_nota.is_(None), func.trim(NotaFiscal.numero_nota) == ""),
        NotaFiscal.extraction_quality_status == "failed",
        NotaFiscal.extraction_parser_source == "ai_fallback",
        NotaFiscal.extraction_item_count == 0,
        func.coalesce(item_count_column, 0) == 0,
        func.coalesce(history_count_column, 0) == 0,
    )


async def find_empty_import_candidates(db: AsyncSession) -> list[EmptyImportCandidate]:
    item_counts = _item_counts_subquery()
    history_counts = _history_counts_subquery()
    itens_salvos = func.coalesce(item_counts.c.itens_salvos, 0)
    historicos_vinculados = func.coalesce(history_counts.c.historicos_vinculados, 0)

    stmt = (
        select(
            NotaFiscal.id,
            NotaFiscal.chave_acesso,
            NotaFiscal.status,
            NotaFiscal.extraction_quality_status,
            NotaFiscal.extraction_parser_source,
            NotaFiscal.extraction_item_count,
            itens_salvos.label("itens_salvos"),
            historicos_vinculados.label("historicos_vinculados"),
            NotaFiscal.created_at,
        )
        .outerjoin(item_counts, item_counts.c.nota_fiscal_id == NotaFiscal.id)
        .outerjoin(history_counts, history_counts.c.nota_fiscal_id == NotaFiscal.id)
        .where(*_candidate_filters(item_counts.c.itens_salvos, history_counts.c.historicos_vinculados))
        .order_by(NotaFiscal.created_at.desc(), NotaFiscal.id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        EmptyImportCandidate(
            id=row.id,
            chave_acesso=row.chave_acesso,
            status=row.status,
            quality_status=row.extraction_quality_status,
            parser_source=row.extraction_parser_source,
            item_count=row.extraction_item_count,
            itens_salvos=int(row.itens_salvos or 0),
            historicos_vinculados=int(row.historicos_vinculados or 0),
            created_at=row.created_at,
        )
        for row in rows
    ]


async def archive_empty_import_candidates(db: AsyncSession) -> list[EmptyImportCandidate]:
    candidates = await find_empty_import_candidates(db)
    if not candidates:
        return []

    candidate_ids = [candidate.id for candidate in candidates]
    notas = (
        await db.execute(
            select(NotaFiscal)
            .where(NotaFiscal.id.in_(candidate_ids))
            .order_by(NotaFiscal.created_at.desc(), NotaFiscal.id)
        )
    ).scalars().all()

    archived_at = datetime.now(timezone.utc)
    for nota in notas:
        nota.status = "archived"
        nota.archived_at = archived_at
        nota.archived_by = ARCHIVED_BY
        nota.archive_reason = ARCHIVE_REASON

    await db.flush()
    return candidates


def format_candidates(candidates: Sequence[EmptyImportCandidate], *, archived: bool = False) -> str:
    action = "arquivada(s)" if archived else "candidata(s)"
    lines = [
        "Limpeza local controlada de notas vazias antigas",
        f"Total {action}: {len(candidates)}",
    ]
    if not candidates:
        return "\n".join(lines)

    lines.append("id | chave | status | quality_status | parser_source | item_count | itens_salvos | historicos | created_at")
    for candidate in candidates:
        lines.append(
            " | ".join(
                [
                    str(candidate.id),
                    candidate.chave_mascarada,
                    candidate.status,
                    str(candidate.quality_status),
                    str(candidate.parser_source),
                    str(candidate.item_count),
                    str(candidate.itens_salvos),
                    str(candidate.historicos_vinculados),
                    candidate.created_at.isoformat(),
                ]
            )
        )
    return "\n".join(lines)


async def run_cleanup(*, apply_local: bool) -> list[EmptyImportCandidate]:
    from backend.core.database import SessionLocal

    async with SessionLocal() as db:
        if apply_local:
            candidates = await archive_empty_import_candidates(db)
            await db.commit()
            return candidates

        candidates = await find_empty_import_candidates(db)
        await db.rollback()
        return candidates


async def _async_main(args: argparse.Namespace) -> int:
    if args.apply_local and not args.confirm_local_cleanup:
        print("Para aplicar, use --apply-local junto com --confirm-local-cleanup.")
        return 2

    candidates = await run_cleanup(apply_local=args.apply_local)
    print(format_candidates(candidates, archived=args.apply_local))
    if not args.apply_local:
        print("Dry-run: nenhuma alteração foi aplicada.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ferramenta local/controlada para arquivar notas vazias antigas sem hard delete.",
    )
    parser.add_argument(
        "--apply-local",
        action="store_true",
        help="Arquiva candidatas locais. Requer --confirm-local-cleanup.",
    )
    parser.add_argument(
        "--archive",
        dest="apply_local",
        action="store_true",
        help="Alias de --apply-local.",
    )
    parser.add_argument(
        "--confirm-local-cleanup",
        action="store_true",
        help="Confirmacao explicita exigida para alterar o banco local.",
    )
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
