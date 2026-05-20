"""Shared FastAPI dependencies for the backend API.

This module centralizes dependency aliases and helper providers so route
handlers can declare infrastructure dependencies in a standardized way.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis
from jose import JWTError, jwt

from backend.core.config import Settings, get_settings
from backend.core.database import get_db
from backend.core.security import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_redis_pool(request: Request) -> ArqRedis:
    """Provides the shared ARQ Redis pool from application state."""
    redis = request.app.state.redis
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servico de fila (Redis) temporariamente indisponivel."
        )
    return redis

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)]
) -> TokenData:
    """Valida o token JWT e retorna os dados do usuário autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, 
            settings.secret_key.get_secret_value(), 
            algorithms=[settings.algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    return token_data

DbSession = Annotated[AsyncSession, Depends(get_db)]
ArqPool = Annotated[ArqRedis, Depends(get_redis_pool)]
AppSettings = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[TokenData, Depends(get_current_user)]


def get_app_settings() -> Settings:
    """Return the cached application settings instance.

    This wrapper keeps route declarations expressive and decoupled from the
    concrete settings factory implementation.
    """

    return get_settings()
