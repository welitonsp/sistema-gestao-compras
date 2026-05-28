from __future__ import annotations

from scripts.audit_nfce_pdf_parser_dry_run import build_report, mask_access_key, sanitize_text


def test_audit_script_sanitiza_documentos_chave_e_url():
    raw = (
        "Chave 52260412345678000199650010000015221234567890 "
        "CNPJ 12.345.678/0001-99 CPF 123.456.789-09 "
        "URL https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p=payload"
    )

    sanitized = sanitize_text(raw, max_length=240)

    assert "52260412345678000199650010000015221234567890" not in sanitized
    assert "12.345.678/0001-99" not in sanitized
    assert "123.456.789-09" not in sanitized
    assert "https://nfeweb.sefaz.go.gov.br" not in sanitized
    assert "<chave-redigida>" in sanitized
    assert "<cnpj-redigido>" in sanitized
    assert "<cpf-redigido>" in sanitized
    assert "<url-redigida>" in sanitized


def test_audit_report_nao_expoe_chave_completa():
    full_key = "52260412345678000199650010000015221234567890"
    row = {
        "arquivo": "nfce.pdf",
        "numero": "1522",
        "chave": mask_access_key(full_key),
        "data": "2025-03-12",
        "itens": "1",
        "total_produtos": "99.98",
        "item_total": "99.98",
        "total_nota": "74.98",
        "status": "OK",
        "motivo": sanitize_text("Processado sem URL https://example.test/payload", max_length=120),
    }

    report = build_report([row], pdf_dir="NOVAS_NOTAS")

    assert full_key not in report
    assert "5226...7890" in report
    assert "https://example.test/payload" not in report
    assert "<url-redigida>" in report
    assert "- OK: 1" in report
