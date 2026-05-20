"""Schemas for dashboard and insights data."""

from __future__ import annotations

from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class GastoCategoria(BaseModel):
    """Total spent per category."""
    model_config = ConfigDict(from_attributes=True)
    
    categoria: str
    total: Decimal


class DashboardResumoResponse(BaseModel):
    """Consolidated summary for the dashboard."""
    total_geral: Decimal
    por_categoria: List[GastoCategoria]


class AlertaPreco(BaseModel):
    """Price anomaly alert."""
    ean: str
    produto: str
    preco_medio: Decimal
    preco_atual: Decimal
    variacao_percentual: float
    data_ultima_compra: str
    local: str


class AlertasPrecoResponse(BaseModel):
    """List of price alerts."""
    alertas: List[AlertaPreco]
