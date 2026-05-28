from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import (
    AuditLog,
    Department,
    Fornecedor,
    HistoricoPreco,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
    UserRole,
)
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.repository import ProcurementRepository


def _valid_access_key(seed: str) -> str:
    base = seed[:43].ljust(43, "0")
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % len(weights)] for i, digit in enumerate(base[::-1]))
    remainder = total % 11
    check_digit = 0 if remainder in (0, 1) else 11 - remainder
    return f"{base}{check_digit}"


async def _create_user(username: str, role: str = UserRole.ADMIN, department_id: UUID | None = None) -> str:
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.username == username))
        db.add(
            User(
                username=username,
                email=f"{username}@test.local",
                hashed_password="unused",
                role=role,
                is_active=True,
                department_id=department_id,
            )
        )
        await db.commit()
    return create_access_token({"sub": username, "role": role})


async def _create_department(name: str) -> UUID:
    async with SessionLocal() as db:
        existing = await db.scalar(select(Department).where(Department.name == name))
        if existing:
            return existing.id
        department = Department(name=name, description=f"{name} test", is_active=True)
        db.add(department)
        await db.commit()
        return department.id


async def _create_imported_note(
    *,
    chave: str,
    suffix: str,
    ean: str | None = None,
    cnpj: str | None = None,
    department_id: UUID | None = None,
) -> tuple[UUID, str, str]:
    cnpj = cnpj or f"1745740402{suffix.zfill(4)}"
    ean = ean or f"SEM_EAN_DELETE_{suffix.zfill(5)}"
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota=f"70{suffix}",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("21.90"),
        fornecedor=FornecedorDTO(
            cnpj=cnpj,
            razao_social=f"MERCADO DELETE {suffix} LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao=f"PRODUTO DELETE {suffix}",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("21.90"),
                valor_total=Decimal("21.90"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )

    async with SessionLocal() as db:
        async with db.begin():
            repo = ProcurementRepository(db)
            nota = await repo.salvar_nota_completa(chave, dto, department_id=department_id)
            await repo.registrar_auditoria(
                usuario="importador_teste",
                operacao="IMPORT_TEST",
                entidade="NotaFiscal",
                entidade_id=f"{chave[:4]}...{chave[-4:]}",
                detalhes="Importacao criada para teste de delete",
                department_id=department_id,
            )
            nota_id = nota.id

    return nota_id, cnpj, ean


async def _delete_request(nota_id: UUID | str, token: str, motivo: str | None = "exclusao operacional de teste"):
    payload = {} if motivo is None else {"motivo": motivo}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            f"/api/v1/notas/importacoes/{nota_id}/excluir",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )


async def _count(model) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model)) or 0


async def _assert_can_reimport_same_key(chave: str, cnpj: str, ean: str) -> None:
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="70301",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("21.90"),
        fornecedor=FornecedorDTO(
            cnpj=cnpj,
            razao_social="MERCADO DELETE 301 LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao="PRODUTO DELETE 301",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("21.90"),
                valor_total=Decimal("21.90"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )

    async with SessionLocal() as db:
        transaction = await db.begin()
        try:
            repo = ProcurementRepository(db)
            reimported = await repo.salvar_nota_completa(chave, dto)
            await db.flush()
            assert reimported.id is not None
        finally:
            await transaction.rollback()


@pytest.mark.anyio
async def test_delete_endpoint_remove_nota_itens_historicos_e_orfaos_sem_vazar_dados():
    chave = _valid_access_key("5226051745740400118365511000040935127513010")
    nota_id, cnpj, ean = await _create_imported_note(chave=chave, suffix="301")
    token = await _create_user("delete_admin_301")
    before_users = await _count(User)
    before_departments = await _count(Department)

    response = await _delete_request(
        nota_id,
        token,
        motivo=f"remover nota com identificadores {chave} {cnpj} https://example.local/qrcode",
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(nota_id),
        "numero_nota": "70301",
        "status": "deleted",
        "itens_deletados": 1,
        "historico_precos_deletados": 1,
        "produtos_orfaos_deletados": 1,
        "fornecedores_orfaos_deletados": 1,
        "mensagem": "Nota fiscal excluída com sucesso.",
    }
    assert chave not in response.text
    assert cnpj not in response.text

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.id == nota_id))
        nota_por_chave = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        itens = (
            await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota_id))
        ).scalars().all()
        historicos = (
            await db.execute(
                select(HistoricoPreco).where(
                    (HistoricoPreco.nota_fiscal_id == nota_id)
                    | (HistoricoPreco.ean == ean)
                )
            )
        ).scalars().all()
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        fornecedor = await db.scalar(select(Fornecedor).where(Fornecedor.cnpj == cnpj))
        audit_log = await db.scalar(
            select(AuditLog).where(AuditLog.operacao == "IMPORT_DELETED", AuditLog.entidade_id == str(nota_id))
        )

    assert nota is None
    assert nota_por_chave is None
    assert itens == []
    assert historicos == []
    assert produto is None
    assert fornecedor is None
    assert await _count(User) == before_users
    assert await _count(Department) == before_departments
    assert audit_log is not None
    assert audit_log.entidade_id == str(nota_id)
    assert chave not in (audit_log.detalhes or "")
    assert cnpj not in (audit_log.detalhes or "")
    assert "https://example.local/qrcode" not in (audit_log.detalhes or "")
    await _assert_can_reimport_same_key(chave, cnpj, ean)


@pytest.mark.anyio
async def test_delete_endpoint_preserva_produto_usado_por_outra_nota():
    shared_ean = "7892000000302"
    chave_a = _valid_access_key("5226051745740400118365511000040935127513020")
    chave_b = _valid_access_key("5226051745740400118365511000040935127513030")
    nota_id, _, _ = await _create_imported_note(chave=chave_a, suffix="302", ean=shared_ean)
    await _create_imported_note(chave=chave_b, suffix="303", ean=shared_ean)
    token = await _create_user("delete_admin_302")

    response = await _delete_request(nota_id, token)

    assert response.status_code == 200
    body = response.json()
    assert body["produtos_orfaos_deletados"] == 0
    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == shared_ean))
        remaining_items = await db.scalar(
            select(func.count()).select_from(ItemNotaFiscal).where(ItemNotaFiscal.ean == shared_ean)
        )
    assert produto is not None
    assert remaining_items == 1


@pytest.mark.anyio
async def test_delete_endpoint_nota_inexistente_retorna_404():
    token = await _create_user("delete_admin_304")

    response = await _delete_request("00000000-0000-0000-0000-000000000000", token)

    assert response.status_code == 404
    assert response.json()["detail"] == "Importacao nao encontrada."


@pytest.mark.anyio
async def test_delete_endpoint_bloqueia_nota_de_outro_department():
    department_a = await _create_department("delete-dept-a")
    department_b = await _create_department("delete-dept-b")
    chave = _valid_access_key("5226051745740400118365511000040935127513050")
    nota_id, _, _ = await _create_imported_note(chave=chave, suffix="305", department_id=department_a)
    token = await _create_user("delete_admin_305", department_id=department_b)

    response = await _delete_request(nota_id, token)

    assert response.status_code == 404
    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.id == nota_id))
        delete_log = await db.scalar(
            select(AuditLog).where(AuditLog.operacao == "IMPORT_DELETED", AuditLog.entidade_id == str(nota_id))
        )
    assert nota is not None
    assert delete_log is None
