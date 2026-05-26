"""Routes for dashboard and price insights."""

from __future__ import annotations

from typing import Any, Annotated
from fastapi import APIRouter, Query, status, Depends
from fastapi.responses import StreamingResponse
import io
import pandas as pd
from backend.api.dependencies import DbSession, CurrentUser
from backend.schemas.dashboard import DashboardResumoResponse, AlertasPrecoResponse
from backend.services.insights_processor import PriceInsightsService
from sqlalchemy import select, func, desc
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import HistoricoPreco, AuditLog, UserRole, User, NotaFiscal, ItemNotaFiscal

from backend.services.notifications import dispatcher
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Insights"])

ACTIVE_INVOICE_STATUS = "active"

@router.get("/notifications", summary="Stream de notificações em tempo real (SSE)")
async def stream_notifications(user: CurrentUser):
    """
    Mantém uma conexão aberta para envio de eventos em tempo real para o frontend.
    """
    return StreamingResponse(
        dispatcher.subscribe(),
        media_type="text/event-stream"
    )

@router.get(
    "/audit-logs/export",
    summary="Exportar logs de auditoria (CSV - Streamed)",
)
async def exportar_audit_logs(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR]))]
) -> StreamingResponse:
    """Exporta a trilha de auditoria via streaming para suportar grandes volumes (Zero-OOM)."""

    async def generate_csv():
        # Header
        yield "Data/Hora;Usuario;Operacao;Entidade;Detalhes;IP de Origem\n"

        # Stream do Banco via Async iterator do SQLAlchemy
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
        result = await db.stream(stmt) # Uso de stream() para carregar em chunks do DB

        async for row in result:
            log = row[0]
            data_str = log.created_at.strftime("%d/%m/%Y %H:%M:%S") if log.created_at else ""
            detalhes = (log.detalhes or "").replace(";", ",").replace("\n", " ")
            yield f"{data_str};{log.usuario};{log.operacao};{log.entidade};{detalhes};{log.ip_origem}\n"

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auditoria_logs.csv"}
    )

@router.get(
    "/audit-logs",
    summary="Listar logs de auditoria",
)
async def listar_audit_logs(
    db: DbSession,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR]))],
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retorna a trilha de auditoria do sistema com isolamento de departamento."""

    stmt = select(AuditLog)
    
    # RLS: Se não for ADMIN global, filtra pelo departamento do usuário
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(AuditLog.department_id == user.department_id)

    stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    return [
        {
            "id": str(log.id),
            "usuario": log.usuario,
            "operacao": log.operacao,
            "entidade": log.entidade,
            "entidade_id": log.entidade_id,
            "detalhes": log.detalhes,
            "ip_origem": log.ip_origem,
            "criado_em": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

@router.get(
    "/resumo",
    response_model=DashboardResumoResponse,
    summary="Obter resumo de gastos por categoria",
)
async def obter_resumo_dashboard(
    db: DbSession,
    user: CurrentUser
) -> DashboardResumoResponse:
    """Retorna o total geral gasto com isolamento de departamento."""
    service = PriceInsightsService(db)
    
    # Total Geral filtrado por Dept
    stmt_total = (
        select(func.sum(ItemNotaFiscal.valor_total))
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
    )
    if user.role != UserRole.ADMIN:
        stmt_total = stmt_total.where(NotaFiscal.department_id == user.department_id)
        
    total_geral = await db.scalar(stmt_total) or 0
    
    # Por Categoria (O service precisa ser atualizado para aceitar o dept_id)
    resumo_categorias = await service.obter_resumo_gastos_por_categoria(
        department_id=user.department_id if user.role != UserRole.ADMIN else None
    )
    
    return DashboardResumoResponse(
        total_geral=total_geral,
        por_categoria=resumo_categorias
    )

@router.get(
    "/alertas",
    response_model=AlertasPrecoResponse,
    summary="Obter alertas de variação de preço",
)
async def obter_alertas_preco(
    db: DbSession,
    user: CurrentUser,
    threshold: float = Query(15.0, description="Limiar percentual para detecção de anomalias")
) -> AlertasPrecoResponse:
    """Retorna produtos com variações de preço anômalas com isolamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    alertas = await service.detectar_variacoes_anomalas(threshold_percent=threshold, department_id=dept_id)
    return AlertasPrecoResponse(alertas=alertas)

@router.get(
    "/alertas/duplicidade",
    summary="Detectar possíveis notas duplicadas",
)
async def obter_duplicatas_suspeitas(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))]
) -> list[dict[str, Any]]:
    """Identifica notas duplicadas com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.detectar_notas_duplicadas_suspeitas(department_id=dept_id)

@router.get(
    "/alertas/estatisticos",
    summary="Detectar anomalias via Z-Score",
)
async def obter_anomalias_estatisticas(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))],
    z_threshold: float = 2.0
) -> list[dict[str, Any]]:
    """Identifica preços fora da curva com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.detectar_anomalias_estatisticas(z_threshold=z_threshold, department_id=dept_id)

@router.get(
    "/insights/tendencia",
    summary="Obter tendência de preços mensal",
)
async def obter_tendencia(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))]
) -> list[dict[str, Any]]:
    """Retorna a evolução dos preços médios por mês com isolamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_tendencia_precos(department_id=dept_id)

@router.get(
    "/insights/forecast",
    summary="Obter previsão de gastos para o próximo mês",
)
async def obter_forecast(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))]
) -> list[dict[str, Any]]:
    """Projeção de gastos com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_forecast_gastos(department_id=dept_id)

@router.get(
    "/insights/volatilidade",
    summary="Obter produtos com maior volatilidade de preço",
)
async def obter_volatilidade(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))]
) -> list[dict[str, Any]]:
    """Retorna volatilidade com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_produtos_mais_volateis(department_id=dept_id)
