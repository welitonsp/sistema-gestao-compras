"""Routes for the AI Audit Chat."""

from __future__ import annotations
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.api.dependencies import DbSession, RoleChecker
from backend.core.security import redact_audit_details
from backend.models.compras import AuditLog, User, UserRole
from backend.services.chat_service import AuditChatService

router = APIRouter(prefix="/chat", tags=["Audit Chat (IA)"])

AUDIT_CHAT_BLOCKED_OPERATION = "AUDIT_CHAT_BLOCKED"
AUDIT_CHAT_BLOCKED_REASONS = {
    "audit_chat_is_read_only",
    "unsafe_sql_blocked",
    "sensitive_sql_blocked",
    "wildcard_sql_blocked",
    "table_not_allowed",
    "column_not_allowed",
    "tenant_scope_missing",
    "query_timeout",
}

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
    await _audit_blocked_chat_if_needed(db, user, dept_id, result)
    return result


def _blocked_chat_reason(result: Dict[str, Any]) -> str | None:
    reason = result.get("blocked_reason") or result.get("error")
    if isinstance(reason, str) and reason in AUDIT_CHAT_BLOCKED_REASONS:
        return reason
    return None


async def _audit_blocked_chat_if_needed(
    db: DbSession,
    user: User,
    department_id: Any | None,
    result: Dict[str, Any],
) -> None:
    reason = _blocked_chat_reason(result)
    if reason is None:
        return

    details = {
        "action": "audit_chat_blocked",
        "reason": reason,
        "origem": "audit_chat",
        "usuario_executor": user.username,
        "department_id": str(department_id) if department_id else None,
    }
    db.add(
        AuditLog(
            department_id=department_id,
            usuario=user.username,
            operacao=AUDIT_CHAT_BLOCKED_OPERATION,
            entidade="AuditChat",
            entidade_id=reason,
            detalhes=redact_audit_details(details),
        )
    )
    await db.commit()
