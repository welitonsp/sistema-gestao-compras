"""FastAPI application entrypoint for the procurement management API."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.dependencies import AppSettings, DbSession
from backend.core.config import settings


api_v1_router = APIRouter(prefix=settings.api_v1_prefix, tags=["v1"])
"""Versioned API router mounted under the configured v1 prefix."""


@api_v1_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Validates that the API is running and the database dependency can be injected.",
)
async def health_check(
    db: DbSession,
    app_settings: AppSettings,
) -> dict[str, str]:
    """Return the operational status of the API.

    A lightweight `SELECT 1` is executed to confirm the async session is usable.
    """

    await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "message": "Sistema Operante",
        "application": app_settings.app_name,
    }


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
