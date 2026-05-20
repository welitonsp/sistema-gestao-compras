"""AI-powered structured data extraction service."""

from __future__ import annotations

import json
import time
from typing import Any

from backend.schemas.internal import NotaFiscalDTO
from core.logger import get_logger
from ia_groq_utils import extrair_json_com_groq_async, consultar_ia_async

logger = get_logger("services.ai")

class AIStructuredExtractor:
    def __init__(self, model: str = "llama3-70b-8192"):
        self.model = model

    async def extrair_nota(self, texto_limpo: str) -> NotaFiscalDTO:
        start_time = time.perf_counter()
        logger.debug(f"Chamando LLM ({self.model}) para extração estruturada.")
        
        prompt_sistema = (
            "Você é um extrator especialista em documentos fiscais (NFC-e). "
            "Retorne exclusivamente um JSON seguindo o schema solicitado."
        )
        
        try:
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

    async def classificar_item_manual(self, descricao: str) -> dict:
        """Classifica um único item de texto manual."""
        start_time = time.perf_counter()
        logger.debug(f"Classificando item manual: {descricao[:30]}...")
        
        try:
            dados = await consultar_ia_async(descricao)
            duration = time.perf_counter() - start_time
            logger.info(f"LLM (classificar_item) respondeu em {duration:.2f}s.")
            return dados
        except Exception as e:
            logger.error(f"Erro ao classificar item manual: {e}")
            return {"produto": descricao, "marca": "", "categoria": "Outros", "unidade": "un"}
