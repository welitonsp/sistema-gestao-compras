"""Spend forecasting using simple linear regression."""

from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.compras import Produto, NotaFiscal, ItemNotaFiscal
from .base import ACTIVE_INVOICE_STATUS

class ForecastService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def obter_forecast_gastos(
        self, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        inicio = (datetime.now() - timedelta(days=180)).date()
        stmt = (
            select(
                Produto.categoria,
                func.date_trunc("month", NotaFiscal.data_emissao).label("mes"),
                func.sum(ItemNotaFiscal.valor_total).label("total"),
            )
            .join(ItemNotaFiscal, Produto.ean == ItemNotaFiscal.ean)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.data_emissao >= inicio)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt = stmt.where(NotaFiscal.department_id == department_id)
        stmt = stmt.group_by(Produto.categoria, "mes").order_by(Produto.categoria, "mes")
        result = await self.db.execute(stmt)

        cat_data = {}
        for row in result.fetchall():
            cat = row.categoria or "Outros"
            if cat not in cat_data: cat_data[cat] = []
            cat_data[cat].append(float(row.total))

        forecasts = []
        for cat, values in cat_data.items():
            if len(values) < 2:
                projecao = values[0] * 1.02
                tendencia = "Insuferiente"
            else:
                n = len(values)
                x = list(range(n))
                y = values
                denom = n * sum(i*i for i in x) - sum(x)**2
                slope = (n * sum(i*j for i,j in zip(x,y)) - sum(x)*sum(y)) / denom if denom != 0 else 0
                projecao = y[-1] + slope
                avg_y = sum(y)/n
                if slope > 0.05 * avg_y: tendencia = "Alta"
                elif slope < -0.05 * avg_y: tendencia = "Queda"
                else: tendencia = "Estável"

            forecasts.append({
                "categoria": cat,
                "media_atual": sum(values) / len(values),
                "projeção_proximo_mes": max(projecao, 0),
                "tendencia": tendencia,
            })
        return sorted(forecasts, key=lambda x: x["projeção_proximo_mes"], reverse=True)
