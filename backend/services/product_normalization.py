"""Strong product-name normalization helpers for catalog canonization preview."""

from __future__ import annotations

import re
import unicodedata


_PUNCTUATION_RE = re.compile(r"[^a-z0-9\s]")
_SPACES_RE = re.compile(r"\s+")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def strong_normalize_product_name(name: str | None) -> str:
    """Normalize product names for conservative deterministic fuzzy matching."""

    if not name:
        return ""

    value = _strip_accents(str(name)).lower()
    value = re.sub(r"\btp\s*(\d+)\b", r" tipo \1 ", value)
    value = re.sub(r"\bc\s*/\s*(\d+)\b", r" com \1 ", value)
    value = re.sub(r"\bc\s+(\d+)\b", r" com \1 ", value)

    value = re.sub(r"(\d+)\s*(kg|kgs|kilo|kilos|quilo|quilos)\b", r"\1 kg", value)
    value = re.sub(r"\bk\s+g\b", "kg", value)
    value = re.sub(r"\b(kgs?|kilos?|quilos?)\b", "kg", value)

    value = re.sub(r"(\d+)\s*(ml)\b", r"\1 ml", value)
    value = re.sub(r"\b(mls)\b", "ml", value)

    value = re.sub(r"(\d+)\s*(lt|lts|litro|litros|l)\b", r"\1 l", value)
    value = re.sub(r"\b(lt|lts|litro|litros)\b", "l", value)

    value = re.sub(r"(\d+)\s*(gr|g)\b", r"\1 g", value)
    value = re.sub(r"\b(gr|grama|gramas)\b", "g", value)

    value = re.sub(r"\b(und|unid|unidade|unidades)\b", "un", value)
    value = re.sub(r"\b(pct|pcte|pacote|pacotes)\b", "pct", value)
    value = re.sub(r"\b(cx|caixa|caixas)\b", "cx", value)

    value = _PUNCTUATION_RE.sub(" ", value)
    value = _SPACES_RE.sub(" ", value).strip()
    return value
