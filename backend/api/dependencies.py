"""Shared FastAPI dependencies for the backend API.

This module centralizes dependency aliases and helper providers so route
handlers can declare infrastructure dependencies in a standardized way.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.core.database import get_db


DbSession = Annotated[AsyncSession, Depends(get_db)]
"""Standard dependency alias for an async database session."""


AppSettings = Annotated[Settings, Depends(get_settings)]
"""Standard dependency alias for application settings."""


def get_app_settings() -> Settings:
    """Return the cached application settings instance.

    This wrapper keeps route declarations expressive and decoupled from the
    concrete settings factory implementation.
    """

    return get_settings()
