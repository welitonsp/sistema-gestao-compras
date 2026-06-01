"""Background task worker configuration using ARQ."""

from __future__ import annotations

import asyncio
from typing import Any
from arq.connections import RedisSettings
from pathlib import Path

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.storage import get_storage_provider
from backend.services.repository import ProcurementRepository
from backend.services.xml_processor import XmlProcessorService
from backend.services.pdf_processor import PdfProcessorService
from backend.services.notifications import dispatcher as sse_dispatcher
from backend.core.events import dispatcher, EVENT_NOTA_IMPORTADA
from core.logger import get_logger

logger = get_logger("backend.worker")

async def startup(ctx: dict[str, Any]) -> None:
    """Initialize worker resources."""
    logger.info("ARQ Worker iniciando...")
    
    # Registra listeners internos
    from backend.services.insights_processor import PriceInsightsService
    
    async def processar_insights_pos_importacao(nota_id, department_id):
        async with SessionLocal() as db:
            insights = PriceInsightsService(db)
            logger.info(f"Processando insights pos-importacao para nota {nota_id}...")
            await insights.detectar_notas_duplicadas_suspeitas(department_id=department_id)
            await insights.detectar_anomalias_estatisticas(department_id=department_id)

    dispatcher.subscribe(EVENT_NOTA_IMPORTADA, processar_insights_pos_importacao)

async def shutdown(ctx: dict[str, Any]) -> None:
    """Cleanup worker resources."""
    logger.info("ARQ Worker desligando...")

async def processar_arquivo_background(ctx: dict[str, Any], caminho_str: str, department_id: str | None = None) -> dict[str, Any]:
    """Processa um arquivo (PDF/XML) em background com suporte a Multi-tenancy."""
    caminho = Path(caminho_str)
    job_id = ctx.get("job_id")
    
    logger.info(f"Iniciando processamento em background: {caminho.name} (Job: {job_id}, Dept: {department_id})")
    
    async with SessionLocal() as db:
        repo = ProcurementRepository(db)
        
        try:
            # 1. Identifica o processador adequado
            ext = caminho.suffix.lower()
            success = False
            nota_id = None
            
            if ext == ".xml":
                processor = XmlProcessorService(repo)
                success = await processor.processar_arquivo(caminho, department_id=department_id)
            elif ext == ".pdf":
                processor = PdfProcessorService(repo)
                success = await processor.processar_arquivo(caminho, department_id=department_id)
            else:
                logger.error(f"Formato de arquivo não suportado: {ext}")
                return {"status": "error", "message": f"Formato {ext} não suportado"}

            if success:
                # 2. Busca o ID da nota recém importada (heurística simples ou retorno do processador)
                # No fluxo atual, o processador salva a nota.
                # 3. Notifica via SSE
                await sse_dispatcher.broadcast("JOB_COMPLETED", {"job_id": job_id, "filename": caminho.name})
                
                # 4. Dispara evento para processamento posterior (anomalias, insights, etc)
                # nota_id aqui é opcional se o listener processar o departamento inteiro
                await dispatcher.publish(EVENT_NOTA_IMPORTADA, nota_id=None, department_id=department_id)
                
                return {"status": "success"}
            else:
                await sse_dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": "Processamento falhou"})
                return {"status": "error", "message": "Processamento falhou"}
                
        except Exception as e:
            logger.error(f"Erro no worker ao processar {caminho.name}: {e}", exc_info=True)
            await sse_dispatcher.broadcast("JOB_FAILED", {"job_id": job_id, "error": str(e)})
            return {"status": "error", "message": str(e)}

class WorkerSettings:
    """ARQ Worker configuration."""
    functions = [processar_arquivo_background]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
