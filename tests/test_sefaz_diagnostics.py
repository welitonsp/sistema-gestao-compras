from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from backend.core.fiscal import classificar_identificador_importacao
from backend.services.importador_sefaz import (
    AI_FALLBACK_TEXT_LIMIT,
    ImportadorSefazService,
    SefazConsultaInvalidaError,
    build_sefaz_go_query_strategy,
    is_access_key_44_digits,
    is_qrcode_payload,
)
from backend.services.parsers.sefaz_go import SefazGoParser
from backend.services.sefaz_diagnostics import (
    classify_sefaz_html_response,
    summarize_fallback_text,
    summarize_sefaz_html,
)


HTML_ROOT = Path(__file__).parent / "fixtures" / "sefaz" / "html"
SYNTHETIC_KEY = "52260517457404001183655110000409351275197600"
SYNTHETIC_QRCODE_PAYLOAD = f"{SYNTHETIC_KEY}|2|1|1|ABCD1234"


def test_summarize_sefaz_html_detecta_bloqueio_captcha_sem_expor_dados_fiscais():
    html = (HTML_ROOT / "nfe_bloqueio_captcha.html").read_text(encoding="utf-8")
    summary = summarize_sefaz_html(html)

    assert summary["content_length"] == len(html)
    assert summary["title"] == "Consulta NFC-e - validação de acesso"
    assert summary["has_captcha_keyword"] is True
    assert summary["has_inexistente_keyword"] is True
    assert summary["has_expirada_keyword"] is True
    assert summary["table_count"] == 1
    assert summary["row_count"] == 1
    assert summary["form_count"] == 1
    assert "consulta-publica" in summary["first_ids"]
    assert "captcha-form" in summary["first_ids"]
    assert "bloqueio" in summary["first_classes"]
    assert classify_sefaz_html_response(summary) == "sefaz_no_invoice_content"

    rendered = repr(summary)
    assert "5226051745740400118365511000040935127519760" not in rendered
    assert "93000000810001" not in rendered


def test_summarize_sefaz_html_redige_chave_e_numeros_longos_no_title_e_tokens():
    chave = "5226051745740400118365511000040935127519760"
    html = f"""
    <html>
      <head><title>Consulta {chave} fornecedor 93000000810001</title></head>
      <body><div id="linha-{chave}" class="produto item-12345678">Produto Valor</div></body>
    </html>
    """

    summary = summarize_sefaz_html(html)
    rendered = repr(summary)

    assert chave not in rendered
    assert "93000000810001" not in rendered
    assert summary["title"] == "Consulta <chave-redigida> fornecedor <cnpj-redigido>"
    assert summary["first_ids"] == []
    assert summary["first_classes"] == ["produto"]


def test_parser_nao_retorna_sucesso_para_pagina_de_bloqueio_captcha():
    html = (HTML_ROOT / "nfe_bloqueio_captcha.html").read_text(encoding="utf-8")

    assert SefazGoParser().parse(html) is None


def test_diagnostico_do_texto_fallback_mostra_se_conteudo_util_chega_ao_groq():
    html = (HTML_ROOT / "nfe_bloqueio_captcha.html").read_text(encoding="utf-8")
    service = ImportadorSefazService(db=None, http_client=None)
    texto_limpo, html_truncated, clean_text_length = service._limpar_html_com_metadados(html)

    summary = summarize_fallback_text(
        texto_limpo,
        html_truncated=html_truncated,
        clean_text_length=clean_text_length,
        text_limit=AI_FALLBACK_TEXT_LIMIT,
    )

    assert summary["text_length_sent"] == len(texto_limpo)
    assert summary["clean_text_length"] == clean_text_length
    assert summary["html_truncated"] is False
    assert summary["has_captcha_keyword"] is True
    assert summary["has_inexistente_keyword"] is True
    assert summary["has_produtos_keyword"] is False
    assert summary["has_quantidade_keyword"] is False


def test_chave_44_digitos_nao_e_tratada_como_payload_qrcode():
    strategy = build_sefaz_go_query_strategy(SYNTHETIC_KEY)

    assert is_access_key_44_digits(SYNTHETIC_KEY) is True
    assert is_qrcode_payload(SYNTHETIC_KEY) is False
    assert strategy.kind == "access_key"
    assert strategy.url == ""
    assert strategy.error_code == "plain_access_key_not_supported_for_go"
    assert "/sites/nfce/danfeNFCe" not in strategy.url


def test_payload_qrcode_com_pipes_e_urlencoded():
    strategy = build_sefaz_go_query_strategy(SYNTHETIC_QRCODE_PAYLOAD)

    assert is_qrcode_payload(SYNTHETIC_QRCODE_PAYLOAD) is True
    assert strategy.kind == "qrcode_payload"
    assert strategy.chave_acesso == SYNTHETIC_KEY
    assert "%7C" in strategy.url
    assert "|" not in strategy.url
    assert strategy.url.endswith(f"p={SYNTHETIC_KEY}%7C2%7C1%7C1%7CABCD1234")


def test_payload_qrcode_em_url_e_normalizado_e_urlencoded():
    url = f"https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={SYNTHETIC_KEY}%7C2%7C1%7C1%7CABCD1234"

    strategy = build_sefaz_go_query_strategy(url)

    assert strategy.kind == "qrcode_payload"
    assert strategy.chave_acesso == SYNTHETIC_KEY
    assert "%7C" in strategy.url


def test_url_qrcode_classifica_e_extrai_payload_sem_juntar_parametros():
    url = f"https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={SYNTHETIC_KEY}%7C2%7C1%7C1%7CABCD1234"

    classificacao = classificar_identificador_importacao(url)

    assert classificacao.kind == "qrcode_url"
    assert classificacao.access_key == SYNTHETIC_KEY
    assert classificacao.qrcode_payload == SYNTHETIC_QRCODE_PAYLOAD
    assert classificacao.access_key != f"{SYNTHETIC_KEY}211"


def test_url_qrcode_sem_parametro_p_retorna_classificacao_invalida_sem_payload():
    url = "https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?x=1"

    classificacao = classificar_identificador_importacao(url)
    strategy = build_sefaz_go_query_strategy(url)

    assert classificacao.kind == "invalid"
    assert classificacao.error_code == "qrcode_url_missing_payload"
    assert strategy.error_code == "qrcode_url_missing_payload"


def test_html_parametros_nao_encontrados_classifica_falha_tecnica_sem_chave():
    html = f"""
    <html>
      <head><title>Nota Fiscal Eletronica {SYNTHETIC_KEY}</title></head>
      <body>
        <div class="panel-generic-error-parametros-nao-encon">Parametros nao encontrados</div>
        <script>var chave = "{SYNTHETIC_KEY}";</script>
      </body>
    </html>
    """

    summary = summarize_sefaz_html(html)

    assert classify_sefaz_html_response(summary) == "sefaz_invalid_parameters"
    assert SYNTHETIC_KEY not in repr(summary)


def test_html_sem_tabelas_linhas_ou_keywords_nao_deve_ir_para_groq():
    html = "<html><head><title>Nota Fiscal Eletronica</title></head><body>Consulta indisponivel</body></html>"
    summary = summarize_sefaz_html(html)

    assert summary["table_count"] == 0
    assert summary["row_count"] == 0
    assert summary["has_produtos_keyword"] is False
    assert classify_sefaz_html_response(summary) == "sefaz_no_invoice_content"


def test_html_sintetico_com_produtos_continua_extraindo_itens():
    html = (HTML_ROOT / "nfe_valida_multiplos_itens.html").read_text(encoding="utf-8")
    summary = summarize_sefaz_html(html)
    dto = SefazGoParser().parse(html)

    assert classify_sefaz_html_response(summary) is None
    assert dto is not None
    assert len(dto.itens) >= 1


@pytest.mark.asyncio
async def test_pagina_parametros_invalidos_nao_chama_fallback_ia():
    html = """
    <html>
      <head><title>Nota Fiscal Eletronica</title></head>
      <body><div class="panel-generic-error-parametros-nao-encon">Parametros nao encontrados</div></body>
    </html>
    """

    class FakeClient:
        async def get(self, url: str, **kwargs):
            return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    class RepoStub:
        async def obter_categorias_unicas(self):
            return []

        async def nota_existe(self, chave_acesso: str, **kwargs):
            return False
    class AiStub:
        async def extrair_nota(self, *args, **kwargs):
            raise AssertionError("fallback IA nao deveria ser chamado")

        async def classificar_itens_lote(self, *args, **kwargs):
            raise AssertionError("classificacao IA nao deveria ser chamada")

    service = ImportadorSefazService(db=None, http_client=FakeClient())
    service.repo = RepoStub()
    service.ai = AiStub()

    with pytest.raises(SefazConsultaInvalidaError) as exc_info:
        await service.importar_por_chave(SYNTHETIC_QRCODE_PAYLOAD)

    assert exc_info.value.error_code == "sefaz_invalid_parameters"
    assert SYNTHETIC_KEY not in str(exc_info.value)
