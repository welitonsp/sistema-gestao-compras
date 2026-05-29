"""Schemas for dashboard and insights data."""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class GastoCategoria(BaseModel):
    """Total spent per category."""
    model_config = ConfigDict(from_attributes=True)
    
    categoria: str
    total: Decimal


class EvolucaoMensal(BaseModel):
    """Monthly spend evolution."""
    mes: str
    total: Decimal


class TopProduto(BaseModel):
    """Top product by spend."""
    produto: str
    total: Decimal


class TopFornecedor(BaseModel):
    """Top supplier by spend."""
    fornecedor: str
    total: Decimal


class AlertaRisco(BaseModel):
    """Basic risk alert."""
    tipo: str  # ex: concentration, catalog_health, mismatch
    severidade: str  # info, warning, danger
    titulo: str
    mensagem: str
    valor: Optional[float] = None


class DashboardResumoResponse(BaseModel):
    """Consolidated summary for the dashboard."""
    total_geral: Decimal
    por_categoria: List[GastoCategoria]
    evolucao_mensal: List[EvolucaoMensal]
    top_produtos: List[TopProduto]
    top_fornecedores: List[TopFornecedor]
    alertas_risco: List[AlertaRisco] = []


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
