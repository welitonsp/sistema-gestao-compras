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
        em relação à média histórica.
        """
        logger.info(f"Iniciando detecção de anomalias (limiar: {threshold_percent}%)")
        
        # 1. Obter a média de preço por produto
        # Usamos uma subquery ou fazemos em passos.
        # Para performance, vamos buscar as médias e depois as últimas compras.
        
        stmt_medias = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("preco_medio"),
                func.count(HistoricoPreco.id).label("total_compras")
            )
            .group_by(HistoricoPreco.ean)
            .having(func.count(HistoricoPreco.id) > 1)
        )
        
        result_medias = await self.db.execute(stmt_medias)
        medias = {row.ean: (row.preco_medio, row.total_compras) for row in result_medias}
        
        alertas = []
        
        for ean, (preco_medio, total_compras) in medias.items():
            # Buscar a última compra deste EAN
            stmt_ultima = (
                select(HistoricoPreco, Produto.nome_limpo)
                .join(Produto, Produto.ean == HistoricoPreco.ean)
                .where(HistoricoPreco.ean == ean)
                .order_by(desc(HistoricoPreco.data_compra), desc(HistoricoPreco.id))
                .limit(1)
            )
            result_ultima = await self.db.execute(stmt_ultima)
            row_ultima = result_ultima.fetchone()
            
            if not row_ultima:
                continue
                
            ultima_compra, nome_produto = row_ultima
            preco_atual = ultima_compra.preco_pago
            
            # Calcular variação
            variacao = ((preco_atual / preco_medio) - 1) * 100
            
            if abs(variacao) >= Decimal(str(threshold_percent)):
                alertas.append({
                    "ean": ean,
                    "produto": nome_produto,
                    "preco_medio": float(preco_medio),
                    "preco_atual": float(preco_atual),
                    "variacao_percentual": float(variacao),
                    "data_ultima_compra": ultima_compra.data_compra.isoformat(),
                    "local": ultima_compra.local
                })
        
        # Ordenar por maior variação (valor absoluto)
        alertas.sort(key=lambda x: abs(x["variacao_percentual"]), reverse=True)
        
        logger.info(f"Detectados {len(alertas)} alertas de variação de preço.")
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
