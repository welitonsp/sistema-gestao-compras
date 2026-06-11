"""Stub router for the Intelligent Purchasing Agent."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import RoleChecker
from backend.models.compras import User, UserRole
from backend.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentIntent,
    AgentStatus,
    AgentResponseMetadata,
)

router = APIRouter(prefix="/agent", tags=["Intelligent Agent (STUB)"])


@router.post(
    "/query",
    summary="Consultar o Agente Inteligente (STUB)",
    response_model=AgentQueryResponse,
)
async def agent_query(
    request: AgentQueryRequest,
    user: Annotated[
        User,
        Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER])),
    ],
) -> AgentQueryResponse:
    """
    Endpoint stub para o Agente Inteligente de Compras.
    Nesta fase, o endpoint retorna apenas uma resposta informativa de que o agente está em implantação.

    Segurança:
    - ADMIN: Acesso global.
    - AUDITOR/MANAGER: Acesso restrito ao seu department_id. Bloqueado se não houver departamento.
    """
    _ = request

    # Validação de escopo (Tenant Isolation)
    if user.role != UserRole.ADMIN and user.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu perfil requer um departamento associado para usar o Agente Inteligente.",
        )

    # Resposta Stub conforme requisitos H11C-2
    return AgentQueryResponse(
        answer="O Agente Inteligente de Compras ainda está em implantação. Nesta versão inicial, nenhuma consulta foi executada.",
        intent=AgentIntent.UNSUPPORTED,
        status=AgentStatus.INSUFFICIENT_DATA,
        metadata=AgentResponseMetadata(
            row_count=0,
            execution_time_ms=0.0
        ),
        recommendations=[],
        safe_id=None
    )
