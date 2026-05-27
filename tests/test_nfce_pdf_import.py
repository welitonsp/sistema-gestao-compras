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
    br_decimal,
    build_pdf_deduplication_identity,
    decimal_to_centavos,
    fiscal_year_month,
    is_nfce_detalhada_text,
    parse_nfce_detalhada_text,
)
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


def _synthetic_real_metadata_layout_text(chave: str | None = None) -> str:
    chave = chave or _nfce_key("67676767")
    return f"""
Governo do Estado de Goiás
Chave de Acesso:{chave}Número NF-e:34805
Data de Emissão:27/05/2026 12:00:00-03:00
Dados da NF-e
Modelo
Série
Número
Data de Emissão
Valor Total da Nota Fiscal
65
514
34805
27/05/2026 12:00:00-03:00
39,87
Emitente
CNPJ
Nome / Razão Social
Inscrição Estadual
99.999.999/0001-91
MERCADO SINTETICO METADADOS S.A
12345678
Dados do Emitente
Nome Fantasia
MERCADO SINTETICO FILIAL
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
QR-Code
URL NFC-e: https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}%7C2
"""


def _synthetic_multipagem_nfce_text(chave: str | None = None) -> str:
    chave = chave or _nfce_key("98989898")
    # Itens 1 a 36, depois marcadores, depois itens 37 a 59
    # Total esperado 870,70. 59 itens.
    # Vamos fazer 58 itens de 10,00 e o último de 290,70? 
    # Não, melhor 58 * 10 = 580. 870.70 - 580 = 290.70.
    itens_1_36 = "\n".join([f"{i} PRODUTO TESTE {i} 1,0000 UN 10,00" for i in range(1, 37)])
    itens_37_58 = "\n".join([f"{i} PRODUTO TESTE {i} 1,0000 UN 10,00" for i in range(37, 59)])
    item_59 = "59 PRODUTO TESTE 59 1,0000 UN 290,70"
    
    return f"""
Nota Fiscal do Consumidor Eletrônica
Chave de Acesso: {chave}
Modelo: 65
Série: 1
Número: 123
Data de Emissão: 27/05/2026
Emitente: MERCADO MULTIPAGINA LTDA
CNPJ: 99.999.999/0001-91
Valor Total dos Produtos: 870,70
Valor Total da Nota Fiscal: 870,70

Página 2
Dados dos Produtos e Serviços
{itens_1_36}

Página 3
Totais
ICMS
Dados do Transporte
Formas de Pagamento
{itens_37_58}
{item_59}

Página 4
Valor Total dos Produtos 870,70
Valor Total da NFe 870,70
QR-Code
URL NFC-e: https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}%7C2
"""


def test_detecta_texto_pdf_nfce_detalhado():
    assert is_nfce_detalhada_text(_synthetic_nfce_text()) is True
    assert is_nfce_detalhada_text("recibo comum sem produtos") is False


def test_extrai_metadados_principais():
    chave = _nfce_key("11112222")
    parsed = parse_nfce_detalhada_text(_synthetic_nfce_text(chave))

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


def test_extrai_data_brasileira_com_hora_timezone_e_deriva_ano_mes():
    parsed = parse_nfce_detalhada_text(
        _synthetic_nfce_text(issue_date="09/03/2026 20:51:53-03:00").replace(
            "Data de Emissão:",
            "Data Emissão ",
        )
    )

    assert parsed.data_emissao == date(2026, 3, 9)
    assert parsed.data_emissao.isoformat() == "2026-03-09"
    assert fiscal_year_month(parsed.data_emissao) == "2026-03"


def test_extrai_produtos_multiplas_paginas_com_stop_markers_no_meio():
    chave = _nfce_key("98989898")
    text = _synthetic_multipagem_nfce_text(chave)
    parsed = parse_nfce_detalhada_text(text)

    # Atualmente deve falhar (pegar apenas 36 ou parar no primeiro stop marker)
    # Esperado após o fix: 59 itens
    assert len(parsed.itens) == 59
    assert parsed.item_total == Decimal("870.70")
    assert parsed.valor_total_nota == Decimal("870.70")
    assert parsed.itens[0].numero_item == 1
    assert parsed.itens[-1].numero_item == 59


def test_extrai_produtos_multiplas_paginas_nao_para_mais_em_totais_icms():
    parsed = parse_nfce_detalhada_text(_synthetic_nfce_text())

    assert [item.numero_item for item in parsed.itens] == [1, 2, 3, 4]
    assert [item.descricao for item in parsed.itens] == [
        "ARROZ TIPO 1 C",
        "QUEIJO MUSSARELA",
        "IOGURTE NATURAL",
        "MASSA RAVIOLI",
    ]


def test_extrai_produtos_em_layout_columnar_do_pdfminer():
    parsed = parse_nfce_detalhada_text(_synthetic_columnar_nfce_text())

    assert [item.numero_item for item in parsed.itens] == [1, 2, 3]
    assert [item.descricao for item in parsed.itens] == [
        "ARROZ TIPO 1 C",
        "QUEIJO MUSSARELA",
        "MASSA RAVIOLI",
    ]
    assert [item.quantidade for item in parsed.itens] == [Decimal("3.0000"), Decimal("1.0000"), Decimal("2.0000")]
    assert [item.unidade for item in parsed.itens] == ["UN", "KG", "UN"]
    assert [item.valor_total_item for item in parsed.itens] == [Decimal("11.37"), Decimal("20.00"), Decimal("8.50")]


def test_extrai_metadados_em_layout_real_sem_capturar_labels():
    parsed = parse_nfce_detalhada_text(_synthetic_real_metadata_layout_text())

    assert parsed.emitente == "MERCADO SINTETICO METADADOS S.A"
    assert parsed.emitente != "CNPJ"
    assert parsed.emitente != "Nome / Razão Social"
    assert parsed.modelo == "65"
    assert parsed.serie == "514"
    assert parsed.numero == "34805"
    assert len(parsed.itens) == 3


def test_converte_quantidade_valores_brasileiros_e_soma_itens():
    parsed = parse_nfce_detalhada_text(_synthetic_nfce_text())

    assert parsed.itens[0].quantidade == Decimal("3.0000")
    assert parsed.itens[0].valor_total_item == Decimal("11.37")
    assert br_decimal("1.234,56") == Decimal("1234.56")
    assert decimal_to_centavos(Decimal("55.00")) == 5500
    assert parsed.item_total == Decimal("55.00")
    assert parsed.item_total == parsed.valor_total_produtos


def test_rejeita_texto_nfce_sem_produtos():
    with pytest.raises(ImportacaoSemProdutosError):
        parse_nfce_detalhada_text(_synthetic_nfce_without_products())


def test_pdf_sem_data_emissao_retorna_erro_controlado():
    with pytest.raises(NfcePdfImportError) as exc_info:
        parse_nfce_detalhada_text(_synthetic_nfce_without_issue_date())

    assert exc_info.value.error_code == "missing_issue_date"


def test_identidade_deduplicacao_fallback_inclui_data_emissao():
    identity = build_pdf_deduplication_identity(
        chave_acesso=None,
        data_emissao=date(2026, 3, 9),
        modelo="65",
        serie="514",
        numero="34805",
        cnpj_emitente="99999999000191",
        valor_total_nota=Decimal("807.12"),
    )

    assert identity.startswith("fallback|2026-03-09|65|514|34805|")
    assert "807.12" in identity


def test_aplica_categorizacao_deterministica_nos_produtos():
    parsed = parse_nfce_detalhada_text(_synthetic_nfce_text())
    by_description = {item.descricao: item for item in parsed.itens}

    assert by_description["ARROZ TIPO 1 C"].categoria == "MERCEARIA"
    assert by_description["ARROZ TIPO 1 C"].subcategoria == "ARROZ"
    assert by_description["QUEIJO MUSSARELA"].categoria == "FRIOS E LATICÍNIOS"
    assert by_description["IOGURTE NATURAL"].subcategoria == "IOGURTES"
    assert by_description["MASSA RAVIOLI"].subcategoria == "MASSAS"
    assert {item.origem_categorizacao for item in parsed.itens} == {"deterministica"}


@pytest.mark.anyio
async def test_endpoint_importa_pdf_nfce_sem_sefaz_ou_groq(monkeypatch):
    chave = _nfce_key("22223333")
    token = await _create_user("nfce_pdf_admin")

    async def fail_importar_por_chave(self, *args, **kwargs):
        raise AssertionError("SEFAZ nao deveria ser chamada na importacao por PDF")

    async def fail_extrair_nota(self, *args, **kwargs):
        raise AssertionError("Groq nao deveria ser chamado na importacao por PDF")

    monkeypatch.setattr(
        "backend.services.nfce_pdf_import.extract_text_from_pdf_bytes",
        lambda content: _synthetic_nfce_text(chave, issue_date="09/03/2026 20:51:53-03:00"),
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
    assert body["nota_fiscal"]["extraction_parser_source"] == "deterministic"

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        itens = (await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))).scalars().all()
        historicos = (
            await db.execute(select(HistoricoPreco).where(HistoricoPreco.nota_fiscal_id == nota.id))
        ).scalars().all()

    assert nota is not None
    assert nota.data_emissao == date(2026, 3, 9)
    quality_details = json.loads(nota.extraction_quality_details)
    assert quality_details["details"]["data_emissao"] == "2026-03-09"
    assert quality_details["details"]["ano_mes"] == "2026-03"
    assert len(itens) == 4
    assert all(item.ean.startswith("SEM_EAN_") for item in itens)
    assert len(historicos) == 4
    assert {historico.data_compra for historico in historicos} == {date(2026, 3, 9)}
    assert {historico.nota_fiscal_id for historico in historicos} == {nota.id}
    assert {item.categoria_sugerida_origem for item in itens} == {"deterministica"}


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

    monkeypatch.setattr("backend.services.nfce_pdf_import.extract_text_from_pdf_bytes", lambda content: _synthetic_nfce_without_products(chave))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-pdf-nfce",
            files={"arquivo": ("nfce-vazia.pdf", b"%PDF-sintetico", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert chave not in response.text
    assert await _count(NotaFiscal) == before[NotaFiscal]
    assert await _count(Fornecedor) == before[Fornecedor]
    assert await _count(ItemNotaFiscal) == before[ItemNotaFiscal]
    assert await _count(Produto) == before[Produto]
    assert await _count(HistoricoPreco) == before[HistoricoPreco]
    assert await _count(AuditLog) == before[AuditLog]


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
        monkeypatch.setattr("backend.services.nfce_pdf_import.extract_text_from_pdf_bytes", lambda content: _synthetic_nfce_text(chave))

        await service.importar_pdf_bytes(
            b"%PDF-sintetico",
            filename="nfce-chave-99999999000191.pdf",
            usuario="log_test",
        )
        await db.rollback()

    rendered_logs = "\n".join(messages)
    assert chave not in rendered_logs
    assert "99999999000191" not in rendered_logs
    assert "ARROZ TIPO 1 C" not in rendered_logs
    assert "Nota Fiscal do Consumidor" not in rendered_logs
    assert "item_count=4" in rendered_logs
    assert "quality_status=ok" in rendered_logs
