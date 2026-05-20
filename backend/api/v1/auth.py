"""Authentication routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from backend.api.dependencies import AppSettings
from backend.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login", summary="Login simplificado para obtenção de token JWT")
async def login(
    settings: AppSettings,
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Endpoint de login temporário. 
    NOTA: Atualmente aceita qualquer senha para o usuário 'admin' (Fase de QA).
    """
    if form_data.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}
