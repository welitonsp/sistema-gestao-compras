"""Service for specialized ERP exports and external system integrations."""

from __future__ import annotations
from typing import Any, List, Dict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.compras import NotaFiscal, ItemNotaFiscal, Fornecedor
import json

class ERPIntegrationService:
    """Generates specialized data structures for ERP ingestion (SAP, TOTVS, etc)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_accounting_payload(self, department_id: Any | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Generates a flat JSON structure optimized for accounting systems.
        Includes supplier details and tax keys.
        """
        stmt = (
            select(NotaFiscal, Fornecedor)
            .join(Fornecedor)
            .order_by(desc(NotaFiscal.data_emissao))
            .limit(limit)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        result = await self.db.execute(stmt)
        payload = []
        
        for nf, forn in result.all():
            payload.append({
                "erp_id": f"PURCH_{nf.id.hex[:8]}",
                "invoice_number": nf.numero_nota,
                "access_key": nf.chave_acesso,
                "issue_date": nf.data_emissao.isoformat(),
                "total_amount": float(nf.valor_total),
                "supplier": {
                    "cnpj": forn.cnpj,
                    "name": forn.razao_social
                },
                "status": "APPROVED",
                "source_system": "PROCUREMENT_AI_V3"
            })
            
        return payload

    async def get_price_index(self, search: str | None = None) -> List[Dict[str, Any]]:
        """Provides a public price reference for common supermarket items."""
        from backend.models.compras import Produto, HistoricoPreco
        from sqlalchemy import func

        stmt = (
            select(
                Produto.nome_limpo,
                Produto.marca,
                func.avg(HistoricoPreco.preco_pago).label("avg_price"),
                func.min(HistoricoPreco.preco_pago).label("min_price"),
                func.max(HistoricoPreco.preco_pago).label("max_price"),
                func.count(HistoricoPreco.id).label("observations")
            )
            .join(HistoricoPreco)
            .group_by(Produto.ean, Produto.nome_limpo, Produto.marca)
            .having(func.count(HistoricoPreco.id) > 2)
            .order_by(desc("observations"))
            .limit(50)
        )
        
        if search:
            stmt = stmt.where(Produto.nome_limpo.ilike(f"%{search}%"))

        result = await self.db.execute(stmt)
        return [
            {
                "item": row.nome_limpo,
                "brand": row.marca,
                "reference_price": round(float(row.avg_price), 2),
                "range": {"min": float(row.min_price), "max": float(row.max_price)},
                "sample_size": int(row.observations)
            }
            for row in result.fetchall()
        ]
