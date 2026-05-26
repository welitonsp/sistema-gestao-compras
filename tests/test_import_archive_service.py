from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from backend.core.database import SessionLocal
from backend.models.compras import AuditLog, Fornecedor, HistoricoPreco, ItemNotaFiscal, NotaFiscal, Produto
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.import_archive_service import (
    ImportacaoJaArquivadaError,
    ImportacaoNaoEncontradaError,
    archive_importacao_por_chave,
)
from backend.services.repository import ProcurementRepository


def _valid_access_key(seed: str) -> str:
    base = seed[:43].ljust(43, "0")
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % len(weights)] for i, digit in enumerate(base[::-1]))
    remainder = total % 11
    check_digit = 0 if remainder in (0, 1) else 11 - remainder
    return f"{base}{check_digit}"


async def _create_imported_note(chave: str, suffix: str) -> tuple[str, str]:
    cnpj = f"1745740400{suffix.zfill(4)}"
    ean = f"78910000{suffix.zfill(5)}"
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota=f"50{suffix}",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("15.90"),
        fornecedor=FornecedorDTO(
            cnpj=cnpj,
            razao_social=f"MERCADO ARCHIVE {suffix} LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao=f"PRODUTO ARCHIVE {suffix}",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("15.90"),
                valor_total=Decimal("15.90"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )

    async with SessionLocal() as db:
        async with db.begin():
            repo = ProcurementRepository(db)
            await repo.salvar_nota_completa(chave, dto)
            await repo.registrar_auditoria(
                usuario="importador_teste",
                operacao="IMPORT_TEST",
                entidade="NotaFiscal",
                entidade_id=chave,
                detalhes="Importacao criada para teste de archive",
            )

    return cnpj, ean


async def _count(model) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model)) or 0


async def _count_archive_logs(chave: str) -> int:
    async with SessionLocal() as db:
        return await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entidade_id == chave, AuditLog.operacao == "IMPORT_ARCHIVED")
        ) or 0


@pytest.mark.anyio
async def test_archive_importacao_ativa_preserva_dados_e_registra_auditoria():
    chave = _valid_access_key("5226051745740400118365511000040935127511850")
    cnpj, ean = await _create_imported_note(chave, "185")

    async with SessionLocal() as db:
        async with db.begin():
            result = await archive_importacao_por_chave(
                chave_acesso=chave,
                usuario="archive_admin",
                motivo="importacao de teste",
                db=db,
            )

    assert result.status == "archived"
    assert result.total_itens == 1
    assert result.total_historicos_vinculados == 1

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        fornecedor = await db.scalar(select(Fornecedor).where(Fornecedor.cnpj == cnpj))
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        itens = (
            await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))
        ).scalars().all()
        historicos = (
            await db.execute(select(HistoricoPreco).where(HistoricoPreco.nota_fiscal_id == nota.id))
        ).scalars().all()
        archive_log = await db.scalar(
            select(AuditLog).where(AuditLog.entidade_id == chave, AuditLog.operacao == "IMPORT_ARCHIVED")
        )
        original_log = await db.scalar(
            select(AuditLog).where(AuditLog.entidade_id == chave, AuditLog.operacao == "IMPORT_TEST")
        )

    assert nota.status == "archived"
    assert nota.archived_at is not None
    assert nota.archived_by == "archive_admin"
    assert nota.archive_reason == "importacao de teste"
    assert fornecedor is not None
    assert produto is not None
    assert len(itens) == 1
    assert len(historicos) == 1
    assert archive_log is not None
    assert "Historicos vinculados: 1" in archive_log.detalhes
    assert original_log is not None


@pytest.mark.anyio
async def test_archive_importacao_inexistente_falha_sem_alterar_banco():
    chave = _valid_access_key("5226051745740400118365511000040935127511860")
    before = {
        NotaFiscal: await _count(NotaFiscal),
        AuditLog: await _count(AuditLog),
    }

    with pytest.raises(ImportacaoNaoEncontradaError):
        async with SessionLocal() as db:
            async with db.begin():
                await archive_importacao_por_chave(
                    chave_acesso=chave,
                    usuario="archive_admin",
                    motivo="nota inexistente",
                    db=db,
                )

    assert await _count(NotaFiscal) == before[NotaFiscal]
    assert await _count(AuditLog) == before[AuditLog]


@pytest.mark.anyio
async def test_archive_importacao_ja_arquivada_retorna_erro_controlado():
    chave = _valid_access_key("5226051745740400118365511000040935127511870")
    await _create_imported_note(chave, "187")

    async with SessionLocal() as db:
        async with db.begin():
            await archive_importacao_por_chave(
                chave_acesso=chave,
                usuario="archive_admin",
                motivo="primeiro archive",
                db=db,
            )

    with pytest.raises(ImportacaoJaArquivadaError):
        async with SessionLocal() as db:
            async with db.begin():
                await archive_importacao_por_chave(
                    chave_acesso=chave,
                    usuario="archive_admin",
                    motivo="segundo archive",
                    db=db,
                )

    assert await _count_archive_logs(chave) == 1


@pytest.mark.anyio
async def test_archive_importacao_falha_no_meio_faz_rollback(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511880")
    await _create_imported_note(chave, "188")

    async def fail_audit(self, **kwargs):
        raise RuntimeError("falha simulada na auditoria")

    monkeypatch.setattr(ProcurementRepository, "registrar_auditoria", fail_audit)

    with pytest.raises(RuntimeError):
        async with SessionLocal() as db:
            async with db.begin():
                await archive_importacao_por_chave(
                    chave_acesso=chave,
                    usuario="archive_admin",
                    motivo="rollback de teste",
                    db=db,
                )

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))

    assert nota.status == "active"
    assert nota.archived_at is None
    assert nota.archived_by is None
    assert nota.archive_reason is None
    assert await _count_archive_logs(chave) == 0
