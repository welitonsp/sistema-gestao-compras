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

    async def extrair_nota(self, texto_limpo: str, categorias_contexto: list[str] | None = None) -> NotaFiscalDTO:
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
        exemplos = await obter_exemplos_verificados(limit=10)

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
                
            duration = time.perf_counter() - start_time
            logger.info(f"Groq respondeu em {duration:.2f}s.")
            return NotaFiscalDTO.model_validate(dados_brutos)
        except Exception as e:
            logger.error(f"Erro na extração via Groq ({self.model_name}): {e}")
            raise

    async def classificar_itens_lote(self, itens: list[ItemNotaDTO], categorias_contexto: list[str]) -> list[ItemNotaDTO]:
        """Classifica itens usando Groq."""
        if not itens: return []

        start_time = time.perf_counter()
        lista_cats = ", ".join(categorias_contexto)
        exemplos = await obter_exemplos_verificados(limit=10)

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
            
            return itens
        except Exception as e:
            logger.error(f"Erro ao classificar via Groq: {e}")
            return itens

    async def classificar_item_manual(self, descricao: str) -> dict:
        """Classifica um único item de texto manual usando Groq com Cache."""
        # 1. Tentar Cache
        cached = await buscar_no_cache(descricao)
        if cached:
            return cached

        start_time = time.perf_counter()
        logger.debug(f"Classificando item manual via Groq: {descricao[:30]}...")
        
        try:
            async with _ai_semaphore:
                resultado = await consultar_ia_async(descricao)
                
            duration = time.perf_counter() - start_time
            logger.info(f"Groq (classificar_item) respondeu em {duration:.2f}s.")
            return resultado
        except Exception as e:
            logger.error(f"Erro ao classificar item manual via Groq: {e}")
            return {"produto": descricao, "marca": "", "categoria": "Outros", "unidade": "un"}
