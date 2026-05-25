"""AI-powered structured data extraction service."""

from __future__ import annotations

import json
import time
import asyncio
from typing import Any

from backend.schemas.internal import NotaFiscalDTO, ItemNotaDTO
from core.logger import get_logger
from backend.services.ia_groq_utils import extrair_json_com_groq_async, consultar_ia_async

logger = get_logger("services.ai")

# Semáforo global para limitar a concorrência nas APIs de IA, prevenindo HTTP 429 (Rate Limit)
_ai_semaphore = asyncio.Semaphore(3)

class AIStructuredExtractor:
    def __init__(self, model: str = "llama3-70b-8192"):
        self.model = model

    async def extrair_nota(self, texto_limpo: str, categorias_contexto: list[str] | None = None) -> NotaFiscalDTO:
        start_time = time.perf_counter()
        logger.debug(f"Chamando LLM ({self.model}) para extração estruturada.")
        
        lista_cats = ", ".join(categorias_contexto) if categorias_contexto else "ALIMENTOS, LIMPEZA, BEBIDAS, OUTROS"
        
        prompt_sistema = (
            "Você é um extrator especialista em documentos fiscais (NFC-e). "
            "Extraia os dados do fornecedor, nota e itens. "
            "Para cada item, identifique também a MARCA e a CATEGORIA. "
            f"Categorias preferenciais: [{lista_cats}]. "
            "Retorne exclusivamente um JSON seguindo o schema solicitado."
        )
        
        try:
            async with _ai_semaphore:
                dados_brutos = await extrair_json_com_groq_async(
                    conteudo=texto_limpo,
                    prompt_sistema=prompt_sistema,
                    model=self.model
                )
            duration = time.perf_counter() - start_time
            logger.info(f"LLM (extrair_nota) respondeu em {duration:.2f}s.")
            return NotaFiscalDTO.model_validate(dados_brutos)
        except Exception as e:
            logger.error(f"Erro na extração ou validação Pydantic: {e}")
            raise

    async def classificar_itens_lote(self, itens: list[ItemNotaDTO], categorias_contexto: list[str]) -> list[ItemNotaDTO]:
        """Classifica uma lista de itens em uma única chamada de IA para consistência e performance."""
        if not itens: return []
        
        start_time = time.perf_counter()
        lista_cats = ", ".join(categorias_contexto)
        
        prompt_user = "Classifique os seguintes itens de supermercado:\n"
        for i, item in enumerate(itens):
            prompt_user += f"{i+1}. {item.descricao}\n"
            
        prompt_sistema = (
            "Para cada item fornecido, retorne a MARCA e a CATEGORIA ideal. "
            f"Categorias permitidas: [{lista_cats}, OUTROS]. "
            "Retorne um JSON no formato: {'classificacoes': [{'marca': '...', 'categoria': '...'}, ...]}"
        )
        
        try:
            async with _ai_semaphore:
                res = await extrair_json_com_groq_async(
                    conteudo=prompt_user,
                    prompt_sistema=prompt_sistema,
                    model=self.model
                )
            classificacoes = res.get("classificacoes", [])
            
            for i, item in enumerate(itens):
                if i < len(classificacoes):
                    item.marca = classificacoes[i].get("marca", "")
                    item.categoria = classificacoes[i].get("categoria", "OUTROS")
            
            duration = time.perf_counter() - start_time
            logger.info(f"LLM (classificar_itens_lote) processou {len(itens)} itens em {duration:.2f}s.")
            return itens
        except Exception as e:
            logger.error(f"Erro ao classificar itens em lote: {e}")
            return itens

    async def classificar_item_manual(self, descricao: str) -> dict:
        """Classifica um único item de texto manual."""
        start_time = time.perf_counter()
        logger.debug(f"Classificando item manual: {descricao[:30]}...")
        
        try:
            async with _ai_semaphore:
                dados = await consultar_ia_async(descricao)
            duration = time.perf_counter() - start_time
            logger.info(f"LLM (classificar_item) respondeu em {duration:.2f}s.")
            return dados
        except Exception as e:
            logger.error(f"Erro ao classificar item manual: {e}")
            return {"produto": descricao, "marca": "", "categoria": "Outros", "unidade": "un"}
