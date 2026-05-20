"""Service for processing PDF procurement documents."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple, Optional

from backend.services.ocr_processor import GeminiOCRService
from backend.services.repository import ProcurementRepository
from core.logger import get_logger, ContextAdapter
from backend.schemas.internal import ItemNotaDTO, NotaFiscalDTO, FornecedorDTO

logger = get_logger("services.pdf_processor")

class PDFProcessorService:
    """Service to extract and process data from PDF and Image files using OCR."""

    def __init__(self, repo: ProcurementRepository, ocr_service: GeminiOCRService):
        self.repo = repo
        self.ocr = ocr_service
        self._log = logger

    async def processar_arquivo(self, caminho: Path) -> bool:
        """Process a PDF or Image file and persist its data."""
        self._log = ContextAdapter(logger, {"arquivo": caminho.name})
        self._log.info(f"Iniciando processamento OCR: {caminho.name}")

        try:
            # 1. Extração via OCR (Gemini Vision)
            if caminho.suffix.lower() == ".pdf":
                nota_dto = await self.ocr.extrair_de_pdf(caminho)
            elif caminho.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                nota_dto = await self.ocr.extrair_de_imagem(caminho)
            else:
                self._log.error(f"Formato não suportado: {caminho.suffix}")
                return False

            if not nota_dto:
                self._log.error("Falha ao extrair dados via OCR.")
                return False

            # 2. Persistência
            async with self.repo.db.begin():
                if await self.repo.nota_existe(nota_dto.chave_acesso):
                    self._log.warning(f"Nota {nota_dto.chave_acesso} já processada.")
                    return True
                
                await self.repo.salvar_nota_completa(nota_dto.chave_acesso, nota_dto)
            
            self._log.info(f"Arquivo processado com sucesso. Chave: {nota_dto.chave_acesso}")
            return True

        except Exception as e:
            self._log.error(f"Erro ao processar arquivo {caminho.name}: {e}", exc_info=True)
            return False
