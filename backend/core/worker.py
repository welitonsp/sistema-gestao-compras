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

from backend.services.notifications import dispatcher

from backend.core.storage import get_storage_provider

async def processar_arquivo_background(ctx: dict[Any, Any], caminho_str: str, department_id: str | None = None) -> bool:
    """Task to process a file (PDF, XML or Image) in the background via Storage Abstraction."""
    caminho = Path(caminho_str)
    job_id = ctx.get("job_id")
    storage = get_storage_provider()
    
    logger.info(f"Iniciando processamento em background: {caminho.name} (Job: {job_id}, Dept: {department_id})")
    
    await dispatcher.broadcast("JOB_STARTED", {"job_id": job_id, "file": caminho.name})
    
    async with SessionLocal() as db:
        try:
            repo = ProcurementRepository(db)
            
            # No futuro, o worker baixaria o arquivo do StorageProvider se não fosse local
            # Por enquanto, como é local, o StorageProvider apenas confirma o path
            # path_real = await storage.get_file_path(caminho.name, folder="NOVAS_NOTAS")
            
            if caminho.suffix.lower() in [".pdf", ".jpg", ".jpeg", ".png"]:
                if not settings.enable_gemini:
                    logger.warning(f"Processamento de imagem/PDF ignorado: ENABLE_GEMINI está falso. Arquivo: {caminho.name}")
                    await dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": "OCR desativado (Custo Gemini)"})
                    return False
                ocr = GeminiOCRService()
                service = PDFProcessorService(repo, ocr)
            elif caminho.suffix.lower() == ".xml":
                service = XMLProcessorService(repo)
            else:
                logger.error(f"Formato de arquivo não suportado: {caminho.suffix}")
                await dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": "Formato não suportado"})
                return False
                
            success = await service.processar_arquivo(caminho, department_id=department_id)
            
            if success:
                await dispatcher.broadcast("JOB_COMPLETED", {"job_id": job_id, "status": "success", "file": caminho.name})
                
                # Proatividade: Após ingestão, verifica anomalias e duplicidades imediatamente
                from backend.services.insights_processor import PriceInsightsService
                insights = PriceInsightsService(db)
                
                # 1. Checa duplicidades (Isso já dispara webhooks internamente)
                await insights.detectar_notas_duplicadas_suspeitas(department_id=department_id)
                
                # 2. Checa anomalias críticas (Z-Score > 3.0)
                anomalias = await insights.detectar_anomalias_estatisticas(z_threshold=3.0, department_id=department_id)
                if anomalias:
                    from backend.services.webhook_service import webhook_service
                    for anom in anomalias:
                        await webhook_service.trigger_event("alert.anomaly_detected", department_id, anom)
                        await dispatcher.broadcast("ANOMALY_DETECTED", anom)

            else:
                await dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": "Processamento falhou"})
                
            return success
        except Exception as e:
            logger.error(f"Erro no worker ao processar {caminho.name}: {e}")
            await dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": str(e)})
            return False

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
