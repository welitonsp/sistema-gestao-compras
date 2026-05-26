from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import AuditLog, Fornecedor, HistoricoPreco, ItemNotaFiscal, NotaFiscal, Produto, User, UserRole
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.repository import ProcurementRepository


def _valid_access_key(seed: str) -> str:
    base = seed[:43].ljust(43, "0")
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % len(weights)] for i, digit in enumerate(base[::-1]))
    remainder = total % 11
    check_digit = 0 if remainder in (0, 1) else 11 - remainder
    return f"{base}{check_digit}"


async def _create_user(username: str, role: str = UserRole.ADMIN) -> str:
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.username == username))
        db.add(
            User(
                username=username,
                email=f"{username}@test.local",
                hashed_password="unused",
                role=role,
                is_active=True,
            )
        )
        await db.commit()
    return create_access_token({"sub": username, "role": role})


async def _create_imported_note(chave: str, suffix: str) -> tuple[str, str]:
    cnpj = f"1745740401{suffix.zfill(4)}"
    ean = f"78920000{suffix.zfill(5)}"
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota=f"60{suffix}",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("19.90"),
        fornecedor=FornecedorDTO(
            cnpj=cnpj,
            razao_social=f"MERCADO ARCHIVE ENDPOINT {suffix} LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao=f"PRODUTO ARCHIVE ENDPOINT {suffix}",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("19.90"),
                valor_total=Decimal("19.90"),
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
                detalhes="Importacao criada para teste de endpoint archive",
            )

    return cnpj, ean


async def _archive_request(chave: str, token: str, motivo: str = "archive operacional de teste"):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            f"/api/v1/notas/{chave}/archive",
            json={"motivo": motivo},
            headers={"Authorization": f"Bearer {token}"},
        )


async def _count_archive_logs(chave: str) -> int:
    async with SessionLocal() as db:
        return await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entidade_id == chave, AuditLog.operacao == "IMPORT_ARCHIVED")
        ) or 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "suffix"),
    [
        (UserRole.ADMIN, "191"),
        (UserRole.MANAGER, "192"),
    ],
)
async def test_archive_endpoint_admin_e_manager_arquivam_nota_ativa(role, suffix):
    chave = _valid_access_key(f"522605174574040011836551100004093512751{suffix}0")
    cnpj, ean = await _create_imported_note(chave, suffix)
    token = await _create_user(f"archive_{role}_{suffix}", role)

    response = await _archive_request(chave, token, motivo="archive operacional de teste")

    assert response.status_code == 200
    body = response.json()
    assert body["mensagem"] == "Importacao arquivada com sucesso."
    assert body["status"] == "archived"
    assert body["chave_acesso"] == f"{chave[:4]}...{chave[-4:]}"
    assert body["archived_by"] == f"archive_{role}_{suffix}"
    assert body["archive_reason"] == "archive operacional de teste"

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

    assert nota.status == "archived"
    assert nota.archived_at is not None
    assert nota.archived_by == f"archive_{role}_{suffix}"
    assert nota.archive_reason == "archive operacional de teste"
    assert fornecedor is not None
    assert produto is not None
    assert len(itens) == 1
    assert len(historicos) == 1
    assert archive_log is not None


@pytest.mark.anyio
async def test_archive_endpoint_usuario_comum_recebe_403():
    chave = _valid_access_key("5226051745740400118365511000040935127511930")
    await _create_imported_note(chave, "193")
    token = await _create_user("archive_operator_193", UserRole.OPERATOR)

    response = await _archive_request(chave, token)

    assert response.status_code == 403
    assert await _count_archive_logs(chave) == 0


@pytest.mark.anyio
async def test_archive_endpoint_rejeita_motivo_invalido():
    chave = _valid_access_key("5226051745740400118365511000040935127511940")
    await _create_imported_note(chave, "194")
    token = await _create_user("archive_admin_194", UserRole.ADMIN)

    response = await _archive_request(chave, token, motivo="    ")

    assert response.status_code == 422
    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
    assert nota.status == "active"


@pytest.mark.anyio
async def test_archive_endpoint_nota_inexistente_retorna_404():
    chave = _valid_access_key("5226051745740400118365511000040935127511950")
    token = await _create_user("archive_admin_195", UserRole.ADMIN)

    response = await _archive_request(chave, token)

    assert response.status_code == 404
    assert response.json()["detail"] == "Importacao nao encontrada."


@pytest.mark.anyio
async def test_archive_endpoint_nota_ja_arquivada_retorna_409():
    chave = _valid_access_key("5226051745740400118365511000040935127511960")
    await _create_imported_note(chave, "196")
    token = await _create_user("archive_admin_196", UserRole.ADMIN)

    first = await _archive_request(chave, token)
    second = await _archive_request(chave, token, motivo="segunda tentativa controlada")

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "Importacao ja arquivada."
    assert await _count_archive_logs(chave) == 1


@pytest.mark.anyio
async def test_archive_endpoint_falha_no_commit_faz_rollback(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511970")
    await _create_imported_note(chave, "197")
    token = await _create_user("archive_admin_197", UserRole.ADMIN)

    async def fail_commit(self):
        raise RuntimeError("falha simulada no commit")

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.commit", fail_commit)

    response = await _archive_request(chave, token)

    assert response.status_code == 500
    assert response.json()["detail"] == "Falha ao arquivar importacao."
    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))

    assert nota.status == "active"
    assert nota.archived_at is None
    assert nota.archived_by is None
    assert nota.archive_reason is None
    assert await _count_archive_logs(chave) == 0
