from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.parsers.sefaz_go import SefazGoParser
from tests.helpers.sefaz_quality import build_extraction_quality


FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "sefaz"
HTML_ROOT = FIXTURES_ROOT / "html"
EXPECTED_ROOT = FIXTURES_ROOT / "expected"

DETERMINISTIC_CASES = [
    "nfe_valida_multiplos_itens",
    "nfe_sem_ean",
    "nfe_com_desconto",
    "nfe_layout_alternativo",
]


def _load_html(case_name: str) -> str:
    return (HTML_ROOT / f"{case_name}.html").read_text(encoding="utf-8")


def _load_expected(case_name: str) -> dict:
    return json.loads((EXPECTED_ROOT / f"{case_name}.json").read_text(encoding="utf-8"))


def _assert_dto_matches_expected(dto: NotaFiscalDTO, expected: dict) -> None:
    assert dto.chave_acesso == expected["chave_acesso"]
    assert dto.numero_nota == expected["numero_nota"]
    assert dto.fornecedor.cnpj == expected["fornecedor"]["cnpj"]
    assert dto.fornecedor.razao_social == expected["fornecedor"]["razao_social"]
    assert dto.data_emissao.isoformat() == expected["data_emissao"]
    assert dto.valor_total == Decimal(expected["valor_total"])
    assert len(dto.itens) == expected["expected_item_count"]

    for item, expected_item in zip(dto.itens, expected["itens"], strict=True):
        assert item.codigo_produto == expected_item["ean"]
        assert item.descricao == expected_item["descricao"]
        assert item.quantidade == Decimal(expected_item["quantidade"])
        assert item.valor_unitario == Decimal(expected_item["valor_unitario"])
        assert item.valor_total == Decimal(expected_item["valor_total"])
        assert item.categoria == expected_item["categoria"]


async def _extract_with_mocked_fallback(html: str) -> tuple[NotaFiscalDTO, str]:
    parser = SefazGoParser()
    dto = parser.parse(html)
    if dto:
        return dto, "deterministic"

    ai = AIStructuredExtractor()
    fallback_dto = await ai.extrair_nota(html, categorias_contexto=[])
    return fallback_dto, "ai_fallback"


@pytest.mark.parametrize("case_name", DETERMINISTIC_CASES)
def test_parser_deterministico_extrai_fixture_sintetica_com_quality_score(case_name: str):
    expected = _load_expected(case_name)
    dto = SefazGoParser().parse(_load_html(case_name))

    assert dto is not None
    _assert_dto_matches_expected(dto, expected)

    quality = build_extraction_quality(dto, expected, parser_source="deterministic")
    assert quality.item_count == expected["expected_item_count"]
    assert quality.extracted_item_count == expected["expected_item_count"]
    assert quality.missing_ean_count == expected["expected_missing_ean_count"]
    assert quality.empty_description_count == 0
    assert quality.invalid_quantity_count == 0
    assert quality.invalid_value_count == 0
    assert quality.total_itens == Decimal(expected["expected_sum_itens"])
    assert quality.total_nota == Decimal(expected["valor_total"])
    assert quality.total_mismatch is expected["expected_total_mismatch"]
    assert quality.parser_source == expected["expected_parser_source"]
    assert quality.quality_status == expected["expected_quality_status"]


def test_produto_sem_ean_recebe_identificador_controlado():
    expected = _load_expected("nfe_sem_ean")
    dto = SefazGoParser().parse(_load_html("nfe_sem_ean"))

    assert dto is not None
    assert dto.itens[0].codigo_produto == "SEM_EAN_08FDEAB69FAA"
    assert dto.itens[0].codigo_produto == expected["itens"][0]["ean"]


def test_layout_alternativo_nao_quebra_silenciosamente():
    expected = _load_expected("nfe_layout_alternativo")
    dto = SefazGoParser().parse(_load_html("nfe_layout_alternativo"))

    assert dto is not None
    assert dto.itens
    assert dto.itens[0].descricao == expected["itens"][0]["descricao"]


@pytest.mark.anyio
async def test_fallback_ia_groq_mockado_sem_chamada_real(monkeypatch):
    case_name = "nfe_parser_falha_ai_fallback"
    expected = _load_expected(case_name)
    fallback_called = False

    async def fake_extrair_nota(self, texto_limpo: str, categorias_contexto=None):
        nonlocal fallback_called
        fallback_called = True
        return NotaFiscalDTO(
            chave_acesso=expected["chave_acesso"],
            numero_nota=expected["numero_nota"],
            data_emissao=expected["data_emissao"],
            valor_total=Decimal(expected["valor_total"]),
            fornecedor=FornecedorDTO(**expected["fornecedor"]),
            itens=[
                ItemNotaDTO(
                    ean=item["ean"],
                    descricao=item["descricao"],
                    quantidade=Decimal(item["quantidade"]),
                    valor_unitario=Decimal(item["valor_unitario"]),
                    valor_total=Decimal(item["valor_total"]),
                    categoria=item["categoria"],
                    categoria_sugerida_origem="groq",
                    categoria_sugerida_modelo="mock-groq",
                )
                for item in expected["itens"]
            ],
        )

    monkeypatch.setattr(AIStructuredExtractor, "extrair_nota", fake_extrair_nota)

    assert SefazGoParser().parse(_load_html(case_name)) is None
    dto, parser_source = await _extract_with_mocked_fallback(_load_html(case_name))

    assert fallback_called is True
    _assert_dto_matches_expected(dto, expected)
    quality = build_extraction_quality(dto, expected, parser_source=parser_source)
    assert quality.parser_source == "ai_fallback"
    assert quality.quality_status == "ok"


def test_fixtures_sefaz_sao_sinteticas_e_sem_dados_fiscais_reais():
    expected_keys = {
        _load_expected(path.stem)["chave_acesso"]
        for path in EXPECTED_ROOT.glob("*.json")
    }

    for path in [*HTML_ROOT.glob("*.html"), *EXPECTED_ROOT.glob("*.json")]:
        text = path.read_text(encoding="utf-8")
        assert "nfeweb.sefaz.go.gov.br" not in text
        assert "<?xml" not in text.lower()
        assert "MERCADO SINTETICO" in text or path.name == "nfe_parser_falha_ai_fallback.html"
        for chave in re.findall(r"\d{44}", text):
            assert chave in expected_keys
