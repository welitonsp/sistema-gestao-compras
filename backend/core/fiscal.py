"""Fiscal domain logic and validations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse


ImportacaoIdentificadorKind = Literal["plain_access_key", "qrcode_payload", "qrcode_url", "invalid"]


@dataclass(frozen=True)
class ImportacaoIdentificador:
    kind: ImportacaoIdentificadorKind
    original: str
    access_key: str = ""
    qrcode_payload: str = ""
    error_code: str | None = None


def extrair_payload_qrcode_de_url(value: str) -> str:
    parsed = urlparse(value or "")
    params = parse_qs(parsed.query, keep_blank_values=True)
    payloads = params.get("p") or []
    if not payloads:
        return ""
    return unquote(payloads[0])


def extrair_chave_acesso_de_payload_qrcode(payload: str) -> str:
    match = re.search(r"\d{44}", payload or "")
    return match.group(0) if match else ""


def classificar_identificador_importacao(value: str) -> ImportacaoIdentificador:
    original = (value or "").strip()
    if not original:
        return ImportacaoIdentificador(kind="invalid", original=original, error_code="empty_identifier")

    if original.startswith(("http://", "https://")):
        payload = extrair_payload_qrcode_de_url(original)
        if not payload:
            return ImportacaoIdentificador(
                kind="invalid",
                original=original,
                error_code="qrcode_url_missing_payload",
            )
        chave = extrair_chave_acesso_de_payload_qrcode(payload)
        if not chave:
            return ImportacaoIdentificador(
                kind="qrcode_url",
                original=original,
                qrcode_payload=payload,
                error_code="sefaz_qrcode_payload_incomplete",
            )
        return ImportacaoIdentificador(
            kind="qrcode_url",
            original=original,
            access_key=chave,
            qrcode_payload=payload,
        )

    if "|" in original:
        chave = extrair_chave_acesso_de_payload_qrcode(original)
        if not chave:
            return ImportacaoIdentificador(
                kind="qrcode_payload",
                original=original,
                qrcode_payload=original,
                error_code="sefaz_qrcode_payload_incomplete",
            )
        return ImportacaoIdentificador(
            kind="qrcode_payload",
            original=original,
            access_key=chave,
            qrcode_payload=original,
        )

    digits = re.sub(r"\D", "", original)
    if len(digits) == 44:
        return ImportacaoIdentificador(kind="plain_access_key", original=original, access_key=digits)

    return ImportacaoIdentificador(kind="invalid", original=original, error_code="unsupported_identifier")

def validar_chave_acesso(chave: str) -> bool:
    """
    Valida uma chave de acesso de documento fiscal (NF-e/NFC-e) usando o dígito verificador.
    
    A chave deve ter 44 dígitos numéricos.
    """
    chave = re.sub(r"\D", "", chave)
    
    if len(chave) != 44:
        return False
        
    # Cálculo do Dígito Verificador (Módulo 11)
    # Pesos: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4... (da direita para a esquerda)
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    
    # Inverte a chave excluindo o último dígito (o próprio DV)
    chave_base = chave[:-1][::-1]
    
    for i, digito in enumerate(chave_base):
        peso = pesos[i % len(pesos)]
        soma += int(digito) * peso
        
    resto = soma % 11
    dv_calculado = 0 if resto in (0, 1) else 11 - resto
    
    return dv_calculado == int(chave[-1])


def extrair_modelo_fiscal(chave: str) -> str | None:
    """Retorna o modelo do documento (55 para NF-e, 65 para NFC-e)."""
    if len(chave) == 44:
        return chave[20:22]
    return None
