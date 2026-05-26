from __future__ import annotations

import re
import unicodedata


SAFE_LABEL_PATTERN = re.compile(r"^[^\W_][\wÀ-ÿ0-9\s\-/&]*$", re.UNICODE)
PROMPT_TOKEN_PATTERN = re.compile(r"(```|[<>{}\[\]\"'`]|-->|<!--|#|;|\\|\||\n|\r|\t)")


class UnsafeLabelError(ValueError):
    """Raised when user-controlled catalog text is unsafe for persistence or prompts."""


def normalize_label_text(value: str | None, *, max_length: int = 80) -> str | None:
    if value is None:
        return None

    normalized = unicodedata.normalize("NFKC", value)
    if PROMPT_TOKEN_PATTERN.search(normalized):
        raise UnsafeLabelError("Texto contem caracteres nao permitidos.")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise UnsafeLabelError(f"Texto deve ter no maximo {max_length} caracteres.")
    if not SAFE_LABEL_PATTERN.fullmatch(normalized):
        raise UnsafeLabelError("Texto contem caracteres nao permitidos.")
    return normalized


def sanitize_manual_category(value: str | None) -> str | None:
    return normalize_label_text(value, max_length=80)


def sanitize_manual_brand(value: str | None) -> str | None:
    return normalize_label_text(value, max_length=80)


def sanitize_prompt_category(value: str | None) -> str | None:
    try:
        return normalize_label_text(value, max_length=80)
    except UnsafeLabelError:
        return None


def sanitize_prompt_categories(values: list[str], *, limit: int = 40, max_total_length: int = 1200) -> list[str]:
    sanitized: list[str] = []
    seen: set[str] = set()
    total_length = 0

    for value in values:
        label = sanitize_prompt_category(value)
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        projected_total = total_length + len(label)
        if len(sanitized) >= limit or projected_total > max_total_length:
            break
        sanitized.append(label)
        seen.add(key)
        total_length = projected_total

    return sanitized
