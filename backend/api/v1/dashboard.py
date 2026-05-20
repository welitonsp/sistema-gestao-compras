"""Routes for dashboard and price insights."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from backend.api.dependencies import DbSession
from backend.schemas.dashboard import DashboardResumoResponse, AlertasPrecoResponse
from backend.services.insights_processor import PriceInsightsService
from sqlalchemy import select, func
from backend.models.compras import HistoricoPreco

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Insights"])

@router.get(
    "/resumo",
    response_model=DashboardResumoResponse,
    summary="Obter resumo de gastos por categoria",
)
async def obter_resumo_dashboard(db: DbSession) -> DashboardResumoResponse:
    """Retorna o total geral gasto e o detalhamento por categoria."""
    service = PriceInsightsService(db)
    
    # Total Geral
    stmt_total = select(func.sum(HistoricoPreco.preco_pago * HistoricoPreco.quantidade))
    total_geral = await db.scalar(stmt_total) or 0
    
    # Por Categoria
    resumo_categorias = await service.obter_resumo_gastos_por_categoria()
    
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
    threshold: float = Query(15.0, description="Limiar percentual para detecção de anomalias")
) -> AlertasPrecoResponse:
    """Retorna produtos com variações de preço anômalas."""
    service = PriceInsightsService(db)
    alertas = await service.detectar_variacoes_anomalas(threshold_percent=threshold)
    return AlertasPrecoResponse(alertas=alertas)
