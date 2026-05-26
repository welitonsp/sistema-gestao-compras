from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from unittest.mock import AsyncMock

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import (
    AuditLog,
    Fornecedor,
    HistoricoPreco,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
    UserRole,
)
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.importador_sefaz import ImportadorSefazService, SefazComunicacaoError
from backend.services.parsers.sefaz_go import SefazGoParser


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


async def _count(model) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model)) or 0


@pytest.mark.anyio
async def test_importacao_por_chave_persiste_nota_fornecedor_e_itens(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511810")
    token = await _create_user("import_admin")

    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40935",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("18.90"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001183",
            razao_social="MERCADO TESTE IMPORTACAO LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="7891000000001",
                descricao="ARROZ TESTE 5KG",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("18.90"),
                valor_total=Decimal("18.90"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )

    async def fake_fetch_url(self, url: str) -> str:
        return "<html>nota fiscal mockada</html>"

    async def fake_classificar_itens_lote(self, itens, categorias_contexto):
        return itens

    monkeypatch.setattr(ImportadorSefazService, "_fetch_url", fake_fetch_url)
    monkeypatch.setattr(SefazGoParser, "parse", lambda self, html: dto)
    monkeypatch.setattr(AIStructuredExtractor, "classificar_itens_lote", fake_classificar_itens_lote)
    app.state.http_client = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    assert response.json()["nota_fiscal"]["chave_acesso"] == chave

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        fornecedor = await db.scalar(select(Fornecedor).where(Fornecedor.cnpj == "17457404001183"))
        itens = (
            await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))
        ).scalars().all()
        produto = await db.scalar(select(Produto).where(Produto.ean == "7891000000001"))
        historico = await db.scalar(select(HistoricoPreco).where(HistoricoPreco.ean == "7891000000001"))
        auditoria = await db.scalar(select(AuditLog).where(AuditLog.entidade_id == chave))

    assert nota is not None
    assert fornecedor is not None
    assert len(itens) == 1
    assert produto is not None
    assert historico is not None
    assert auditoria is not None


@pytest.mark.anyio
async def test_importacao_por_chave_falha_externa_nao_persiste(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511820")
    token = await _create_user("import_failure_admin")
    before = {
        NotaFiscal: await _count(NotaFiscal),
        Fornecedor: await _count(Fornecedor),
        ItemNotaFiscal: await _count(ItemNotaFiscal),
        Produto: await _count(Produto),
        HistoricoPreco: await _count(HistoricoPreco),
        AuditLog: await _count(AuditLog),
    }

    async def fail_fetch_url(self, url: str) -> str:
        raise SefazComunicacaoError("SEFAZ indisponivel no teste")

    monkeypatch.setattr(ImportadorSefazService, "_fetch_url", fail_fetch_url)
    app.state.http_client = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    assert await _count(NotaFiscal) == before[NotaFiscal]
    assert await _count(Fornecedor) == before[Fornecedor]
    assert await _count(ItemNotaFiscal) == before[ItemNotaFiscal]
    assert await _count(Produto) == before[Produto]
    assert await _count(HistoricoPreco) == before[HistoricoPreco]
    assert await _count(AuditLog) == before[AuditLog]
