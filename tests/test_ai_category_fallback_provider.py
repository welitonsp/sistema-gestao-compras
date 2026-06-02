from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.config import settings
from backend.services import product_categorization
from backend.services.ai_processor import ai_category_fallback_provider


@pytest.mark.asyncio
async def test_ai_fallback_provider_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    payload = {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    result = await ai_category_fallback_provider(payload)
    assert result is None


@pytest.mark.asyncio
async def test_ai_fallback_provider_returns_none_when_payload_incomplete(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "fake-key")
    payloads = [
        {"sanitized_product_name": None, "allowed_categories": ["Alimentos"]},
        {"sanitized_product_name": "Arroz", "allowed_categories": None},
        {},
    ]
    for p in payloads:
        assert await ai_category_fallback_provider(p) is None


@pytest.mark.asyncio
async def test_ai_fallback_provider_returns_json_on_success(monkeypatch):
    mock_response = {
        "suggested_category": "Alimentos",
        "confidence": 0.9,
        "reason": "Produto alimentício básico.",
    }

    async def mock_extrair(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(
        "backend.services.ai_processor.extrair_json_com_groq_async", mock_extrair
    )
    monkeypatch.setattr(settings, "groq_api_key", "fake-key")

    payload = {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    result = await ai_category_fallback_provider(payload)

    assert result == mock_response


@pytest.mark.asyncio
async def test_ai_fallback_provider_handles_timeout(monkeypatch):
    async def mock_extrair_long(*args, **kwargs):
        await asyncio.sleep(6.0)
        return {"too": "late"}

    monkeypatch.setattr(
        "backend.services.ai_processor.extrair_json_com_groq_async", mock_extrair_long
    )
    monkeypatch.setattr(settings, "groq_api_key", "fake-key")

    payload = {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    # O timeout do wait_for (5.0s) deve disparar
    result = await ai_category_fallback_provider(payload)
    assert result is None


@pytest.mark.asyncio
async def test_ai_fallback_provider_handles_exception(monkeypatch):
    async def mock_extrair_error(*args, **kwargs):
        raise ValueError("Groq connection failed")

    monkeypatch.setattr(
        "backend.services.ai_processor.extrair_json_com_groq_async", mock_extrair_error
    )
    monkeypatch.setattr(settings, "groq_api_key", "fake-key")

    payload = {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    result = await ai_category_fallback_provider(payload)
    assert result is None


@pytest.mark.asyncio
async def test_ai_integration_in_categorization_preview(monkeypatch):
    # Testar que get_ai_category_suggestion_preview realmente chama ai_category_fallback_provider
    mock_provider = AsyncMock(return_value={"test": "ok"})
    monkeypatch.setattr(
        "backend.services.ai_processor.ai_category_fallback_provider", mock_provider
    )

    payload = {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    result = await product_categorization.get_ai_category_suggestion_preview(payload)

    assert result == {"test": "ok"}
    mock_provider.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_provider_receives_only_sanitized_data(monkeypatch):
    captured_payload = {}

    async def mock_extrair(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = {"conteudo": kwargs.get("conteudo"), "sistema": kwargs.get("prompt_sistema")}
        return {"suggested_category": "Alimentos", "confidence": 1.0, "reason": "ok"}

    monkeypatch.setattr(
        "backend.services.ai_processor.extrair_json_com_groq_async", mock_extrair
    )
    monkeypatch.setattr(settings, "groq_api_key", "fake-key")

    payload = {
        "sanitized_product_name": "Arroz Seguro",
        "allowed_categories": ["Alimentos", "Limpeza"],
    }
    await ai_category_fallback_provider(payload)

    assert "Arroz Seguro" in captured_payload["conteudo"]
    assert "Alimentos" in captured_payload["sistema"]
    assert "Limpeza" in captured_payload["sistema"]
    # Garantir que não há vazamento de dados sensíveis que NÃO deveriam estar no payload
    for forbidden in ["ean", "cnpj", "cpf", "chave", "sefaz"]:
        assert forbidden not in str(captured_payload).lower()
