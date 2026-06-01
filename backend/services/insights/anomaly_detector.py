"""Anomaly detection logic for procurement data."""

from __future__ import annotations
from decimal import Decimal
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.compras import Produto, HistoricoPreco, NotaFiscal
from .base import ACTIVE_INVOICE_STATUS, historico_visivel_filter, historico_department_filter

class AnomalyDetector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detectar_variacoes_anomalas(
        self, threshold_percent: float = 15.0, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        # ... logic from insights_processor.py ...
        sub_medias_stmt = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("preco_medio"),
            )
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(historico_visivel_filter())
            .group_by(HistoricoPreco.ean)
        )
        dept_filter = historico_department_filter(department_id)
        if dept_filter is not None:
            sub_medias_stmt = sub_medias_stmt.where(dept_filter)
        sub_medias = sub_medias_stmt.subquery()

        sub_ultima_stmt = (
            select(
                HistoricoPreco.ean,
                HistoricoPreco.preco_pago,
                HistoricoPreco.data_compra,
                HistoricoPreco.local,
                Produto.nome_limpo,
                NotaFiscal.department_id,
                func.row_number()
                .over(
                    partition_by=HistoricoPreco.ean,
                    order_by=[
                        desc(HistoricoPreco.data_compra),
                        desc(HistoricoPreco.id),
                    ],
                )
                .label("rn"),
            )
            .join(Produto, Produto.ean == HistoricoPreco.ean)
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(historico_visivel_filter())
        )
        if dept_filter is not None:
            sub_ultima_stmt = sub_ultima_stmt.where(dept_filter)
        sub_ultima = sub_ultima_stmt.subquery()

        variacao_calc = (
            (sub_ultima.c.preco_pago / func.nullif(sub_medias.c.preco_medio, 0)) - 1
        ) * 100

        stmt = (
            select(
                sub_ultima.c.ean,
                sub_ultima.c.preco_pago,
                sub_ultima.c.data_compra,
                sub_ultima.c.local,
                sub_ultima.c.nome_limpo,
                sub_medias.c.preco_medio,
                variacao_calc.label("variacao"),
            )
            .join(sub_medias, sub_medias.c.ean == sub_ultima.c.ean)
            .where(sub_ultima.c.rn == 1)
            .where(func.abs(variacao_calc) >= threshold_percent)
            .order_by(desc(func.abs(variacao_calc)))
        )
        result = await self.db.execute(stmt)
        alertas = []
        for row in result.fetchall():
            alertas.append(
                {
                    "ean": row.ean,
                    "produto": row.nome_limpo,
                    "preco_medio": float(row.preco_medio),
                    "preco_atual": float(row.preco_pago),
                    "variacao_percentual": float(row.variacao),
                    "data_ultima_compra": row.data_compra.isoformat(),
                    "local": row.local,
                }
            )
        return alertas

    async def detectar_anomalias_estatisticas(
        self, z_threshold: float = 2.0, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        sub_stats_stmt = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("avg_price"),
                func.stddev(HistoricoPreco.preco_pago).label("stddev_price"),
            )
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(historico_visivel_filter())
            .group_by(HistoricoPreco.ean)
            .having(func.count(HistoricoPreco.id) >= 3)
        )
        dept_filter = historico_department_filter(department_id)
        if dept_filter is not None:
            sub_stats_stmt = sub_stats_stmt.where(dept_filter)
        sub_stats = sub_stats_stmt.subquery()

        sub_ultima_stmt = (
            select(
                HistoricoPreco.ean,
                HistoricoPreco.preco_pago,
                Produto.nome_limpo,
                NotaFiscal.department_id,
                func.row_number()
                .over(
                    partition_by=HistoricoPreco.ean,
                    order_by=[
                        desc(HistoricoPreco.data_compra),
                        desc(HistoricoPreco.id),
                    ],
                )
                .label("rn"),
            )
            .join(Produto, Produto.ean == HistoricoPreco.ean)
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(historico_visivel_filter())
        )
        if dept_filter is not None:
            sub_ultima_stmt = sub_ultima_stmt.where(dept_filter)
        sub_ultima = sub_ultima_stmt.subquery()

        stmt = (
            select(sub_ultima, sub_stats.c.avg_price, sub_stats.c.stddev_price)
            .join(sub_stats, sub_stats.c.ean == sub_ultima.c.ean)
            .where(sub_ultima.c.rn == 1)
        )
        result = await self.db.execute(stmt)
        anomalias = []
        for row in result.fetchall():
            if not row.stddev_price:
                continue
            z = abs((row.preco_pago - row.avg_price) / row.stddev_price)
            if z >= Decimal(str(z_threshold)):
                anomalias.append(
                    {
                        "ean": row.ean,
                        "produto": row.nome_limpo,
                        "preco_atual": float(row.preco_pago),
                        "media_historica": float(row.avg_price),
                        "z_score": float(z),
                        "confianca": "Alta" if z > 3 else "Média",
                    }
                )
        return sorted(anomalias, key=lambda x: x["z_score"], reverse=True)
