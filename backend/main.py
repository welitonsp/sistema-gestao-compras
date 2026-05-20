"""FastAPI application entrypoint for the procurement management API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.dependencies import AppSettings, DbSession
from backend.api.v1.notas import router as notas_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.core.config import settings


api_v1_router = APIRouter(prefix=settings.api_v1_prefix, tags=["v1"])
"""Versioned API router mounted under the configured v1 prefix."""


@api_v1_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check avançado",
    description="Valida o estado operacional de todos os componentes críticos (DB, Redis, IA).",
)
async def health_check(
    db: DbSession,
    app_settings: AppSettings,
) -> dict[str, Any]:
    """Retorna o estado operacional detalhado do sistema."""
    import time
    from arq import create_pool
    from arq.connections import RedisSettings
    import httpx

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

    # 2. Redis / Fila de Tarefas
    try:
        start = time.perf_counter()
        # Timeout curto e sem retries para o health check não travar
        redis = await asyncio.wait_for(
            create_pool(RedisSettings.from_dsn(app_settings.redis_url)),
            timeout=1.0
        )
        await redis.ping()
        await redis.close()
        results["components"]["redis"] = {
            "status": "healthy",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2)
        }
    except Exception as e:
        results["status"] = "degraded"
        results["components"]["redis"] = {"status": "unhealthy", "error": "Redis unreachable (Timeout or Connection Error)"}

    # 3. Groq API (Connectivity only)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Apenas verifica se o host é resolvível e responde algo
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
    )

    cors_origins: list[str] = settings.cors_origins or ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_v1_router)
    return application


app = create_application()
