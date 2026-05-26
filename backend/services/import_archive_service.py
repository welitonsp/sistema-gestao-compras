"""Service for audit-safe archiving of imported invoices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import HistoricoPreco, ItemNotaFiscal, NotaFiscal
from backend.services.repository import ProcurementRepository


class ImportArchiveError(Exception):
    """Base error for controlled import archive failures."""


class ImportacaoNaoEncontradaError(ImportArchiveError):
    """Raised when no imported invoice exists for the requested access key."""


class ImportacaoJaArquivadaError(ImportArchiveError):
    """Raised when the imported invoice has already been archived."""


@dataclass(frozen=True)
class ImportArchiveResult:
    """Summary of an archived import operation."""

    chave_acesso: str
    status: str
    archived_at: datetime
    total_itens: int
    total_historicos_vinculados: int


class ImportArchiveService:
    """Archives an import without deleting fiscal, catalog, price, or audit data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProcurementRepository(db)

    async def archive_importacao_por_chave(
        self,
        chave_acesso: str,
        usuario: str,
        motivo: str,
    ) -> ImportArchiveResult:
        """Mark an imported invoice as archived inside the caller-managed transaction."""

        motivo = motivo.strip()
        if not motivo:
            raise ImportArchiveError("Motivo do archive e obrigatorio.")

        nota = await self.db.scalar(
            select(NotaFiscal)
            .where(NotaFiscal.chave_acesso == chave_acesso)
            .with_for_update()
        )
        if nota is None:
            raise ImportacaoNaoEncontradaError("Importacao nao encontrada.")

        if nota.status == "archived":
            raise ImportacaoJaArquivadaError("Importacao ja arquivada.")

        total_itens = await self.db.scalar(
            select(func.count()).select_from(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id)
        ) or 0
        total_historicos = await self.db.scalar(
            select(func.count()).select_from(HistoricoPreco).where(HistoricoPreco.nota_fiscal_id == nota.id)
        ) or 0

        archived_at = datetime.now(timezone.utc)
        nota.status = "archived"
        nota.archived_at = archived_at
        nota.archived_by = usuario
        nota.archive_reason = motivo

        await self.repo.registrar_auditoria(
            usuario=usuario,
            operacao="IMPORT_ARCHIVED",
            entidade="NotaFiscal",
            entidade_id=nota.chave_acesso,
            detalhes=(
                f"Archive de importacao. Motivo: {motivo}. "
                f"Itens: {total_itens}. Historicos vinculados: {total_historicos}."
            ),
            department_id=nota.department_id,
        )
        await self.db.flush()

        return ImportArchiveResult(
            chave_acesso=nota.chave_acesso,
            status=nota.status,
            archived_at=archived_at,
            total_itens=total_itens,
            total_historicos_vinculados=total_historicos,
        )


async def archive_importacao_por_chave(
    chave_acesso: str,
    usuario: str,
    motivo: str,
    db: AsyncSession,
) -> ImportArchiveResult:
    """Convenience function for archiving an import by access key."""

    service = ImportArchiveService(db)
    return await service.archive_importacao_por_chave(
        chave_acesso=chave_acesso,
        usuario=usuario,
        motivo=motivo,
    )
