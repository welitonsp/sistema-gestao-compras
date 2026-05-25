"""Shared FastAPI dependencies for the backend API.

This module centralizes dependency aliases and helper providers so route
handlers can declare infrastructure dependencies in a standardized way.
"""

from __future__ import annotations

from typing import Annotated, List

from fastapi import Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq.connections import ArqRedis
import httpx
from jose import JWTError, jwt

from backend.core.config import Settings, get_settings
from backend.core.database import get_db
from backend.core.security import TokenData
from backend.models.compras import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Provides the shared HTTP client from application state."""
    client = request.app.state.http_client
    if not client:
         raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cliente HTTP indisponivel."
        )
    return client

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
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """Valida o token JWT proveniente de COOKIE (HttpOnly) ou Header."""
    token = request.cookies.get("access_token")
    
    # Robustez: Se request.cookies falhar (comum em alguns transports de teste), tenta o header bruto
    if not token:
        cookie_header = request.headers.get("cookie")
        if cookie_header:
            for part in cookie_header.split(";"):
                if "access_token=" in part:
                    token = part.split("access_token=")[1].strip()

    # Fallback para Header Authorization (útil para APIs de integração)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessao invalida ou expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token, 
            settings.secret_key.get_secret_value(), 
            algorithms=[settings.algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Busca usuário no banco
    stmt = select(User).where(User.username == username, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

class RoleChecker:
    """Dependency para validar roles de usuario."""
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[User, Depends(get_current_user)]):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voce nao tem permissao para realizar esta operacao."
            )
        return user

DbSession = Annotated[AsyncSession, Depends(get_db)]
ArqPool = Annotated[ArqRedis, Depends(get_redis_pool)]
HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
AppSettings = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_app_settings() -> Settings:
    """Return the cached application settings instance.

    This wrapper keeps route declarations expressive and decoupled from the
    concrete settings factory implementation.
    """

    return get_settings()
