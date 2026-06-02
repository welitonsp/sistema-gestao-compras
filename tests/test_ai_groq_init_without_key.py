from __future__ import annotations

import importlib
import sys
from unittest.mock import AsyncMock

import pytest

from backend.core.config import settings


GROQ_MODULES = [
    "backend.services.ia_groq_utils",
    "backend.services.ai_processor",
    "backend.main",
]
_MISSING = object()


def _parent_attr(module_name: str):
    parent_name, attr_name = module_name.rsplit(".", 1)
    parent_module = sys.modules.get(parent_name)
    if parent_module is None:
        return parent_name, attr_name, _MISSING
    return parent_name, attr_name, getattr(parent_module, attr_name, _MISSING)


def _remove_groq_modules() -> None:
    for module_name in GROQ_MODULES:
        sys.modules.pop(module_name, None)


@pytest.fixture
def groq_key_absent(monkeypatch):
    original_modules = {
        module_name: sys.modules.get(module_name, _MISSING)
        for module_name in GROQ_MODULES
    }
    original_parent_attrs = {
        module_name: _parent_attr(module_name)
        for module_name in GROQ_MODULES
    }
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(settings, "groq_api_key", None)
    _remove_groq_modules()
    yield
    for module_name, module in original_modules.items():
        if module is _MISSING:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = module
    for _module_name, (parent_name, attr_name, attr_value) in original_parent_attrs.items():
        parent_module = sys.modules.get(parent_name)
        if parent_module is None:
            continue
        if attr_value is _MISSING:
            if hasattr(parent_module, attr_name):
                delattr(parent_module, attr_name)
        else:
            setattr(parent_module, attr_name, attr_value)


def test_import_ia_groq_utils_without_groq_api_key_does_not_raise(groq_key_absent):
    module = importlib.import_module("backend.services.ia_groq_utils")

    assert hasattr(module, "get_async_groq_client")


def test_import_ai_processor_without_groq_api_key_does_not_raise(groq_key_absent):
    module = importlib.import_module("backend.services.ai_processor")

    assert hasattr(module, "AIStructuredExtractor")


def test_import_backend_main_without_groq_api_key_does_not_raise(groq_key_absent):
    module = importlib.import_module("backend.main")

    assert module.app is not None


@pytest.mark.asyncio
async def test_ai_category_fallback_provider_without_key_returns_none_and_skips_groq(
    groq_key_absent, monkeypatch
):
    ai_processor = importlib.import_module("backend.services.ai_processor")
    groq_call = AsyncMock()
    monkeypatch.setattr(ai_processor, "extrair_json_com_groq_async", groq_call)

    result = await ai_processor.ai_category_fallback_provider(
        {"sanitized_product_name": "Arroz", "allowed_categories": ["Alimentos"]}
    )

    assert result is None
    groq_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_groq_json_call_without_key_fails_only_when_called_and_safely(
    groq_key_absent,
):
    ia_groq_utils = importlib.import_module("backend.services.ia_groq_utils")

    with pytest.raises(ia_groq_utils.GroqNotConfiguredError) as exc_info:
        await ia_groq_utils.extrair_json_com_groq_async(
            conteudo="conteudo sanitizado",
            prompt_sistema="retorne JSON",
        )

    message = str(exc_info.value)
    assert "GROQ_API_KEY not configured" == message
    assert "fake_key" not in message
    assert "conteudo sanitizado" not in message
    assert "retorne JSON" not in message


@pytest.mark.asyncio
async def test_real_groq_classification_call_without_key_fails_controlled_without_network(
    groq_key_absent, monkeypatch
):
    ia_groq_utils = importlib.import_module("backend.services.ia_groq_utils")
    monkeypatch.setattr(ia_groq_utils, "buscar_no_cache", AsyncMock(return_value=None))

    with pytest.raises(ia_groq_utils.GroqNotConfiguredError) as exc_info:
        await ia_groq_utils.consultar_ia_async("ARROZ TESTE")

    assert str(exc_info.value) == "GROQ_API_KEY not configured"


@pytest.mark.asyncio
async def test_enable_ai_false_does_not_invoke_ai_fallback(groq_key_absent, monkeypatch):
    from backend.services import product_categorization

    apply_ai = AsyncMock()
    monkeypatch.setattr(product_categorization, "_apply_ai_fallback_preview", apply_ai)

    class EmptyResult:
        def fetchall(self):
            return []

    class EmptyDb:
        async def execute(self, _stmt):
            return EmptyResult()

    response = await product_categorization.get_category_suggestion_candidates(
        db=EmptyDb(),
        enable_ai=False,
        ai_provider=AsyncMock(),
    )

    assert response.total_candidates == 0
    apply_ai.assert_not_awaited()
