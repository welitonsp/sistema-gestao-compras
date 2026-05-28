"""Controlled deletion of imported invoices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import Fornecedor, HistoricoPreco, ItemNotaFiscal, NotaFiscal, Produto
from backend.services.repository import ProcurementRepository


DEFAULT_IMPORT_DELETE_REASON = "Exclusao solicitada pelo usuario."
_FORMATTED_DOC_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_SENSITIVE_NUMBER_RE = re.compile(r"\b\d{11,44}\b")
_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)


class ImportDeleteError(Exception):
    """Base error for controlled import deletion failures."""


class ImportDeleteNotFoundError(ImportDeleteError):
    """Raised when the invoice does not exist or is outside the user's department."""


def _redact_sensitive_text(text: str) -> str:
    text = _URL_RE.sub("<url-redigida>", text)
    text = _FORMATTED_DOC_RE.sub("<documento-redigido>", text)
    return _SENSITIVE_NUMBER_RE.sub("<numero-redigido>", text)


@dataclass(frozen=True)
class ImportDeleteResult:
    id: UUID
    numero_nota: str
    status: str
    itens_deletados: int
    historico_precos_deletados: int
    produtos_orfaos_deletados: int
    fornecedores_orfaos_deletados: int
    mensagem: str = "Nota fiscal excluída com sucesso."


class ImportDeleteService:
    """Deletes an imported invoice and dependent import data inside a transaction."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProcurementRepository(db)

    async def delete_importacao_por_id(
        self,
        *,
        nota_id: UUID,
        usuario: str,
        department_id: UUID | None,
        motivo: str | None = None,
    ) -> ImportDeleteResult:
        motivo_normalizado = (motivo or DEFAULT_IMPORT_DELETE_REASON).strip() or DEFAULT_IMPORT_DELETE_REASON
        motivo_auditavel = _redact_sensitive_text(motivo_normalizado)

        nota = await self.db.scalar(
            select(NotaFiscal)
            .where(NotaFiscal.id == nota_id)
            .with_for_update()
        )
        if nota is None or (department_id is not None and nota.department_id != department_id):
            raise ImportDeleteNotFoundError("Importacao nao encontrada.")

        numero_nota = nota.numero_nota
        fornecedor_id = nota.fornecedor_id
        nota_department_id = nota.department_id

        item_rows = (
            await self.db.execute(
                select(ItemNotaFiscal.id, ItemNotaFiscal.ean)
                .where(ItemNotaFiscal.nota_fiscal_id == nota.id)
            )
        ).all()
        item_ids = [row.id for row in item_rows]
        item_eans = sorted({row.ean for row in item_rows})

        historico_delete_stmt = delete(HistoricoPreco).where(HistoricoPreco.nota_fiscal_id == nota.id)
        if item_ids:
            historico_delete_stmt = delete(HistoricoPreco).where(
                (HistoricoPreco.nota_fiscal_id == nota.id)
                | (HistoricoPreco.item_nota_fiscal_id.in_(item_ids))
            )
        historico_precos_deletados = (await self.db.execute(historico_delete_stmt)).rowcount or 0

        itens_deletados = (
            await self.db.execute(delete(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))
        ).rowcount or 0

        await self.db.execute(delete(NotaFiscal).where(NotaFiscal.id == nota.id))

        produtos_orfaos_deletados = 0
        for ean in item_eans:
            if not ean.startswith("SEM_EAN_"):
                continue
            remaining_items = await self.db.scalar(
                select(func.count()).select_from(ItemNotaFiscal).where(ItemNotaFiscal.ean == ean)
            ) or 0
            remaining_history = await self.db.scalar(
                select(func.count()).select_from(HistoricoPreco).where(HistoricoPreco.ean == ean)
            ) or 0
            if remaining_items == 0 and remaining_history == 0:
                produtos_orfaos_deletados += (
                    await self.db.execute(delete(Produto).where(Produto.ean == ean))
                ).rowcount or 0

        remaining_supplier_notes = await self.db.scalar(
            select(func.count()).select_from(NotaFiscal).where(NotaFiscal.fornecedor_id == fornecedor_id)
        ) or 0
        fornecedores_orfaos_deletados = 0
        if remaining_supplier_notes == 0:
            fornecedores_orfaos_deletados = (
                await self.db.execute(delete(Fornecedor).where(Fornecedor.id == fornecedor_id))
            ).rowcount or 0

        await self.repo.registrar_auditoria(
            usuario=usuario,
            operacao="IMPORT_DELETED",
            entidade="NotaFiscal",
            entidade_id=str(nota_id),
            detalhes=(
                f"Exclusao de importacao por id. Motivo: {motivo_auditavel}. "
                f"Nota: {numero_nota}. Itens: {itens_deletados}. "
                f"Historicos: {historico_precos_deletados}. "
                f"Produtos orfaos: {produtos_orfaos_deletados}. "
                f"Fornecedores orfaos: {fornecedores_orfaos_deletados}."
            ),
            department_id=nota_department_id,
        )
        await self.db.flush()

        return ImportDeleteResult(
            id=nota_id,
            numero_nota=numero_nota,
            status="deleted",
            itens_deletados=itens_deletados,
            historico_precos_deletados=historico_precos_deletados,
            produtos_orfaos_deletados=produtos_orfaos_deletados,
            fornecedores_orfaos_deletados=fornecedores_orfaos_deletados,
        )


async def delete_importacao_por_id(
    *,
    nota_id: UUID,
    usuario: str,
    department_id: UUID | None,
    motivo: str | None,
    db: AsyncSession,
) -> ImportDeleteResult:
    service = ImportDeleteService(db)
    return await service.delete_importacao_por_id(
        nota_id=nota_id,
        usuario=usuario,
        department_id=department_id,
        motivo=motivo,
    )
