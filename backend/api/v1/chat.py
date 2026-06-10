"""Routes for the AI Audit Chat."""

from __future__ import annotations
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.api.dependencies import DbSession, RoleChecker
from backend.models.compras import User, UserRole
from backend.services.chat_service import AuditChatService

router = APIRouter(prefix="/chat", tags=["Audit Chat (IA)"])

@router.post("", summary="Enviar pergunta para o Auditor Virtual")
async def audit_chat(
    db: DbSession,
    user: Annotated[
        User,
        Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER])),
    ],
    payload: Dict[str, str] = Body(..., examples=[{"message": "Qual o total gasto em laticínios no mês passado?"}])
) -> Dict[str, Any]:
    """
    Interface de chat em linguagem natural.
    Traduz perguntas do auditor para SQL, executa e explica os resultados.
    """
    service = AuditChatService(db)
    message = payload.get("message")
    
    # RLS: Passa o department_id do usuário logado se não for ADMIN
    if user.role != UserRole.ADMIN and user.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sem departamento nao pode usar o chat de auditoria.",
        )

    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    
    result = await service.chat(message, department_id=dept_id)
    return result
