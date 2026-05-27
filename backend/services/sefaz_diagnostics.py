"""Sanitized diagnostics for SEFAZ HTML responses.

The helpers in this module deliberately avoid returning raw HTML, fiscal payloads,
full access keys, CNPJ values, or product text. They are meant for operational
debugging when parsing fails, without creating fixtures or logs with real fiscal data.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from typing import Any

from bs4 import BeautifulSoup


INVALID_PARAMETERS_CLASS = "panel-generic-error-parametros-nao-encon"

KEYWORDS = {
    "captcha": ("captcha", "recaptcha", "hcaptcha"),
    "produtos": ("produto", "produtos"),
    "item": ("item", "itens"),
    "descricao": ("descricao", "descrição"),
    "quantidade": ("quantidade", "qtd", "qtde"),
    "valor": ("valor", "vlr", "total"),
    "erro": ("erro", "error", "falha"),
    "inexistente": ("inexistente", "nao encontrado", "não encontrado", "documento nao encontrado", "documento não encontrado"),
    "expirada": ("expirada", "expirado", "sessao expirada", "sessão expirada"),
    "bloqueio": ("bloqueio", "bloqueado", "acesso negado", "forbidden"),
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", unescape(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _redact_sensitive_text(value: str | None, *, max_length: int = 120) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\d{30,}", "<chave-redigida>", value)
    text = re.sub(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", "<cnpj-redigido>", text)
    text = re.sub(r"\d{8,}", "<numero-redigido>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def _safe_token(value: str | None) -> str | None:
    if not value:
        return None
    token = re.sub(r"[^a-zA-Z0-9_-]", "", value.strip())
    if not token or re.search(r"\d{4,}", token):
        return None
    return token[:40]


def _first_safe_tokens(values: list[str | None], *, limit: int = 12) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _safe_token(value)
        if not token or token in seen:
            continue
        tokens.append(token)
        seen.add(token)
        if len(tokens) >= limit:
            break
    return tokens


def _layout_hints(soup: BeautifulSoup, html: str) -> list[str]:
    hints = []
    checks = {
        "table#tabResult": soup.find("table", id="tabResult") is not None,
        "span.chave": soup.find("span", class_="chave") is not None,
        "input#chaveAcesso": soup.find("input", id="chaveAcesso") is not None,
        "div#aba_produto_1": soup.find("div", id="aba_produto_1") is not None,
        "consulta-completa": "consulta-completa" in html,
        "span.txtTit": soup.find("span", class_="txtTit") is not None,
        "span.RCod": soup.find("span", class_="RCod") is not None,
        "span.Rqtd": soup.find("span", class_="Rqtd") is not None,
        "span.valor": soup.find("span", class_="valor") is not None,
    }
    for label, present in checks.items():
        if present:
            hints.append(label)
    return hints


def summarize_sefaz_html(html: str) -> dict[str, Any]:
    """Return a sanitized structural summary of a SEFAZ HTML response."""

    html = html or ""
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    normalized_text = _normalize_text(page_text)
    title_elem = soup.find("title")
    classes: list[str | None] = []
    ids: list[str | None] = []
    for element in soup.find_all(True):
        ids.append(element.get("id"))
        class_attr = element.get("class") or []
        if isinstance(class_attr, str):
            classes.append(class_attr)
        else:
            classes.extend(class_attr)

    keyword_flags = {
        f"has_{name}_keyword": any(_normalize_text(keyword) in normalized_text for keyword in keywords)
        for name, keywords in KEYWORDS.items()
    }

    return {
        "content_length": len(html),
        "text_length": len(page_text),
        "title": _redact_sensitive_text(title_elem.get_text(" ", strip=True) if title_elem else None),
        **keyword_flags,
        "table_count": len(soup.find_all("table")),
        "row_count": len(soup.find_all("tr")),
        "form_count": len(soup.find_all("form")),
        "script_count": len(soup.find_all("script")),
        "parser_layout_hints": _layout_hints(soup, html),
        "first_classes": _first_safe_tokens(classes),
        "first_ids": _first_safe_tokens(ids),
    }


def summarize_fallback_text(texto_limpo: str, *, html_truncated: bool, clean_text_length: int, text_limit: int) -> dict[str, Any]:
    """Return sanitized metrics for the text sent to the AI fallback."""

    text = texto_limpo or ""
    normalized_text = _normalize_text(text)
    keyword_flags = {
        f"has_{name}_keyword": any(_normalize_text(keyword) in normalized_text for keyword in keywords)
        for name, keywords in KEYWORDS.items()
    }
    return {
        "text_length_sent": len(text),
        "clean_text_length": clean_text_length,
        "html_truncated": html_truncated,
        "text_limit": text_limit,
        **keyword_flags,
    }


def has_minimum_invoice_content(summary: dict[str, Any]) -> bool:
    """Return whether an HTML summary looks worth sending to parser/AI fallback."""

    has_structure = summary.get("table_count", 0) > 0 or summary.get("row_count", 0) > 0
    has_product_words = any(
        summary.get(flag, False)
        for flag in (
            "has_produtos_keyword",
            "has_item_keyword",
            "has_descricao_keyword",
            "has_quantidade_keyword",
        )
    )
    return bool(has_structure or has_product_words)


def classify_sefaz_html_response(summary: dict[str, Any]) -> str | None:
    """Classify obvious SEFAZ error/intermediate pages using only sanitized metrics."""

    classes = set(summary.get("first_classes") or [])
    hints = set(summary.get("parser_layout_hints") or [])
    if INVALID_PARAMETERS_CLASS in classes:
        return "sefaz_invalid_parameters"

    has_product_words = any(
        summary.get(flag, False)
        for flag in (
            "has_produtos_keyword",
            "has_item_keyword",
            "has_descricao_keyword",
            "has_quantidade_keyword",
        )
    )
    has_error_signal = any(
        summary.get(flag, False)
        for flag in (
            "has_captcha_keyword",
            "has_erro_keyword",
            "has_inexistente_keyword",
            "has_expirada_keyword",
            "has_bloqueio_keyword",
        )
    )
    no_table_rows = summary.get("table_count", 0) == 0 and summary.get("row_count", 0) == 0
    sparse_text = summary.get("text_length", 0) < 500

    if has_error_signal and not has_product_words:
        return "sefaz_no_invoice_content"
    if no_table_rows and sparse_text and not has_product_words and not hints:
        return "sefaz_no_invoice_content"

    return None
