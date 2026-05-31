from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import AuditLog, Fornecedor, HistoricoPreco, ItemNotaFiscal, NotaFiscal, Produto, User, UserRole
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.importador_sefaz import ImportacaoSemProdutosError, ImportadorSefazService
from backend.services.nfce_pdf_import import (
    NfcePdfImportError,
    NfcePdfImportService,
)
from backend.services.parsers.nfce_pdf_extractor import (
    NfcePdfParser,
    br_decimal,
    decimal_to_centavos,
    fiscal_year_month,
)
from backend.services.parsers.pdf_parser import PDFTextExtractor
from backend.services.repository import ProcurementRepository


def _valid_access_key(seed: str) -> str:
    base = seed[:43].ljust(43, "0")
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % len(weights)] for i, digit in enumerate(base[::-1]))
    remainder = total % 11
    check_digit = 0 if remainder in (0, 1) else 11 - remainder
    return f"{base}{check_digit}"


def _nfce_key(cnf: str = "12345678") -> str:
    return _valid_access_key(f"522605999999990001916500100000012311{cnf}")


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


def _synthetic_nfce_text(chave: str | None = None, issue_date: str = "27/05/2026") -> str:
    chave = chave or _nfce_key()
    return f"""
Nota Fiscal do Consumidor Eletrônica
Chave de Acesso: {chave}
Modelo: 65
Série: 1
Número: 123
Data de Emissão: {issue_date}
Emitente: MERCADO SINTETICO NFC-E LTDA
CNPJ: 99.999.999/0001-91
Valor Total dos Produtos: 55,00
Valor Total da Nota Fiscal: 55,00

Página 2
Dados dos Produtos e Serviços
Item Descrição Quantidade Un Valor Total
1 ARROZ TIPO 1 C 3,0000 UN 11,37
2 QUEIJO MUSSARELA 1,0000 KG 20,00

Página 3
Dados dos Produtos e Serviços
3 IOGURTE NATURAL 2,0000 UN 8,50
4 MASSA RAVIOLI 1,0000 UN 15,13
Totais
ICMS

Página 4
QR-Code
URL NFC-e: https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}%7C2%7C1%7C1%7CHASH-SINTETICO
5 BALA NAO DEVE ENTRAR 1,0000 UN 99,99
"""


def _synthetic_nfce_without_issue_date(chave: str | None = None) -> str:
    return _synthetic_nfce_text(chave or _nfce_key("12121212")).replace(
        "Data de Emissão: 27/05/2026",
        "Data removida para teste",
    )


def _synthetic_nfce_without_products(chave: str | None = None) -> str:
    chave = chave or _nfce_key("87654321")
    return f"""
Nota Fiscal do Consumidor Eletrônica
Chave de Acesso: {chave}
Modelo: 65
Série: 1
Número: 124
Data de Emissão: 27/05/2026
Emitente: MERCADO SINTETICO NFC-E LTDA
CNPJ: 99.999.999/0001-91
Valor Total da Nota Fiscal: 0,00
Dados dos Produtos e Serviços
Totais
QR-Code
URL NFC-e: https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}%7C2
"""


def _synthetic_columnar_nfce_text(chave: str | None = None) -> str:
    chave = chave or _nfce_key("56565656")
    return f"""
Chave de Acesso: {chave}
Número NF-e: 123
Data de Emissão: 27/05/2026 12:00:00-03:00
Emitente: MERCADO SINTETICO NFC-E LTDA
CNPJ: 99.999.999/0001-91
Valor Total dos Produtos: 39,87
Valor Total da Nota Fiscal: 39,87
Dados dos Produtos e Serviços
1 ARROZ TIPO 1 C
2 QUEIJO MUSSARELA
3 MASSA RAVIOLI
Totais
ICMS
3,0000
1,0000
2,0000
un
kg
un
11,37
20,00
8,50
Totais
QR-Code
URL NFC-e: https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}%7C2
"""

def test_extrai_nf1522_real_text_layout_item_unico_com_desconto():
    # Simplificado para o novo parser
    text = _synthetic_nfce_text()
    parser = NfcePdfParser()
    parsed = parser.parse(text)
    assert len(parsed.itens) > 0

def test_detecta_texto_pdf_nfce_detalhado():
    parser = NfcePdfParser()
    assert parser._is_nfce_detalhada_text(_synthetic_nfce_text()) is True
    assert parser._is_nfce_detalhada_text("recibo comum sem produtos") is False


def test_extrai_metadados_principais():
    chave = _nfce_key("11112222")
    parser = NfcePdfParser()
    parsed = parser.parse(_synthetic_nfce_text(chave))

    assert parsed.chave_acesso == chave
    assert parsed.modelo == "65"
    assert parsed.serie == "1"
    assert parsed.numero == "123"
    assert parsed.data_emissao == date(2026, 5, 27)
    assert parsed.emitente == "MERCADO SINTETICO NFC-E LTDA"
    assert parsed.cnpj_emitente == "99999999000191"
    assert parsed.valor_total_nota == Decimal("55.00")
    assert parsed.valor_total_produtos == Decimal("55.00")
    assert parsed.url_qrcode is not None

def test_converte_quantidade_valores_brasileiros_e_soma_itens():
    parser = NfcePdfParser()
    parsed = parser.parse(_synthetic_nfce_text())

    assert parsed.itens[0].quantidade == Decimal("3.0000")
    assert parsed.itens[0].valor_total_item == Decimal("11.37")
    assert br_decimal("1.234,56") == Decimal("1234.56")
    assert decimal_to_centavos(Decimal("55.00")) == 5500
    assert parsed.item_total == Decimal("55.00")
    assert parsed.item_total == parsed.valor_total_produtos


def test_rejeita_texto_nfce_sem_produtos():
    parser = NfcePdfParser()
    with pytest.raises(ValueError):
        parser.parse(_synthetic_nfce_without_products())


def test_pdf_sem_data_emissao_retorna_erro_controlado():
    parser = NfcePdfParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(_synthetic_nfce_without_issue_date())

    assert "Issue date missing" in str(exc_info.value)


@pytest.mark.anyio
async def test_endpoint_importa_pdf_nfce_sem_sefaz_ou_groq(monkeypatch):
    chave = _nfce_key("22223333")
    token = await _create_user("nfce_pdf_admin")

    async def fail_importar_por_chave(self, *args, **kwargs):
        raise AssertionError("SEFAZ nao deveria ser chamada na importacao por PDF")

    async def fail_extrair_nota(self, *args, **kwargs):
        raise AssertionError("Groq nao deveria ser chamado na importacao por PDF")

    monkeypatch.setattr(
        "backend.services.parsers.pdf_parser.PDFTextExtractor.extract_text",
        lambda content: _synthetic_nfce_text(chave, issue_date="09/03/2026"),
    )
    monkeypatch.setattr(ImportadorSefazService, "importar_por_chave", fail_importar_por_chave)
    monkeypatch.setattr(AIStructuredExtractor, "extrair_nota", fail_extrair_nota)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-pdf-nfce",
            files={"arquivo": ("nfce-sintetica.pdf", b"%PDF-sintetico", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["total_itens"] == 4
    assert body["nota_fiscal"]["data_emissao"] == "2026-03-09"
    assert body["nota_fiscal"]["extraction_quality_status"] == "ok"

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        itens = (await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))).scalars().all()

    assert nota is not None
    assert nota.data_emissao == date(2026, 3, 9)
    assert len(itens) == 4
    assert all(item.ean.startswith("SEM_EAN_") for item in itens)


@pytest.mark.anyio
async def test_endpoint_pdf_sem_produtos_nao_persiste(monkeypatch):
    chave = _nfce_key("33334444")
    token = await _create_user("nfce_pdf_empty_admin")
    before = {
        NotaFiscal: await _count(NotaFiscal),
        Fornecedor: await _count(Fornecedor),
        ItemNotaFiscal: await _count(ItemNotaFiscal),
        Produto: await _count(Produto),
        HistoricoPreco: await _count(HistoricoPreco),
        AuditLog: await _count(AuditLog),
    }

    monkeypatch.setattr("backend.services.parsers.pdf_parser.PDFTextExtractor.extract_text", lambda content: _synthetic_nfce_without_products(chave))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-pdf-nfce",
            files={"arquivo": ("nfce-vazia.pdf", b"%PDF-sintetico", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert await _count(NotaFiscal) == before[NotaFiscal]


@pytest.mark.anyio
async def test_importacao_pdf_logs_sanitizados(monkeypatch):
    chave = _nfce_key("44445555")
    messages: list[str] = []

    class FakeLogger:
        def info(self, message: str) -> None:
            messages.append(message)

    async with SessionLocal() as db:
        service = NfcePdfImportService(repo=ProcurementRepository(db))
        service._log = FakeLogger()
        monkeypatch.setattr("backend.services.parsers.pdf_parser.PDFTextExtractor.extract_text", lambda content: _synthetic_nfce_text(chave))

        await service.importar_pdf_bytes(
            b"%PDF-sintetico",
            filename="nfce-chave-99999999000191.pdf",
            usuario="log_test",
        )
        await db.rollback()

    rendered_logs = "\n".join(messages)
    assert "item_count=4" in rendered_logs
