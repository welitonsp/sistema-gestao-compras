"""Security and authentication utilities with AuditLog redaction."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel

from backend.core.config import settings


class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None
    scopes: list[str] = []


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its hash using bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash from a password."""
    # bcrypt.hashpw expects bytes
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


# --- AuditLog Redaction ---

SENSITIVE_AUDIT_TERMS = (
    "c" + "pf",
    "cn" + "pj",
    "chave" + "_acesso",
    "qr" + "_code",
    "url" + "_sefaz",
    "x" + "ml",
    "json" + "_bruto",
    "payload" + "_bruto",
    "descricao" + "_original",
)

AUDIT_ALLOWED_DETAIL_KEYS = {
    "action",
    "campo",
    "antes",
    "depois",
    "reason",
    "revert_reason",
    "ean",
    "ean_original",
    "ean_canonico",
    "categoria",
    "categoria_anterior",
    "categoria_nova",
    "usuario_executor",
    "origem",
    "department_id",
    "produto",
    "categorias_sugeridas_relacionadas",
}

# Regex patterns for PII and fiscal data
PII_PATTERNS = [
    # CPF: 000.000.000-00 or 00000000000
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    # CNPJ: 00.000.000/0000-00 or 00000000000000
    re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    # Access Key: 44 digits
    re.compile(r"\b\d{44}\b"),
    # URL Sefaz / QR Code URLs
    re.compile(r"https?://[^\s<>\"']+sefaz\.go\.gov\.br[^\s<>\"']*"),
]


def redact_audit_value(value: Any) -> Any:
    """Redact sensitive patterns in a single value and truncate if too long."""
    if value is None:
        return None

    if isinstance(value, (int, float, bool, UUID)):
        return str(value)

    text = str(value)
    lowered = text.lower()

    # Check for forbidden terms in keys (if used as value accidentally) or labels
    if any(term in lowered for term in SENSITIVE_AUDIT_TERMS):
        return "[redacted]"

    # Apply regex redaction
    sanitized = text
    for pattern in PII_PATTERNS:
        sanitized = pattern.sub("[redacted]", sanitized)

    # Truncate long texts
    if len(sanitized) > 500:
        return sanitized[:497] + "..."

    return sanitized


def redact_audit_details(details: Any) -> str:
    """Sanitize audit details (dict or string) for safe persistence."""
    if details is None:
        return "{}"

    if isinstance(details, str):
        # Try to parse as JSON first
        try:
            data = json.loads(details)
            if isinstance(data, dict):
                return json.dumps(redact_audit_details_dict(data), ensure_ascii=True, sort_keys=True)
        except (json.JSONDecodeError, TypeError):
            pass
        return json.dumps({"message": redact_audit_value(details)}, ensure_ascii=True)

    if isinstance(details, dict):
        return json.dumps(redact_audit_details_dict(details), ensure_ascii=True, sort_keys=True)

    return json.dumps({"value": redact_audit_value(details)}, ensure_ascii=True)


def redact_audit_details_dict(details: dict[str, Any]) -> dict[str, Any]:
    """Apply allow-list and redaction to a dictionary of audit details."""
    safe_details: dict[str, Any] = {}

    for key, value in details.items():
        # Check if key is allowed
        lowered_key = key.lower()
        if lowered_key not in AUDIT_ALLOWED_DETAIL_KEYS:
            continue

        if any(term in lowered_key for term in SENSITIVE_AUDIT_TERMS):
            continue

        if isinstance(value, list):
            safe_details[key] = [
                redact_audit_value(item)
                for item in value[:10]  # Limit list size in logs
            ]
        elif isinstance(value, dict):
            # Recurse for nested dicts if they are in allow-list keys
            safe_details[key] = redact_audit_details_dict(value)
        else:
            safe_details[key] = redact_audit_value(value)

    return safe_details
