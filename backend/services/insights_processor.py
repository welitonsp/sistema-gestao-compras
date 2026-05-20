"""Service for generating price insights and anomaly detection."""

from __future__ import annotations

from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import Produto, HistoricoPreco
from core.logger import get_logger

logger = get_logger("services.insights")

class PriceInsightsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detectar_variacoes_anomalas(self, threshold_percent: float = 15.0) -> List[Dict[str, Any]]:
        """
        Detecta produtos cujo preço na última compra variou significativamente 
        em relação à média histórica (Otimizado para evitar N+1).
        """
        logger.info(f"Iniciando detecção de anomalias (limiar: {threshold_percent}%)")
        
        # 1. Subquery para a média histórica
        sub_medias = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("preco_medio")
            )
            .group_by(HistoricoPreco.ean)
            .subquery()
        )

        # 2. Query principal: Pega a última compra de cada produto usando Row Number
        sub_ultima = (
            select(
                HistoricoPreco.ean,
                HistoricoPreco.preco_pago,
                HistoricoPreco.data_compra,
                HistoricoPreco.local,
                Produto.nome_limpo,
                func.row_number().over(
                    partition_by=HistoricoPreco.ean,
                    order_by=[desc(HistoricoPreco.data_compra), desc(HistoricoPreco.id)]
                ).label("rn")
            )
            .join(Produto, Produto.ean == HistoricoPreco.ean)
            .subquery()
        )

        stmt = (
            select(
                sub_ultima.c.ean,
                sub_ultima.c.preco_pago,
                sub_ultima.c.data_compra,
                sub_ultima.c.local,
                sub_ultima.c.nome_limpo,
                sub_medias.c.preco_medio
            )
            .join(sub_medias, sub_medias.c.ean == sub_ultima.c.ean)
            .where(sub_ultima.c.rn == 1)
        )
        
        result = await self.db.execute(stmt)
        alertas = []
        
        for row in result.fetchall():
            preco_atual = row.preco_pago
            preco_medio = row.preco_medio
            
            if not preco_medio: continue
            
            # Calcular variação
            variacao = ((preco_atual / preco_medio) - 1) * 100
            
            if abs(variacao) >= Decimal(str(threshold_percent)):
                alertas.append({
                    "ean": row.ean,
                    "produto": row.nome_limpo,
                    "preco_medio": float(preco_medio),
                    "preco_atual": float(preco_atual),
                    "variacao_percentual": float(variacao),
                    "data_ultima_compra": row.data_compra.isoformat(),
                    "local": row.local
                })
        
        # Ordenar por maior variação
        alertas.sort(key=lambda x: abs(x["variacao_percentual"]), reverse=True)
        return alertas

    async def obter_resumo_gastos_por_categoria(self) -> List[Dict[str, Any]]:
        """Retorna o total gasto por categoria."""
        stmt = (
            select(
                Produto.categoria,
                func.sum(HistoricoPreco.preco_pago * HistoricoPreco.quantidade).label("total")
            )
            .join(HistoricoPreco, HistoricoPreco.ean == Produto.ean)
            .group_by(Produto.categoria)
            .order_by(desc("total"))
        )
        result = await self.db.execute(stmt)
        return [{"categoria": row.categoria or "Outros", "total": float(row.total)} for row in result.fetchall()]
