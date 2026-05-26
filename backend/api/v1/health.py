"""Health and Monitoring routes."""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from arq.connections import ArqRedis
import httpx

from backend.api.dependencies import DbSession, ArqPool, AppSettings
from backend.core.config import settings

router = APIRouter(prefix="/health", tags=["Monitoramento"])

@router.get("", summary="Health Check do Sistema")
async def health_check(
    db: DbSession,
    redis: ArqPool,
) -> Dict[str, Any]:
    """
    Verifica a saúde dos componentes críticos: Banco de Dados, Redis e Conetividade de APIs.
    """
    health_status = {
        "status": "healthy",
        "components": {
            "database": "unknown",
            "redis": "unknown",
            "groq_api": "unknown",
            "gemini_api": "unknown"
        }
    }

    # 1. Verifica Banco de Dados
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "online"
    except Exception as e:
        health_status["components"]["database"] = f"offline: {str(e)}"
        health_status["status"] = "degraded"

    # 2. Verifica Redis (Arq Pool)
    try:
        await redis.ping()
        health_status["components"]["redis"] = "online"
    except Exception as e:
        health_status["components"]["redis"] = f"offline: {str(e)}"
        health_status["status"] = "degraded"

    # 3. Verifica APIs de IA (Connectivity Check)
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Groq
        try:
            resp = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {settings.groq_api_key}"})
            health_status["components"]["groq_api"] = "online" if resp.status_code == 200 else f"error: {resp.status_code}"
        except Exception:
            health_status["components"]["groq_api"] = "unreachable"

        # Gemini (Check base domain)
        if not settings.enable_gemini:
            health_status["components"]["gemini_api"] = "disabled"
        else:
            try:
                resp = await client.get("https://generativelanguage.googleapis.com/")
                # Google retorne 404/403 no root mas responde, o que indica conectividade
                health_status["components"]["gemini_api"] = "online" if resp.status_code < 500 else f"error: {resp.status_code}"
            except Exception:
                health_status["components"]["gemini_api"] = "unreachable"

    return health_status
