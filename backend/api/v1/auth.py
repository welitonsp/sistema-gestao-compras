"""Authentication routes."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from backend.api.dependencies import DbSession
from backend.models.compras import User
from backend.core.security import create_access_token, verify_password
from backend.core.config import settings
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login", summary="Login para obtenção de token via Cookie")
async def login(
    response: Response,
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Endpoint de login seguro. 
    Verifica credenciais e retorna o token via HttpOnly Cookie.
    """
    # 1. Busca usuário real no banco
    stmt = select(User).where(User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    # 2. Valida existência e hash da senha com mitigação de timing attack
    dummy_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQqiRQYq"
    is_valid_password = verify_password(form_data.password, user.hashed_password if user else dummy_hash)

    if not user or not is_valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado.",
        )
    
    # 3. Gera token
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    # 4. Define o Cookie Seguro (BFF Pattern)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        expires=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=not settings.debug,
        path="/", # Garante que o cookie seja enviado para todas as rotas
    )
    
    return {"status": "ok", "message": "Autenticado com sucesso"}

@router.post("/logout", summary="Encerrar sessão")
async def logout(response: Response):
    """Remove o cookie de autenticação."""
    response.delete_cookie(key="access_token")
    return {"status": "ok"}
