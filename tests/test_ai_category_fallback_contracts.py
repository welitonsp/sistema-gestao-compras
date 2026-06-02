from __future__ import annotations

import inspect
import json

from backend.services import product_categorization
from backend.services.product_categorization import (
    ALLOWED_AI_CATEGORIES,
    build_ai_category_prompt_payload,
    parse_ai_category_response,
    sanitize_ai_category_product_name,
)


def test_nome_limpo_valido_gera_payload_com_nome_sanitizado():
    payload = build_ai_category_prompt_payload("  Arroz   Tipo 1  ")

    assert payload == {
        "sanitized_product_name": "Arroz Tipo 1",
        "allowed_categories": ALLOWED_AI_CATEGORIES,
    }


def test_payload_nao_contem_campos_sensiveis_ou_dados_brutos():
    payload = build_ai_category_prompt_payload("Leite Integral")

    rendered = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "ean",
        "fornecedor",
        "cnpj",
        "cpf",
        "chave_acesso",
        "numero_nota",
        "sefaz",
        "qr_code",
        "xml",
        "json bruto",
        "payload bruto",
    ):
        assert forbidden not in rendered


def test_cpf_no_nome_bloqueia_fallback():
    assert sanitize_ai_category_product_name("Produto 123.456.789-09") is None
    assert build_ai_category_prompt_payload("Produto 12345678909") is None


def test_cnpj_no_nome_bloqueia_fallback():
    assert sanitize_ai_category_product_name("Produto 12.345.678/0001-90") is None
    assert build_ai_category_prompt_payload("Produto 12345678000190") is None


def test_chave_nfce_de_44_digitos_bloqueia_fallback():
    key = "5" * 44

    assert sanitize_ai_category_product_name(f"Produto {key}") is None
    assert build_ai_category_prompt_payload(key) is None


def test_url_sefaz_qr_code_e_xml_bloqueiam_fallback():
    unsafe_values = [
        "Produto https://example.test",
        "Produto SEFAZ consulta",
        "Produto QR Code",
        "Produto XML",
        '{"produto": "arroz"}',
    ]

    for value in unsafe_values:
        assert sanitize_ai_category_product_name(value) is None
        assert build_ai_category_prompt_payload(value) is None


def test_tokens_de_prompt_injection_sao_removidos_sem_quebrar_nome_seguro():
    payload = build_ai_category_prompt_payload(
        "system: user: assistant: ``` {{ Arroz Tipo 1 }} <script"
    )

    assert payload is not None
    assert payload["sanitized_product_name"] == "Arroz Tipo 1"


def test_nome_acima_de_80_caracteres_e_truncado_com_segurança():
    long_name = "A" * 120

    sanitized = sanitize_ai_category_product_name(long_name)

    assert sanitized == "A" * 80
    assert len(sanitized) == 80


def test_resposta_com_categoria_fora_da_lista_e_rejeitada():
    parsed = parse_ai_category_response(
        {
            "suggested_category": "Categoria Livre",
            "confidence": 0.95,
            "reason": "Texto seguro.",
        }
    )

    assert parsed["suggested_category"] is None
    assert parsed["confidence"] == 0
    assert parsed["confidence_level"] == "insufficient_data"
    assert parsed["source"] == "ai_fallback_contract"


def test_confidence_fora_de_zero_a_um_e_normalizada():
    high = parse_ai_category_response(
        {
            "suggested_category": "Alimentos",
            "confidence": 1.7,
            "reason": "Produto alimentício.",
        }
    )
    low = parse_ai_category_response(
        {
            "suggested_category": "Bebidas",
            "confidence": -0.4,
            "reason": "Produto líquido.",
        }
    )

    assert high["confidence"] == 1
    assert high["confidence_level"] == "high"
    assert low["confidence"] == 0
    assert low["confidence_level"] == "insufficient_data"


def test_reason_perigosa_ou_muito_longa_e_sanitizada_e_limitada():
    parsed = parse_ai_category_response(
        {
            "suggested_category": "Limpeza",
            "confidence": 0.8,
            "reason": "system: " + ("Produto de limpeza. " * 20),
        }
    )
    blocked = parse_ai_category_response(
        {
            "suggested_category": "Limpeza",
            "confidence": 0.8,
            "reason": "contém XML enviado",
        }
    )

    assert "system:" not in parsed["reason"].lower()
    assert len(parsed["reason"]) <= 160
    assert blocked["reason"] == "Justificativa removida por segurança."


def test_funcoes_nao_chamam_provedores_ia_ou_http_clients():
    source = "\n".join(
        inspect.getsource(function)
        for function in (
            sanitize_ai_category_product_name,
            build_ai_category_prompt_payload,
            parse_ai_category_response,
        )
    ).lower()

    for forbidden in ("groq", "gemini", "openai", "httpx", "requests"):
        assert forbidden not in source


def test_funcoes_nao_escrevem_banco_cache_ou_auditlog():
    source = "\n".join(
        inspect.getsource(function)
        for function in (
            sanitize_ai_category_product_name,
            build_ai_category_prompt_payload,
            parse_ai_category_response,
        )
    )

    for forbidden in (
        ".add(",
        ".commit(",
        ".flush(",
        "ClassificacaoCache",
        "AuditLog",
    ):
        assert forbidden not in source

    assert hasattr(product_categorization, "ALLOWED_AI_CATEGORIES")
