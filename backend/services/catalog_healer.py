"""Service for AI-driven catalog maintenance and normalization."""

from __future__ import annotations
import asyncio
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.classification_cache import get_classification_cache_entry
from backend.models.compras import Produto, ItemNotaFiscal, NotaFiscal
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.text_sanitizer import sanitize_manual_brand, sanitize_manual_category
from core.logger import get_logger

logger = get_logger("services.healer")

ACTIVE_INVOICE_STATUS = "active"


def _produto_operacional_filter(department_id: UUID | None = None):
    item_exists = select(ItemNotaFiscal.id).where(ItemNotaFiscal.ean == Produto.ean).exists()
    active_item_exists = (
        select(ItemNotaFiscal.id)
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(
            ItemNotaFiscal.ean == Produto.ean,
            NotaFiscal.status == ACTIVE_INVOICE_STATUS,
        )
    )
    if department_id is not None:
        active_item_exists = active_item_exists.where(NotaFiscal.department_id == department_id)
        return active_item_exists.exists()

    active_item_exists = active_item_exists.exists()
    return or_(~item_exists, active_item_exists)

class CatalogHealerService:
    """Identifies inconsistencies in the product catalog and suggests unifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = AIStructuredExtractor()

    async def get_maintenance_suggestions(
        self,
        department_id: UUID | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Scans the catalog for products with very similar names but different brands/categories.
        Returns a list of suggested unifications.
        """
        logger.info("Iniciando varredura de autocura do catálogo.")
        
        # 1. Busca produtos que podem ser duplicados ou inconsistentes
        # Pega produtos agrupados por nome aproximado (simulação simples)
        stmt = select(Produto).where(_produto_operacional_filter(department_id)).order_by(Produto.nome_limpo)
        result = await self.db.execute(stmt)
        all_products = result.scalars().all()
        
        suggestions = []
        # Agrupamento heurístico simples por similaridade de prefixo
        seen = set()
        for p in all_products:
            if p.ean in seen: continue
            
            # Busca "vizinhos" no catálogo
            prefix = p.nome_limpo[:8].upper()
            neighbors = [other for other in all_products if other.ean != p.ean and other.nome_limpo.upper().startswith(prefix)]
            
            if neighbors:
                for n in neighbors:
                    # Se categoria ou marca for diferente, sugere revisão
                    if n.categoria != p.categoria or n.marca != p.marca:
                        suggestions.append({
                            "type": "INCONSISTENCY",
                            "primary": {"ean": p.ean, "nome": p.nome_limpo, "marca": p.marca, "categoria": p.categoria},
                            "suggestion": {"ean": n.ean, "nome": n.nome_limpo, "marca": n.marca, "categoria": n.categoria},
                            "reason": "Nomes similares com categorias/marcas divergentes."
                        })
                        seen.add(n.ean)
            seen.add(p.ean)
            
        return suggestions[:20] # Limita para o auditor não ser sobrecarregado

    async def apply_healing(self, ean_source: str, target_data: Dict[str, Any]):
        """Applies the correction to a product and updates the global AI cache."""
        stmt = select(Produto).where(Produto.ean == ean_source)
        res = await self.db.execute(stmt)
        produto = res.scalar_one_or_none()
        
        if not produto: return
        
        if "categoria" in target_data: produto.categoria = sanitize_manual_category(target_data["categoria"])
        if "marca" in target_data: produto.marca = sanitize_manual_brand(target_data["marca"])
        if "nome_limpo" in target_data: produto.nome_limpo = target_data["nome_limpo"]
        
        # Sincroniza Cache
        from backend.models.compras import ItemNotaFiscal
        from core.classificador_regras import _normalizar
        
        stmt_desc = select(ItemNotaFiscal.descricao_original).where(ItemNotaFiscal.ean == ean_source).distinct()
        descricoes = (await self.db.execute(stmt_desc)).scalars().all()
        
        for desc in descricoes:
            norm = _normalizar(desc)
            cache_entry = await get_classification_cache_entry(
                self.db,
                descricao_original=norm,
                department_id=None,
            )
            if cache_entry:
                cache_entry.categoria = produto.categoria
                cache_entry.marca = produto.marca
                
        await self.db.commit()
        logger.info(f"Autocura aplicada ao produto {ean_source}.")
