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
    ean: str
    produto: str
    total: Decimal


class TopFornecedor(BaseModel):
    """Top supplier by spend."""
    fornecedor_id: str
    fornecedor: str
    total: Decimal


class AlertaRisco(BaseModel):
    """Basic risk alert."""
    tipo: str  # ex: concentration, catalog_health, mismatch
    severidade: str  # info, warning, danger
    titulo: str
    mensagem: str
    valor: Optional[float] = None


class HistoricoPrecoProduto(BaseModel):
    """Entry in product price history series."""
    data_compra: str
    fornecedor: str
    preco_unitario: Decimal
    quantidade: Decimal
    valor_total: Decimal
    numero_nota: Optional[str] = None


class ProductPriceHistoryResponse(BaseModel):
    """Complete price history for a product."""
    ean: str
    nome_produto: str
    historico: List[HistoricoPrecoProduto]


class ResumoFornecedor(BaseModel):
    """Summary of supplier metrics."""
    total_gasto: Decimal
    quantidade_notas: int
    ticket_medio: Decimal
    primeira_compra: Optional[str] = None
    ultima_compra: Optional[str] = None


class NotaFornecedor(BaseModel):
    """Invoice basic details for supplier drill-down."""
    model_config = ConfigDict(from_attributes=True)

    data_emissao: str
    numero_nota: str
    valor_total: Decimal


class ConcentracaoFornecedor(BaseModel):
    """Supplier concentration metric."""
    percentual: float
    nivel: str  # info, warning, danger
    mensagem: str


class TopProdutoFornecedor(BaseModel):
    """Top product in a specific supplier's drill-down."""
    ean: str
    nome_produto: str
    quantidade_total: Decimal
    total_gasto: Decimal
    preco_medio: Decimal
    quantidade_notas: int


class SupplierDrilldownResponse(BaseModel):
    """Detailed drill-down for a supplier."""
    fornecedor_id: str
    nome_exibicao: str
    resumo: ResumoFornecedor
    concentracao: Optional[ConcentracaoFornecedor] = None
    notas: List[NotaFornecedor]
    top_produtos: List[TopProdutoFornecedor] = []


class DataHealthMetrics(BaseModel):
    """Metrics regarding data quality and extraction integrity."""
    total_notas: int
    notas_ok: int
    notas_warning: int
    notas_failed: int
    percentual_saude: float
    nivel: str  # ok, warning, danger
    total_itens: int
    itens_sem_ean: int
    total_mismatches: int


class DashboardResumoResponse(BaseModel):
    """Consolidated summary for the dashboard."""
    total_geral: Decimal
    por_categoria: List[GastoCategoria]
    evolucao_mensal: List[EvolucaoMensal]
    top_produtos: List[TopProduto]
    top_fornecedores: List[TopFornecedor]
    alertas_risco: List[AlertaRisco] = []
    saude_dados: Optional[DataHealthMetrics] = None


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
