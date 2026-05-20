"""Background task worker configuration using ARQ."""

from __future__ import annotations

import asyncio
from typing import Any
from arq.connections import RedisSettings
from pathlib import Path

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.services.repository import ProcurementRepository
from backend.services.pdf_processor import PDFProcessorService
from backend.services.xml_processor import XMLProcessorService
from backend.services.ocr_processor import GeminiOCRService
from core.logger import get_logger

logger = get_logger("worker")

async def processar_arquivo_background(ctx: dict[Any, Any], caminho_str: str) -> bool:
    """Task to process a file (PDF, XML or Image) in the background."""
    caminho = Path(caminho_str)
    logger.info(f"Iniciando processamento em background: {caminho.name}")
    
    async with SessionLocal() as db:
        repo = ProcurementRepository(db)
        
        if caminho.suffix.lower() in [".pdf", ".jpg", ".jpeg", ".png"]:
            ocr = GeminiOCRService()
            service = PDFProcessorService(repo, ocr)
        elif caminho.suffix.lower() == ".xml":
            service = XMLProcessorService(repo)
        else:
            logger.error(f"Formato de arquivo não suportado: {caminho.suffix}")
            return False
            
        success = await service.processar_arquivo(caminho)
        return success

async def startup(ctx: dict[Any, Any]) -> None:
    """Worker startup hook."""
    logger.info("Worker iniciado e pronto para tarefas.")

async def shutdown(ctx: dict[Any, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("Worker encerrando...")

class WorkerSettings:
    """ARQ Worker configuration."""
    functions = [processar_arquivo_background]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    # Control concurrency
    max_jobs = 5
