"""AI-powered structured data extraction service."""

from __future__ import annotations

import json
import time
import asyncio
from typing import Any

from datetime import date
from google import genai
from google.genai import types

from backend.schemas.internal import NotaFiscalDTO, ItemNotaDTO
from core.logger import get_logger
from backend.core.config import settings
from backend.services.ia_groq_utils import buscar_no_cache, salvar_no_cache, extrair_json_com_groq_async, consultar_ia_async, obter_exemplos_verificados
from backend.services.text_sanitizer import sanitize_prompt_categories

logger = get_logger("services.ai")

# Semáforo global para limitar a concorrência nas APIs de IA
_ai_semaphore = asyncio.Semaphore(3)

class AIStructuredExtractor:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model_name = model
        self._client = None

    @property
    def client(self) -> genai.Client:
        """Mantido para compatibilidade, mas o fluxo principal usa Groq agora."""
        if self._client is None:
            if not settings.enable_gemini:
                raise RuntimeError("Gemini desativado: ENABLE_GEMINI=false")
            api_key = settings.gemini_api_key.get_secret_value() if hasattr(settings.gemini_api_key, "get_secret_value") else settings.gemini_api_key
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY nao configurada")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def extrair_nota(
        self,
        texto_limpo: str,
        categorias_contexto: list[str] | None = None,
        department_id=None,
    ) -> NotaFiscalDTO:
        start_time = time.perf_counter()
        logger.info(f"Chamando Groq ({self.model_name}) para extração estruturada.")

        lista_cats = """
        [ALIMENTAÇÃO - GRÃOS E CEREAIS, ALIMENTAÇÃO - MASSAS E MOLHOS, ALIMENTAÇÃO - ÓLEOS E CONDIMENTOS,
         ALIMENTAÇÃO - CAFÉ, CHÁS E ACHOCOLATADOS, PERECÍVEIS - AÇOUGUE E PEIXARIA, PERECÍVEIS - LATICÍNIOS E FRIOS,
         PERECÍVEIS - HORTIFRUTI (FLV), PERECÍVEIS - PADARIA E CONFEITARIA, PERECÍVEIS - CONGELADOS,
         BEBIDAS - NÃO ALCOÓLICAS, BEBIDAS - ALCOÓLICAS, HIGIENE E PERFUMARIA - CUIDADOS PESSOAIS,
         HIGIENE E PERFUMARIA - CABELOS E CORPO, HIGIENE E PERFUMARIA - INFANTIL/BEBÊ, LIMPEZA - LAVANDERIA,
         LIMPEZA - COZINHA E BANHEIRO, LIMPEZA - UTENSÍLIOS E DESCARTÁVEIS, BAZAR E UTILIDADES DOMÉSTICAS,
         PET SHOP, OUTROS]
        """
        exemplos = await obter_exemplos_verificados(limit=10, department_id=department_id)

        prompt_sistema = (
            "Você é um extrator especialista em documentos fiscais brasileiros (NFC-e). "
            "Sua missão é extrair TODOS os dados disponíveis do texto bruto de um portal da SEFAZ. "
            "IMPORTANTE:\n"
            "1. Procure pelo CNPJ e Razão Social do Fornecedor no início do texto.\n"
            "2. Identifique cada ITEM (descrição, quantidade, valor unitário, valor total).\n"
            "3. O formato da 'data_emissao' DEVE ser YYYY-MM-DD.\n"
            "4. Se não encontrar o EAN/Código, gere um código baseado na descrição.\n"
            f"5. Categorias OBRIGATÓRIAS: {lista_cats}.\n\n"
            f"{exemplos}\n\n"
            "Retorne exclusivamente um JSON válido seguindo exatamente este formato:\n"
            "{\n"
            '    "chave_acesso": "44 digitos",\n'
            '    "numero_nota": "string",\n'
            '    "data_emissao": "YYYY-MM-DD",\n'
            '    "valor_total": 0.0,\n'
            '    "fornecedor": {\n'
            '        "cnpj": "apenas numeros",\n'
            '        "razao_social": "string",\n'
            '        "nome_fantasia": "string"\n'
            '    },\n'
            '    "itens": [\n'
            '        {\n'
            '            "ean": "string",\n'
            '            "descricao": "string",\n'
            '            "quantidade": 1.0,\n'
            '            "valor_unitario": 0.0,\n'
            '            "valor_total": 0.0,\n'
            '            "marca": "string",\n'
            '            "categoria": "string"\n'
            '        }\n'
            '    ]\n'
            "}"
        )

        try:
            async with _ai_semaphore:
                dados_brutos = await extrair_json_com_groq_async(
                    conteudo=texto_limpo,
                    prompt_sistema=prompt_sistema,
                    model=self.model_name,
                    max_tokens=8000 # Aumentado para notas longas (60+ itens)
                )

            # Fallback para data se vier vazio
            if not dados_brutos.get("data_emissao"):
                dados_brutos["data_emissao"] = date.today().isoformat()

            dto = NotaFiscalDTO.model_validate(dados_brutos)
            self._marcar_sugestoes_ia(dto.itens)
            duration = time.perf_counter() - start_time
            logger.info(f"Groq respondeu em {duration:.2f}s.")
            return dto
        except Exception as e:
            logger.error(f"Erro na extração via Groq ({self.model_name}): {e}")
            raise

    async def classificar_itens_lote(
        self,
        itens: list[ItemNotaDTO],
        categorias_contexto: list[str],
        department_id=None,
    ) -> list[ItemNotaDTO]:
        """Classifica itens usando Groq."""
        if not itens: return []

        start_time = time.perf_counter()
        categorias_seguras = sanitize_prompt_categories(categorias_contexto)
        lista_cats = ", ".join(categorias_seguras)
        exemplos = await obter_exemplos_verificados(limit=10, department_id=department_id)

        prompt_user = "Classifique os seguintes itens de supermercado:\n"
        for i, item in enumerate(itens):
            prompt_user += f"{i+1}. {item.descricao}\n"

        prompt_sistema = (
            "Para cada item fornecido, retorne a MARCA e a CATEGORIA ideal. "
            f"Categorias permitidas: [{lista_cats}, OUTROS]. "
            f"{exemplos}\n\n"
            "Retorne um JSON no formato: {'classificacoes': [{'marca': '...', 'categoria': '...'}, ...]}"
        )


        try:
            async with _ai_semaphore:
                res = await extrair_json_com_groq_async(
                    conteudo=prompt_user,
                    prompt_sistema=prompt_sistema,
                    model=self.model_name
                )

            classificacoes = res.get("classificacoes", [])
            for i, item in enumerate(itens):
                if i < len(classificacoes):
                    item.marca = classificacoes[i].get("marca", "")
                    item.categoria = classificacoes[i].get("categoria", "OUTROS")
                    item.categoria_sugerida_origem = "groq"
                    item.categoria_sugerida_modelo = self.model_name

            return itens
        except Exception as e:
            logger.error(f"Erro ao classificar via Groq: {e}")
            return itens

    async def classificar_item_manual(self, descricao: str, department_id=None) -> dict:
        """Classifica um único item de texto manual usando Groq com Cache."""
        # 1. Tentar Cache
        cached = await buscar_no_cache(descricao, department_id=department_id)
        if cached:
            return cached

        start_time = time.perf_counter()
        logger.debug(f"Classificando item manual via Groq: {descricao[:30]}...")

        try:
            async with _ai_semaphore:
                resultado = await consultar_ia_async(descricao, department_id=department_id)

            duration = time.perf_counter() - start_time
            logger.info(f"Groq (classificar_item) respondeu em {duration:.2f}s.")
            return resultado
        except Exception as e:
            logger.error(f"Erro ao classificar item manual via Groq: {e}")
            return {"produto": descricao, "marca": "", "categoria": "Outros", "unidade": "un"}

    def _marcar_sugestoes_ia(self, itens: list[ItemNotaDTO]) -> None:
        for item in itens:
            if item.categoria:
                item.categoria_sugerida_origem = "groq"
                item.categoria_sugerida_modelo = self.model_name


async def ai_category_fallback_provider(payload: dict) -> dict | None:
    """Real AI provider for category fallback using Groq/Llama.

    This function is a standalone provider that follows strict safety contracts:
    - Only receives sanitized data.
    - No EAN, PII, or fiscal data.
    - Strict JSON output within an allow-list of categories.
    """
    if not settings.groq_api_key:
        return None

    sanitized_name = payload.get("sanitized_product_name")
    allowed_cats = payload.get("allowed_categories")

    if not sanitized_name or not allowed_cats:
        return None

    prompt_sistema = (
        "Você é um especialista em classificação de produtos de varejo no Brasil.\n"
        "Classifique o produto baseado APENAS no seu nome canônico.\n"
        f"Categorias Permitidas: {allowed_cats}\n\n"
        "Se não for possível determinar com segurança, utilize a categoria 'Outros'.\n"
        "Não crie novas categorias.\n\n"
        "Retorne um JSON estrito no formato:\n"
        "{\n"
        '  "suggested_category": "string (da lista acima)",\n'
        '  "confidence": 0.0 a 1.0 (float),\n'
        '  "reason": "Justificativa curta, até 160 caracteres."\n'
        "}"
    )

    conteudo = f"Produto: {sanitized_name}"

    try:
        # Usamos o semáforo global para respeitar limites de concorrência
        async with _ai_semaphore:
            # Impor timeout de 5 segundos para não travar a UI de candidatos
            response = await asyncio.wait_for(
                extrair_json_com_groq_async(
                    conteudo=conteudo,
                    prompt_sistema=prompt_sistema,
                    model="llama-3.1-8b-instant", # Modelo leve e rápido para classificação
                ),
                timeout=5.0,
            )
        return response
    except Exception as e:
        # Log seguro: apenas tipo de erro, sem dados do payload ou prompt
        logger.warning(f"Falha na chamada ao Groq no Fallback IA: {type(e).__name__}")
        return None
