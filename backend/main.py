"""FastAPI application entrypoint for the procurement management API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from arq import create_pool
from arq.connections import RedisSettings

from backend.api.dependencies import AppSettings, DbSession
from backend.api.v1.notas import router as notas_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.api.v1.auth import router as auth_router
from backend.core.config import settings
from core.logger import get_logger

logger = get_logger("backend.main")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application-level resources lifecycle."""
    
    # Setup Redis Pool with resilience
    application.state.redis = None
    try:
        application.state.redis = await create_pool(
            RedisSettings.from_dsn(settings.redis_url)
        )
        logger.info("Conexao com pool Redis estabelecida.")
    except Exception as exc:
        logger.error(f"Falha ao iniciar pool Redis (Modo Degradado): {exc}")

    yield

    # Close Redis Pool safely
    if application.state.redis:
        await application.state.redis.close()
        logger.info("Pool Redis encerrado.")


api_v1_router = APIRouter(prefix=settings.api_v1_prefix, tags=["v1"])
"""Versioned API router mounted under the configured v1 prefix."""


@api_v1_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check (Liveness/Readiness)",
    description="Valida o estado básico da API e conexões locais (DB, Redis).",
)
async def health_check(
    db: DbSession,
    request: Request,
) -> dict[str, Any]:
    """Retorna o estado operacional básico do sistema."""
    import time

    results = {
        "status": "ok",
        "timestamp": time.time(),
        "components": {}
    }

    # 1. Banco de Dados
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        results["components"]["database"] = {
            "status": "healthy",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2)
        }
    except Exception as e:
        results["status"] = "degraded"
        results["components"]["database"] = {"status": "unhealthy", "error": str(e)}

    # 2. Redis / Fila de Tarefas (Reuso do pool da app)
    try:
        start = time.perf_counter()
        redis = request.app.state.redis
        if not redis:
            raise RuntimeError("Redis pool not initialized")
            
        await redis.ping()
        results["components"]["redis"] = {
            "status": "healthy",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2)
        }
    except Exception as e:
        results["status"] = "degraded"
        results["components"]["redis"] = {"status": "unhealthy", "error": str(e)}

    return results


@api_v1_router.get(
    "/health/deep",
    status_code=status.HTTP_200_OK,
    summary="Health check profundo (Integridade Externa)",
    include_in_schema=False,
)
async def deep_health_check(
    db: DbSession,
    request: Request,
) -> dict[str, Any]:
    """Testa dependências internas e externas (Groq)."""
    import httpx
    
    # Começa com o health básico
    results = await health_check(db, request)
    
    # 3. Groq API (External Connectivity)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("https://api.groq.com/openai/v1/models")
            results["components"]["groq_api"] = {
                "status": "healthy" if r.status_code in [200, 401] else "degraded",
                "code": r.status_code
            }
    except Exception as e:
        results["components"]["groq_api"] = {"status": "unreachable", "error": str(e)}

    return results


api_v1_router.include_router(notas_router)
api_v1_router.include_router(dashboard_router)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    application = FastAPI(
        title="API - Gestao de Compras",
        version=settings.app_version,
        description=(
            "API RESTful institucional para auditoria, controle de notas fiscais "
            "e analise de precos."
        ),
        debug=settings.debug,
        lifespan=lifespan,
    )

    cors_origins: list[str] = settings.cors_origins
    if settings.is_production and not cors_origins:
        # Segurança P1: Bloqueia inicialização se CORS estiver aberto em produção
        raise RuntimeError("CORS_ORIGINS deve ser configurado explicitamente em producao.")

    if not cors_origins:
        cors_origins = ["*"]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_v1_router)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    return application


app = create_application()
