"""Facade service for procurement insights and analytics."""

from __future__ import annotations
from datetime import date
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from .insights.base import ACTIVE_INVOICE_STATUS
from .insights.kpi_calculator import KPICalculator
from .insights.anomaly_detector import AnomalyDetector
from .insights.forecast_service import ForecastService
from .insights.price_service import PriceService
from .insights.supplier_service import SupplierService

class PriceInsightsService:
    """Facade orchestrating all analytical sub-services."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.kpis = KPICalculator(db)
        self.anomalies = AnomalyDetector(db)
        self.forecast = ForecastService(db)
        self.prices = PriceService(db)
        self.suppliers = SupplierService(db)

    # Delegated methods (Full API compatibility)
    
    async def obter_saude_dados(self, *args, **kwargs):
        return await self.kpis.obter_saude_dados(*args, **kwargs)

    async def obter_resumo_gastos_por_categoria(self, *args, **kwargs):
        return await self.kpis.obter_resumo_gastos_por_categoria(*args, **kwargs)

    async def obter_evolucao_gastos_mensal(self, *args, **kwargs):
        return await self.kpis.obter_evolucao_gastos_mensal(*args, **kwargs)

    async def obter_alertas_risco_basicos(self, *args, **kwargs):
        return await self.kpis.obter_alertas_risco_basicos(*args, **kwargs)

    async def detectar_variacoes_anomalas(self, *args, **kwargs):
        return await self.anomalies.detectar_variacoes_anomalas(*args, **kwargs)

    async def detectar_anomalias_estatisticas(self, *args, **kwargs):
        return await self.anomalies.detectar_anomalias_estatisticas(*args, **kwargs)

    async def obter_forecast_gastos(self, *args, **kwargs):
        return await self.forecast.obter_forecast_gastos(*args, **kwargs)

    async def obter_tendencia_precos(self, *args, **kwargs):
        return await self.prices.obter_tendencia_precos(*args, **kwargs)

    async def obter_top_produtos_gasto(self, *args, **kwargs):
        return await self.prices.obter_top_produtos_gasto(*args, **kwargs)

    async def obter_historico_preco_produto(self, *args, **kwargs):
        return await self.prices.obter_historico_preco_produto(*args, **kwargs)

    async def obter_top_fornecedores_gasto(self, *args, **kwargs):
        return await self.suppliers.obter_top_fornecedores_gasto(*args, **kwargs)

    async def detectar_notas_duplicadas_suspeitas(self, *args, **kwargs):
        return await self.suppliers.detectar_notas_duplicadas_suspeitas(*args, **kwargs)

    async def obter_drilldown_fornecedor(self, *args, **kwargs):
        return await self.suppliers.obter_drilldown_fornecedor(*args, **kwargs)

    async def obter_detalhes_fornecedor(self, *args, **kwargs):
        """Legacy name for obter_drilldown_fornecedor."""
        return await self.suppliers.obter_drilldown_fornecedor(*args, **kwargs)

    async def obter_produtos_fornecedor_export(self, *args, **kwargs):
        return await self.suppliers.obter_produtos_fornecedor_export(*args, **kwargs)
    
    async def obter_produtos_mais_volateis(self, *args, **kwargs):
        return await self.prices.obter_produtos_mais_volateis(*args, **kwargs)
