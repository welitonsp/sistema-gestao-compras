"""Utilities for safe CSV exports."""

from __future__ import annotations

from typing import Any


CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")


def sanitize_csv_cell(value: Any) -> str:
    """Normalize a CSV cell and prevent spreadsheet formula execution."""
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\r", " ").replace("\n", " ").replace(";", ",")

    stripped = text.strip()
    if stripped and stripped[0] in CSV_INJECTION_PREFIXES:
        return f"'{text}"
    return text
