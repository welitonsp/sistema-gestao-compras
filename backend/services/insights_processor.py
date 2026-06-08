"""Service for generating price insights and anomaly detection."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, desc, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.dashboard import (
    OpportunityScoreBreakdown,
    SavingOpportunity,
    SavingOpportunitiesSummary,
)
from backend.core.canonization_queries import build_canonical_item_ean_join
from backend.models.compras import (
    Produto,
    HistoricoPreco,
    NotaFiscal,
    ItemNotaFiscal,
    Fornecedor,
)
from core.logger import get_logger

logger = get_logger("services.insights")

ACTIVE_INVOICE_STATUS = "active"
MIN_SAVINGS_OPPORTUNITY = Decimal("5.00")


def _historico_visivel_filter():
    return or_(
        HistoricoPreco.nota_fiscal_id == None,
        NotaFiscal.status == ACTIVE_INVOICE_STATUS,
    )


def _historico_department_filter(department_id: UUID | None):
    if department_id is None:
        return None
    return or_(
        HistoricoPreco.nota_fiscal_id == None, NotaFiscal.department_id == department_id
    )


def _is_valid_ean(ean: str | None) -> bool:
    """Accept only numeric GTIN/EAN-like identifiers for financial comparisons."""
    if not ean:
        return False
    normalized = ean.strip()
    return normalized.isdigit() and len(normalized) in {8, 12, 13, 14}


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _bounded_score(value: int) -> int:
    return max(0, min(100, value))


def _comparison_metric(current: float, previous: float) -> Dict[str, Any]:
    delta = current - previous
    if previous == 0:
        delta_percent = 0.0 if current == 0 else None
    else:
        delta_percent = (delta / previous) * 100
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "delta_percent": delta_percent,
    }


def _comparison_confidence(current_count: int, previous_count: int) -> str:
    if current_count <= 0 or previous_count <= 0:
        return "insufficient_data"
    if current_count >= 3 and previous_count >= 3:
        return "high"
    if current_count >= 2 and previous_count >= 2:
        return "medium"
    return "low"


class PriceInsightsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def obter_comparativo_dashboard(
        self,
        *,
        department_id: UUID | None = None,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        dimension: str = "all",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Compare fiscal spend between two periods using canonical product reads."""

        limit = max(1, min(50, limit))
        warnings: list[str] = []

        current_days = (current_end - current_start).days
        previous_days = (previous_end - previous_start).days
        if current_days != previous_days:
            warnings.append(
                "Os periodos comparados possuem duracoes diferentes; interprete deltas com cautela."
            )

        current_summary = await self._comparison_summary(
            department_id=department_id,
            start_date=current_start,
            end_date=current_end,
        )
        previous_summary = await self._comparison_summary(
            department_id=department_id,
            start_date=previous_start,
            end_date=previous_end,
        )

        if previous_summary["total_spend"] == 0 and current_summary["total_spend"] > 0:
            warnings.append(
                "O periodo anterior nao possui gasto registrado; percentuais podem ficar indisponiveis."
            )

        products: list[dict[str, Any]] = []
        suppliers: list[dict[str, Any]] = []
        categories: list[dict[str, Any]] = []

        if dimension in {"all", "products"}:
            products = await self._comparison_products(
                department_id=department_id,
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
                limit=limit,
            )
        if dimension in {"all", "suppliers"}:
            suppliers = await self._comparison_suppliers(
                department_id=department_id,
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
                limit=limit,
            )
        if dimension in {"all", "categories"}:
            categories = await self._comparison_categories(
                department_id=department_id,
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
                limit=limit,
            )

        return {
            "periods": {
                "current_start": current_start,
                "current_end": current_end,
                "previous_start": previous_start,
                "previous_end": previous_end,
            },
            "summary": {
                "total_spend": _comparison_metric(
                    current_summary["total_spend"],
                    previous_summary["total_spend"],
                ),
                "invoice_count": _comparison_metric(
                    current_summary["invoice_count"],
                    previous_summary["invoice_count"],
                ),
                "ticket_avg": _comparison_metric(
                    current_summary["ticket_avg"],
                    previous_summary["ticket_avg"],
                ),
            },
            "products": products,
            "suppliers": suppliers,
            "categories": categories,
            "warnings": warnings,
        }

    async def _comparison_summary(
        self,
        *,
        department_id: UUID | None,
        start_date: date,
        end_date: date,
    ) -> Dict[str, float]:
        stmt = (
            select(
                func.coalesce(func.sum(NotaFiscal.valor_total), 0).label("total_spend"),
                func.count(NotaFiscal.id).label("invoice_count"),
            )
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.data_emissao <= end_date)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        row = (await self.db.execute(stmt)).one()
        total = float(row.total_spend or 0)
        invoice_count = int(row.invoice_count or 0)
        return {
            "total_spend": total,
            "invoice_count": float(invoice_count),
            "ticket_avg": total / invoice_count if invoice_count else 0.0,
        }

    async def _comparison_products(
        self,
        *,
        department_id: UUID | None,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        current = await self._aggregate_products(
            department_id=department_id,
            start_date=current_start,
            end_date=current_end,
        )
        previous = await self._aggregate_products(
            department_id=department_id,
            start_date=previous_start,
            end_date=previous_end,
        )
        return self._merge_comparison_items(current, previous, limit)

    async def _comparison_suppliers(
        self,
        *,
        department_id: UUID | None,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        current = await self._aggregate_suppliers(
            department_id=department_id,
            start_date=current_start,
            end_date=current_end,
        )
        previous = await self._aggregate_suppliers(
            department_id=department_id,
            start_date=previous_start,
            end_date=previous_end,
        )
        return self._merge_comparison_items(current, previous, limit)

    async def _comparison_categories(
        self,
        *,
        department_id: UUID | None,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        current = await self._aggregate_categories(
            department_id=department_id,
            start_date=current_start,
            end_date=current_end,
        )
        previous = await self._aggregate_categories(
            department_id=department_id,
            start_date=previous_start,
            end_date=previous_end,
        )
        return self._merge_comparison_items(current, previous, limit)

    async def _aggregate_products(
        self,
        *,
        department_id: UUID | None,
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[str, Any]]:
        canonical_ean = build_canonical_item_ean_join(ItemNotaFiscal.ean, department_id)
        stmt = (
            select(
                canonical_ean.ean_expr.label("key"),
                Produto.nome_limpo.label("label"),
                func.sum(ItemNotaFiscal.valor_total).label("total"),
                func.sum(ItemNotaFiscal.quantidade).label("quantity"),
                func.count(func.distinct(NotaFiscal.id)).label("count"),
                func.count(func.distinct(ItemNotaFiscal.ean)).label("source_eans_count"),
            )
            .select_from(ItemNotaFiscal)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        )
        if canonical_ean.mapping_alias is not None:
            stmt = stmt.outerjoin(
                canonical_ean.mapping_alias,
                canonical_ean.join_condition,
            )
        stmt = (
            stmt.join(Produto, Produto.ean == canonical_ean.ean_expr)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.data_emissao <= end_date)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by(canonical_ean.ean_expr, Produto.nome_limpo)
        result = await self.db.execute(stmt)
        rows: dict[str, dict[str, Any]] = {}
        for row in result.fetchall():
            total = float(row.total or 0)
            quantity = float(row.quantity or 0)
            key = row._mapping["key"]
            rows[key] = {
                "key": key,
                "label": row.label,
                "total": total,
                "count": int(row.count or 0),
                "ean": key,
                "source_eans_count": int(row.source_eans_count or 0),
                "quantity": quantity,
                "avg_price": total / quantity if quantity else 0.0,
            }
        return rows

    async def _aggregate_categories(
        self,
        *,
        department_id: UUID | None,
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[str, Any]]:
        canonical_ean = build_canonical_item_ean_join(ItemNotaFiscal.ean, department_id)
        category_expr = func.coalesce(Produto.categoria, "Outros")
        stmt = (
            select(
                category_expr.label("key"),
                category_expr.label("label"),
                func.sum(ItemNotaFiscal.valor_total).label("total"),
                func.count(func.distinct(NotaFiscal.id)).label("count"),
            )
            .select_from(ItemNotaFiscal)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        )
        if canonical_ean.mapping_alias is not None:
            stmt = stmt.outerjoin(
                canonical_ean.mapping_alias,
                canonical_ean.join_condition,
            )
        stmt = (
            stmt.join(Produto, Produto.ean == canonical_ean.ean_expr)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.data_emissao <= end_date)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by(category_expr)
        result = await self.db.execute(stmt)
        rows: dict[str, dict[str, Any]] = {}
        for row in result.fetchall():
            key = row._mapping["key"] or "Outros"
            rows[key] = {
                "key": key,
                "label": row.label or "Outros",
                "total": float(row.total or 0),
                "count": int(row.count or 0),
                "categoria": key,
            }
        return rows

    async def _aggregate_suppliers(
        self,
        *,
        department_id: UUID | None,
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[str, Any]]:
        stmt = (
            select(
                Fornecedor.id.label("key"),
                Fornecedor.razao_social.label("label"),
                func.sum(NotaFiscal.valor_total).label("total"),
                func.count(NotaFiscal.id).label("count"),
            )
            .join(NotaFiscal, Fornecedor.id == NotaFiscal.fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.data_emissao <= end_date)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by(Fornecedor.id, Fornecedor.razao_social)
        result = await self.db.execute(stmt)
        rows: dict[str, dict[str, Any]] = {}
        for row in result.fetchall():
            key = str(row._mapping["key"])
            rows[key] = {
                "key": key,
                "label": row.label,
                "total": float(row.total or 0),
                "count": int(row.count or 0),
                "fornecedor_id": key,
            }
        return rows

    def _merge_comparison_items(
        self,
        current: dict[str, dict[str, Any]],
        previous: dict[str, dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key in set(current) | set(previous):
            cur = current.get(key, {})
            prev = previous.get(key, {})
            current_total = float(cur.get("total", 0) or 0)
            previous_total = float(prev.get("total", 0) or 0)
            delta = current_total - previous_total
            current_count = int(cur.get("count", 0) or 0)
            previous_count = int(prev.get("count", 0) or 0)
            quantity_current = cur.get("quantity")
            quantity_previous = prev.get("quantity")
            avg_current = cur.get("avg_price")
            avg_previous = prev.get("avg_price")
            item = {
                "key": key,
                "label": cur.get("label") or prev.get("label") or key,
                "current_total": current_total,
                "previous_total": previous_total,
                "delta": delta,
                "delta_percent": _comparison_metric(current_total, previous_total)[
                    "delta_percent"
                ],
                "current_count": current_count,
                "previous_count": previous_count,
                "confidence": _comparison_confidence(current_count, previous_count),
                "ean": cur.get("ean") or prev.get("ean"),
                "fornecedor_id": cur.get("fornecedor_id") or prev.get("fornecedor_id"),
                "categoria": cur.get("categoria") or prev.get("categoria"),
                "source_eans_count": max(
                    int(cur.get("source_eans_count", 0) or 0),
                    int(prev.get("source_eans_count", 0) or 0),
                )
                or None,
                "current_quantity": float(quantity_current)
                if quantity_current is not None
                else None,
                "previous_quantity": float(quantity_previous)
                if quantity_previous is not None
                else None,
                "current_avg_price": float(avg_current)
                if avg_current is not None
                else None,
                "previous_avg_price": float(avg_previous)
                if avg_previous is not None
                else None,
            }
            items.append(item)

        items.sort(key=lambda item: abs(item["delta"]), reverse=True)
        return items[:limit]

    async def get_saving_opportunities(
        self,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 10,
    ) -> SavingOpportunitiesSummary:
        """Build deterministic price-gap saving opportunities from visible fiscal history."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=90)
        if end_date < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        limit = max(1, min(50, limit))

        canonical_ean = build_canonical_item_ean_join(
            HistoricoPreco.ean,
            department_id,
        )
        stmt = (
            select(
                canonical_ean.ean_expr.label("ean"),
                HistoricoPreco.ean.label("source_ean"),
                HistoricoPreco.id,
                HistoricoPreco.preco_pago,
                HistoricoPreco.quantidade,
                HistoricoPreco.data_compra,
                Produto.nome_limpo,
                Produto.categoria,
            )
            .join(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
        )
        if canonical_ean.mapping_alias is not None:
            stmt = stmt.outerjoin(
                canonical_ean.mapping_alias,
                canonical_ean.join_condition,
            )

        stmt = (
            stmt.join(Produto, Produto.ean == canonical_ean.ean_expr)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.data_emissao <= end_date)
        )

        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.order_by(
            HistoricoPreco.ean,
            HistoricoPreco.data_compra,
            HistoricoPreco.id,
        )
        result = await self.db.execute(stmt)

        observations_by_ean: dict[str, list[Any]] = {}
        for row in result.fetchall():
            price = _decimal(row.preco_pago)
            quantity = _decimal(row.quantidade)
            if not _is_valid_ean(row.ean) or price <= 0 or quantity <= 0:
                continue
            observations_by_ean.setdefault(row.ean, []).append(row)

        opportunities: list[SavingOpportunity] = []
        for ean, observations in observations_by_ean.items():
            if len(observations) < 2:
                continue

            current = max(
                observations,
                key=lambda row: (row.data_compra, row.id),
            )
            benchmark = min(_decimal(row.preco_pago) for row in observations)
            current_price = _decimal(current.preco_pago)
            quantity = _decimal(current.quantidade)
            estimated_savings = (current_price - benchmark) * quantity

            if estimated_savings < MIN_SAVINGS_OPPORTUNITY:
                continue

            financial_impact_score = _bounded_score(
                int((estimated_savings / Decimal("500.00")) * Decimal("100"))
            )
            observation_count = len(observations)
            uses_canonical_group = any(row.source_ean != ean for row in observations)
            if observation_count >= 5:
                confidence_score = 90
                confidence = (
                    "high" if estimated_savings >= Decimal("50.00") else "medium"
                )
            elif observation_count >= 3:
                confidence_score = 65
                confidence = "medium"
            else:
                confidence_score = 35
                confidence = "low"

            recurrence_score = _bounded_score(observation_count * 20)
            total_score = _bounded_score(
                int(
                    (
                        financial_impact_score * 50
                        + confidence_score * 30
                        + recurrence_score * 20
                    )
                    / 100
                )
            )
            savings_percent = None
            if current_price > 0:
                savings_percent = (
                    (current_price - benchmark) / current_price
                ) * Decimal("100")

            reasons = [
                (
                    "Comparação feita entre observações do mesmo EAN canônico."
                    if uses_canonical_group
                    else "Comparação feita apenas entre observações do mesmo EAN."
                ),
                "Benchmark calculado pelo menor preço observado no histórico disponível.",
                f"Amostra com {observation_count} observações comparáveis.",
            ]
            if uses_canonical_group:
                reasons.append("Análise consolidada via visão canônica de produtos.")

            opportunities.append(
                SavingOpportunity(
                    id=f"price_gap:{ean}:{current.data_compra.isoformat()}",
                    type="price_gap",
                    title="Potencial estimado de economia por diferença de preço",
                    description=(
                        "O preço unitário mais recente está acima do menor preço "
                        "observado no histórico disponível para o mesmo EAN."
                    ),
                    product_name=current.nome_limpo,
                    ean=ean,
                    category=current.categoria,
                    current_supplier=None,
                    suggested_supplier=None,
                    reference_date=current.data_compra,
                    current_unit_price=current_price,
                    benchmark_unit_price=benchmark,
                    estimated_savings=estimated_savings,
                    estimated_savings_percent=savings_percent,
                    confidence=confidence,
                    score=OpportunityScoreBreakdown(
                        financial_impact_score=financial_impact_score,
                        confidence_score=confidence_score,
                        recurrence_score=recurrence_score,
                        total_score=total_score,
                    ),
                    reasons=reasons,
                    warnings=[
                        "Potencial estimado, não recomendação financeira definitiva.",
                    ],
                )
            )

        opportunities.sort(
            key=lambda item: (item.score.total_score, item.estimated_savings),
            reverse=True,
        )
        opportunities = opportunities[:limit]

        return SavingOpportunitiesSummary(
            period_start=start_date,
            period_end=end_date,
            total_estimated_savings=sum(
                (item.estimated_savings for item in opportunities), Decimal("0")
            ),
            opportunity_count=len(opportunities),
            high_confidence_count=sum(
                1 for item in opportunities if item.confidence == "high"
            ),
            medium_confidence_count=sum(
                1 for item in opportunities if item.confidence == "medium"
            ),
            low_confidence_count=sum(
                1 for item in opportunities if item.confidence == "low"
            ),
            insufficient_data_count=sum(
                1 for item in opportunities if item.confidence == "insufficient_data"
            ),
            opportunities=opportunities,
        )

    async def detectar_variacoes_anomalas(
        self, threshold_percent: float = 15.0, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        """
        Detecta produtos cujo preço na última compra variou significativamente
        em relação à média histórica (Otimizado via Pushdown Filter).
        """
        # Subquery para a média histórica (Global ou por Dept)
        sub_medias_stmt = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("preco_medio"),
            )
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(_historico_visivel_filter())
            .group_by(HistoricoPreco.ean)
        )
        dept_filter = _historico_department_filter(department_id)
        if dept_filter is not None:
            sub_medias_stmt = sub_medias_stmt.where(dept_filter)
        sub_medias = sub_medias_stmt.subquery()

        # Query para a última compra
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
            .where(_historico_visivel_filter())
        )
        if dept_filter is not None:
            sub_ultima_stmt = sub_ultima_stmt.where(dept_filter)
        sub_ultima = sub_ultima_stmt.subquery()

        # Calcula a variação percentual diretamente no banco usando nullif para prevenir Divisão por Zero
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
        """Detecta anomalias usando Z-Score com isolamento de departamento."""
        sub_stats_stmt = (
            select(
                HistoricoPreco.ean,
                func.avg(HistoricoPreco.preco_pago).label("avg_price"),
                func.stddev(HistoricoPreco.preco_pago).label("stddev_price"),
            )
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(_historico_visivel_filter())
            .group_by(HistoricoPreco.ean)
            .having(func.count(HistoricoPreco.id) >= 3)
        )
        dept_filter = _historico_department_filter(department_id)
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
            .where(_historico_visivel_filter())
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

    async def obter_resumo_gastos_por_categoria(
        self,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna o total gasto agrupado por categoria com isolamento e filtro de data."""
        canonical_ean = build_canonical_item_ean_join(
            ItemNotaFiscal.ean,
            department_id,
        )
        stmt = (
            select(
                Produto.categoria, func.sum(ItemNotaFiscal.valor_total).label("total")
            )
            .select_from(ItemNotaFiscal)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        )
        if canonical_ean.mapping_alias is not None:
            stmt = stmt.outerjoin(
                canonical_ean.mapping_alias,
                canonical_ean.join_condition,
            )

        stmt = (
            stmt.join(Produto, Produto.ean == canonical_ean.ean_expr)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        if start_date:
            stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = stmt.group_by(Produto.categoria).order_by(desc("total"))
        result = await self.db.execute(stmt)
        return [
            {"categoria": row.categoria or "Outros", "total": float(row.total)}
            for row in result.fetchall()
        ]

    async def obter_forecast_gastos(
        self, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        """Previsão de gastos usando tendência baseada em regressão linear simples."""
        from datetime import datetime, timedelta

        inicio = (datetime.now() - timedelta(days=180)).date()  # Últimos 6 meses

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
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by(Produto.categoria, "mes").order_by(
            Produto.categoria, "mes"
        )
        result = await self.db.execute(stmt)

        # Agrupa por categoria para calcular a tendência
        cat_data = {}
        for row in result.fetchall():
            cat = row.categoria or "Outros"
            if cat not in cat_data:
                cat_data[cat] = []
            cat_data[cat].append(float(row.total))

        forecasts = []
        for cat, values in cat_data.items():
            if len(values) < 2:
                projecao = values[0] * 1.02  # Fallback
                tendencia = "Insuferiente"
            else:
                # Regressão Linear Simples (x = indices do mês, y = valores)
                n = len(values)
                x = list(range(n))
                y = values

                sum_x = sum(x)
                sum_y = sum(y)
                sum_xx = sum(i * i for i in x)
                sum_xy = sum(i * j for i, j in zip(x, y))

                # Inclinação (slope) = (n*sum_xy - sum_x*sum_y) / (n*sum_xx - sum_x**2)
                denom = n * sum_xx - sum_x**2
                slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0

                projecao = y[-1] + slope
                if slope > 0.05 * (sum_y / n):
                    tendencia = "Alta"
                elif slope < -0.05 * (sum_y / n):
                    tendencia = "Queda"
                else:
                    tendencia = "Estável"

            forecasts.append(
                {
                    "categoria": cat,
                    "media_atual": sum(values) / len(values),
                    "projeção_proximo_mes": max(projecao, 0),
                    "tendencia": tendencia,
                }
            )

        return sorted(forecasts, key=lambda x: x["projeção_proximo_mes"], reverse=True)

    async def obter_tendencia_precos(
        self, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        """Retorna a evolução dos preços médios globais por mês para o gráfico de linhas."""
        from datetime import datetime, timedelta

        inicio = (datetime.now() - timedelta(days=180)).date()

        # Dialect handling
        bind = self.db.get_bind()
        if bind.dialect.name == "postgresql":
            month_func = func.date_trunc("month", NotaFiscal.data_emissao)
        else:
            month_func = func.strftime("%Y-%m-01", NotaFiscal.data_emissao)

        stmt = (
            select(
                month_func.label("mes"),
                func.avg(ItemNotaFiscal.valor_unitario).label("preco_medio"),
            )
            .join(ItemNotaFiscal, ItemNotaFiscal.nota_fiscal_id == NotaFiscal.id)
            .where(NotaFiscal.data_emissao >= inicio)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by("mes").order_by("mes")
        result = await self.db.execute(stmt)

        def format_mes(m):
            if isinstance(m, str):
                return datetime.strptime(m, "%Y-%m-%d").strftime("%b/%y")
            return m.strftime("%b/%y")

        return [
            {"mes": format_mes(row.mes), "valor": float(row.preco_medio)}
            for row in result.fetchall()
        ]

    async def detectar_notas_duplicadas_suspeitas(
        self, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        """Detecta duplicatas com isolamento de departamento e dispara webhooks. (Otimizado sem N+1)"""
        from backend.models.compras import Fornecedor
        from backend.services.webhook_service import webhook_service

        # Subquery para encontrar os grupos duplicados
        subq = (
            select(
                NotaFiscal.fornecedor_id,
                NotaFiscal.data_emissao,
                NotaFiscal.valor_total,
                func.count(NotaFiscal.id).label("quantidade_notas"),
            )
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .group_by(
                NotaFiscal.fornecedor_id,
                NotaFiscal.data_emissao,
                NotaFiscal.valor_total,
            )
            .having(func.count(NotaFiscal.id) > 1)
        )

        if department_id:
            subq = subq.where(NotaFiscal.department_id == department_id)

        subq = subq.subquery("dups")

        # Query principal retorna apenas dados seguros para exibição e webhooks.
        stmt = (
            select(
                subq.c.data_emissao,
                subq.c.valor_total,
                subq.c.quantidade_notas,
                Fornecedor.razao_social,
            )
            .select_from(subq)
            .join(Fornecedor, Fornecedor.id == subq.c.fornecedor_id)
        )

        result = await self.db.execute(stmt)

        alertas = [
            {
                "fornecedor": row.razao_social,
                "data": row.data_emissao.isoformat(),
                "valor": float(row.valor_total),
                "quantidade_notas": row.quantidade_notas,
            }
            for row in result.fetchall()
        ]

        # Dispara Webhooks (Idealmente faríamos batching, mas webhooks são poucos)
        for alerta in alertas:
            await webhook_service.trigger_event(
                "invoice.duplicate_detected", department_id, alerta
            )

        return alertas

    async def obter_produtos_mais_volateis(
        self, limit: int = 10, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        """Top volatilidade com isolamento."""
        stmt = (
            select(
                Produto.nome_limpo,
                func.min(HistoricoPreco.preco_pago).label("min_p"),
                func.max(HistoricoPreco.preco_pago).label("max_p"),
                (
                    (
                        func.max(HistoricoPreco.preco_pago)
                        - func.min(HistoricoPreco.preco_pago)
                    )
                    / func.nullif(func.min(HistoricoPreco.preco_pago), 0)
                    * 100
                ).label("v"),
            )
            .join(HistoricoPreco, Produto.ean == HistoricoPreco.ean)
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(_historico_visivel_filter())
        )

        dept_filter = _historico_department_filter(department_id)
        if dept_filter is not None:
            stmt = stmt.where(dept_filter)

        stmt = (
            stmt.group_by(Produto.ean, Produto.nome_limpo)
            .having(func.count(HistoricoPreco.id) > 1)
            .order_by(desc("v"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {
                "produto": r.nome_limpo,
                "min": float(r.min_p),
                "max": float(r.max_p),
                "variacao": float(r.v),
            }
            for r in result.fetchall()
        ]

    async def obter_evolucao_gastos_mensal(
        self,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna o total gasto por mês para o gráfico de evolução temporal."""
        from datetime import datetime, timedelta

        # Se houver filtro, respeitamos. Senão, mantemos últimos 12 meses por contexto.
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).date()

        # Dialect handling
        bind = self.db.get_bind()
        if bind.dialect.name == "postgresql":
            month_func = func.date_trunc("month", NotaFiscal.data_emissao)
        else:
            month_func = func.strftime("%Y-%m-01", NotaFiscal.data_emissao)

        stmt = (
            select(
                month_func.label("mes"),
                func.sum(NotaFiscal.valor_total).label("total"),
                func.count(NotaFiscal.id).label("quantidade_notas"),
            )
            .where(NotaFiscal.data_emissao >= start_date)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        stmt = stmt.group_by("mes").order_by("mes")
        result = await self.db.execute(stmt)

        def format_mes(m):
            if isinstance(m, str):
                return datetime.strptime(m, "%Y-%m-%d").strftime("%b/%y")
            return m.strftime("%b/%y")

        return [
            {
                "mes": format_mes(row.mes),
                "total": float(row.total),
                "quantidade_notas": row.quantidade_notas,
            }
            for row in result.fetchall()
        ]

    async def obter_top_produtos_gasto(
        self,
        limit: int = 10,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna os top produtos por valor total gasto com filtro de data."""
        canonical_ean = build_canonical_item_ean_join(
            ItemNotaFiscal.ean,
            department_id,
        )
        stmt = (
            select(
                canonical_ean.ean_expr.label("ean"),
                Produto.nome_limpo,
                func.sum(ItemNotaFiscal.valor_total).label("total"),
                func.sum(ItemNotaFiscal.quantidade).label("quantidade_total"),
                (
                    func.sum(ItemNotaFiscal.valor_total)
                    / func.nullif(func.sum(ItemNotaFiscal.quantidade), 0)
                ).label("preco_medio"),
            )
            .select_from(ItemNotaFiscal)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        )
        if canonical_ean.mapping_alias is not None:
            stmt = stmt.outerjoin(
                canonical_ean.mapping_alias,
                canonical_ean.join_condition,
            )

        stmt = (
            stmt.join(Produto, Produto.ean == canonical_ean.ean_expr)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        if start_date:
            stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = (
            stmt.group_by(canonical_ean.ean_expr, Produto.nome_limpo)
            .order_by(desc("total"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {
                "ean": row.ean,
                "produto": row.nome_limpo,
                "total": float(row.total),
                "quantidade_total": float(row.quantidade_total or 0),
                "preco_medio": float(row.preco_medio or 0),
            }
            for row in result.fetchall()
        ]

    async def obter_top_fornecedores_gasto(
        self,
        limit: int = 10,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna os top fornecedores por valor total gasto com filtro de data."""
        stmt = (
            select(
                Fornecedor.id,
                Fornecedor.razao_social,
                func.sum(NotaFiscal.valor_total).label("total"),
                func.count(NotaFiscal.id).label("quantidade_notas"),
                (func.sum(NotaFiscal.valor_total) / func.count(NotaFiscal.id)).label(
                    "ticket_medio"
                ),
            )
            .join(NotaFiscal, Fornecedor.id == NotaFiscal.fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        if start_date:
            stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = (
            stmt.group_by(Fornecedor.id, Fornecedor.razao_social)
            .order_by(desc("total"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {
                "fornecedor_id": str(row.id),
                "fornecedor": row.razao_social,
                "total": float(row.total),
                "quantidade_notas": row.quantidade_notas,
                "ticket_medio": float(row.ticket_medio or 0),
            }
            for row in result.fetchall()
        ]

    async def obter_alertas_risco_basicos(
        self,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna alertas de risco básicos (Concentração, Saúde do Catálogo, Mismatch)."""
        alertas = []

        # 1. Concentração de fornecedor
        stmt_total = select(func.sum(NotaFiscal.valor_total)).where(
            NotaFiscal.status == ACTIVE_INVOICE_STATUS
        )
        if department_id:
            stmt_total = stmt_total.where(NotaFiscal.department_id == department_id)
        if start_date:
            stmt_total = stmt_total.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt_total = stmt_total.where(NotaFiscal.data_emissao <= end_date)

        total_gasto = await self.db.scalar(stmt_total) or Decimal("0")

        if total_gasto > 0:
            top_forn = await self.obter_top_fornecedores_gasto(
                limit=1,
                department_id=department_id,
                start_date=start_date,
                end_date=end_date,
            )
            if top_forn:
                maior_forn = top_forn[0]
                percentual = (Decimal(str(maior_forn["total"])) / total_gasto) * 100
                if percentual >= 70:
                    alertas.append(
                        {
                            "tipo": "concentration",
                            "severidade": "warning",
                            "titulo": "Alta Concentração",
                            "mensagem": f"Atenção: {percentual:.1f}% dos seus gastos estão concentrados em {maior_forn['fornecedor']}. Considere comparar preços em outros locais.",
                            "valor": float(percentual),
                        }
                    )

        # 2. Saúde do catálogo: produtos sem categoria
        # Nota: Filtro de período não se aplica facilmente a 'produtos' sem join com notas,
        # mas faremos global ou baseado nos produtos comprados no período para ser mais preciso.
        stmt_sem_cat = select(func.count(Produto.ean)).where(
            or_(
                Produto.categoria == None,
                Produto.categoria == "",
                Produto.categoria == "Outros",
            )
        )
        # Opcional: filtrar apenas produtos que aparecem em notas do período
        if start_date or end_date or department_id:
            subq_prods = (
                select(ItemNotaFiscal.ean)
                .join(NotaFiscal)
                .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            )
            if department_id:
                subq_prods = subq_prods.where(NotaFiscal.department_id == department_id)
            if start_date:
                subq_prods = subq_prods.where(NotaFiscal.data_emissao >= start_date)
            if end_date:
                subq_prods = subq_prods.where(NotaFiscal.data_emissao <= end_date)
            stmt_sem_cat = stmt_sem_cat.where(Produto.ean.in_(subq_prods))

        count_sem_cat = await self.db.scalar(stmt_sem_cat) or 0
        if count_sem_cat > 0:
            alertas.append(
                {
                    "tipo": "catalog_health",
                    "severidade": "info",
                    "titulo": "Saúde do Catálogo",
                    "mensagem": f"Você possui {count_sem_cat} produtos sem categoria. Classifique-os para melhorar seus gráficos.",
                    "valor": float(count_sem_cat),
                }
            )

        # 3. Notas com divergência de total
        stmt_mismatch = (
            select(func.count(NotaFiscal.id))
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .where(NotaFiscal.extraction_total_mismatch == True)
        )
        if department_id:
            stmt_mismatch = stmt_mismatch.where(
                NotaFiscal.department_id == department_id
            )
        if start_date:
            stmt_mismatch = stmt_mismatch.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt_mismatch = stmt_mismatch.where(NotaFiscal.data_emissao <= end_date)

        count_mismatch = await self.db.scalar(stmt_mismatch) or 0
        if count_mismatch > 0:
            alertas.append(
                {
                    "tipo": "mismatch",
                    "severidade": "danger",
                    "titulo": "Divergência de Dados",
                    "mensagem": f"Há {count_mismatch} nota(s) com divergência de total. Revise antes de confiar nos totais.",
                    "valor": float(count_mismatch),
                }
            )

        return alertas[:3]  # Limita a 3 alertas

    async def obter_detalhes_fornecedor(
        self,
        fornecedor_id: UUID | str,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> Dict[str, Any] | None:
        """Retorna detalhes e notas recentes de um fornecedor."""
        if isinstance(fornecedor_id, str):
            try:
                fornecedor_id = UUID(fornecedor_id)
            except ValueError:
                return None

        # 1. Verifica se o fornecedor existe e pega nome
        stmt_forn = select(Fornecedor.razao_social, Fornecedor.nome_fantasia).where(
            Fornecedor.id == fornecedor_id
        )
        res_forn = await self.db.execute(stmt_forn)
        fornecedor = res_forn.first()

        if not fornecedor:
            return None

        nome_exibicao = fornecedor.nome_fantasia or fornecedor.razao_social

        # 2. Resumo (Total, Qtd, Ticket, Primeira, Ultima)
        stmt_resumo = (
            select(
                func.sum(NotaFiscal.valor_total).label("total_gasto"),
                func.count(NotaFiscal.id).label("quantidade_notas"),
                func.min(NotaFiscal.data_emissao).label("primeira_compra"),
                func.max(NotaFiscal.data_emissao).label("ultima_compra"),
            )
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt_resumo = stmt_resumo.where(NotaFiscal.department_id == department_id)
        if start_date:
            stmt_resumo = stmt_resumo.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt_resumo = stmt_resumo.where(NotaFiscal.data_emissao <= end_date)

        resumo_row = await self.db.execute(stmt_resumo)
        r = resumo_row.first()

        total_gasto = r.total_gasto or Decimal("0")
        qtd_notas = r.quantidade_notas or 0
        ticket_medio = total_gasto / qtd_notas if qtd_notas > 0 else Decimal("0")
        primeira_compra = r.primeira_compra.isoformat() if r.primeira_compra else None
        ultima_compra = r.ultima_compra.isoformat() if r.ultima_compra else None

        # 2b. Cálculo de Concentração
        stmt_total_periodo = select(func.sum(NotaFiscal.valor_total)).where(
            NotaFiscal.status == ACTIVE_INVOICE_STATUS
        )
        if department_id:
            stmt_total_periodo = stmt_total_periodo.where(
                NotaFiscal.department_id == department_id
            )
        if start_date:
            stmt_total_periodo = stmt_total_periodo.where(
                NotaFiscal.data_emissao >= start_date
            )
        if end_date:
            stmt_total_periodo = stmt_total_periodo.where(
                NotaFiscal.data_emissao <= end_date
            )

        total_periodo = await self.db.scalar(stmt_total_periodo) or Decimal("0")

        concentracao = None
        if total_periodo > 0:
            percentual = float((total_gasto / total_periodo) * 100)

            if percentual >= 50:
                nivel = "danger"
                msg = f"Concentração alta: este fornecedor representa {percentual:.1f}% dos seus gastos no período selecionado."
            elif percentual >= 30:
                nivel = "warning"
                msg = f"Atenção: este fornecedor concentra {percentual:.1f}% dos seus gastos no período selecionado."
            else:
                nivel = "info"
                msg = f"Este fornecedor representa {percentual:.1f}% dos seus gastos no período selecionado."

            concentracao = {
                "percentual": round(percentual, 1),
                "nivel": nivel,
                "mensagem": msg,
            }

        # 3. Notas
        stmt_notas = (
            select(
                NotaFiscal.data_emissao,
                NotaFiscal.numero_nota,
                NotaFiscal.valor_total,
            )
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt_notas = stmt_notas.where(NotaFiscal.department_id == department_id)
        if start_date:
            stmt_notas = stmt_notas.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt_notas = stmt_notas.where(NotaFiscal.data_emissao <= end_date)

        stmt_notas = stmt_notas.order_by(
            desc(NotaFiscal.data_emissao), desc(NotaFiscal.id)
        ).limit(limit)
        notas_res = await self.db.execute(stmt_notas)

        notas = [
            {
                "data_emissao": row.data_emissao.isoformat(),
                "numero_nota": row.numero_nota,
                "valor_total": float(row.valor_total),
            }
            for row in notas_res.fetchall()
        ]

        # 4. Top Produtos
        stmt_top_prod = (
            select(
                Produto.ean,
                Produto.nome_limpo,
                func.sum(ItemNotaFiscal.quantidade).label("quantidade_total"),
                func.sum(ItemNotaFiscal.valor_total).label("total_gasto"),
                (
                    func.sum(ItemNotaFiscal.valor_total)
                    / func.nullif(func.sum(ItemNotaFiscal.quantidade), 0)
                ).label("preco_medio"),
                func.count(func.distinct(ItemNotaFiscal.nota_fiscal_id)).label(
                    "quantidade_notas"
                ),
            )
            .join(ItemNotaFiscal, Produto.ean == ItemNotaFiscal.ean)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt_top_prod = stmt_top_prod.where(
                NotaFiscal.department_id == department_id
            )
        if start_date:
            stmt_top_prod = stmt_top_prod.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt_top_prod = stmt_top_prod.where(NotaFiscal.data_emissao <= end_date)

        stmt_top_prod = (
            stmt_top_prod.group_by(Produto.ean, Produto.nome_limpo)
            .order_by(desc("total_gasto"))
            .limit(5)
        )
        top_prod_res = await self.db.execute(stmt_top_prod)

        top_produtos = [
            {
                "ean": row.ean,
                "nome_produto": row.nome_limpo,
                "quantidade_total": float(row.quantidade_total),
                "total_gasto": float(row.total_gasto),
                "preco_medio": float(row.preco_medio or 0),
                "quantidade_notas": row.quantidade_notas,
            }
            for row in top_prod_res.fetchall()
        ]

        return {
            "fornecedor_id": str(fornecedor_id),
            "nome_exibicao": nome_exibicao,
            "resumo": {
                "total_gasto": float(total_gasto),
                "quantidade_notas": qtd_notas,
                "ticket_medio": float(ticket_medio),
                "primeira_compra": primeira_compra,
                "ultima_compra": ultima_compra,
            },
            "concentracao": concentracao,
            "notas": notas,
            "top_produtos": top_produtos,
        }

    async def obter_historico_preco_produto(
        self, ean: str, department_id: UUID | None = None, limit: int = 50
    ) -> Dict[str, Any]:
        """Retorna o histórico cronológico de compras de um produto específico."""
        from backend.core.canonization_queries import ACTIVE_CANONIZATION_STATUS
        from backend.models.compras import CanonizacaoProduto

        target_ean = ean
        history_eans = [ean]

        if department_id is not None:
            original_mapping = await self.db.scalar(
                select(CanonizacaoProduto.ean_canonico).where(
                    CanonizacaoProduto.department_id == department_id,
                    CanonizacaoProduto.ean_original == ean,
                    CanonizacaoProduto.status == ACTIVE_CANONIZATION_STATUS,
                )
            )
            if original_mapping is not None:
                target_ean = original_mapping

            active_originals = (
                (
                    await self.db.execute(
                        select(CanonizacaoProduto.ean_original).where(
                            CanonizacaoProduto.department_id == department_id,
                            CanonizacaoProduto.ean_canonico == target_ean,
                            CanonizacaoProduto.status == ACTIVE_CANONIZATION_STATUS,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if active_originals:
                history_eans = [target_ean, *active_originals]

        # Busca o nome do produto
        res_prod = await self.db.execute(
            select(Produto.nome_limpo).where(Produto.ean == target_ean)
        )
        nome_produto = res_prod.scalar_one_or_none() or "Produto Desconhecido"

        # Busca o histórico de preços
        stmt = (
            select(
                HistoricoPreco.ean.label("ean_original"),
                HistoricoPreco.data_compra,
                HistoricoPreco.local,
                HistoricoPreco.preco_pago,
                HistoricoPreco.quantidade,
                NotaFiscal.numero_nota,
                (HistoricoPreco.preco_pago * HistoricoPreco.quantidade).label("total"),
            )
            .outerjoin(NotaFiscal, NotaFiscal.id == HistoricoPreco.nota_fiscal_id)
            .where(HistoricoPreco.ean.in_(history_eans))
            .where(_historico_visivel_filter())
        )

        dept_filter = _historico_department_filter(department_id)
        if dept_filter is not None:
            stmt = stmt.where(dept_filter)

        stmt = stmt.order_by(
            desc(HistoricoPreco.data_compra), desc(HistoricoPreco.id)
        ).limit(limit)
        result = await self.db.execute(stmt)

        historico = []
        for row in result.fetchall():
            historico.append(
                {
                    "data_compra": row.data_compra.isoformat(),
                    "fornecedor": row.local,
                    "preco_unitario": float(row.preco_pago),
                    "quantidade": float(row.quantidade),
                    "valor_total": float(row.total),
                    "numero_nota": row.numero_nota,
                    "ean_original": row.ean_original,
                }
            )

        return {
            "ean": target_ean,
            "nome_produto": nome_produto,
            "historico": historico,
        }

    async def obter_produtos_fornecedor_export(
        self,
        fornecedor_id: UUID | str,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retorna produtos agregados de um fornecedor para exportação CSV."""
        if isinstance(fornecedor_id, str):
            try:
                fornecedor_id = UUID(fornecedor_id)
            except ValueError:
                return []

        stmt = (
            select(
                Produto.nome_limpo,
                Produto.ean,
                func.sum(ItemNotaFiscal.quantidade).label("quantidade_total"),
                (
                    func.sum(ItemNotaFiscal.valor_total)
                    / func.nullif(func.sum(ItemNotaFiscal.quantidade), 0)
                ).label("preco_medio"),
                func.sum(ItemNotaFiscal.valor_total).label("total_gasto"),
                func.count(func.distinct(NotaFiscal.id)).label("frequencia_notas"),
            )
            .join(ItemNotaFiscal, Produto.ean == ItemNotaFiscal.ean)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)

        if start_date:
            stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = (
            stmt.group_by(Produto.ean, Produto.nome_limpo)
            .order_by(desc("total_gasto"))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return [
            {
                "produto": row.nome_limpo,
                "ean": row.ean,
                "quantidade_total": float(row.quantidade_total or 0),
                "preco_medio": float(row.preco_medio or 0),
                "total_gasto": float(row.total_gasto or 0),
                "frequencia_notas": row.frequencia_notas,
            }
            for row in result.fetchall()
        ]

    async def obter_saude_dados(
        self,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Dict[str, Any]:
        """Agrega métricas de saúde cadastral e qualidade de extração."""
        stmt = (
            select(
                func.count(NotaFiscal.id).label("total_notas"),
                func.sum(case((NotaFiscal.extraction_quality_status == "ok", 1), else_=0)).label("notas_ok"),
                func.sum(case((NotaFiscal.extraction_quality_status == "warning", 1), else_=0)).label("notas_warning"),
                func.sum(case((NotaFiscal.extraction_quality_status == "failed", 1), else_=0)).label("notas_failed"),
                func.sum(NotaFiscal.extraction_item_count).label("total_itens"),
                func.sum(NotaFiscal.extraction_missing_ean_count).label("itens_sem_ean"),
                func.sum(case((NotaFiscal.extraction_total_mismatch == True, 1), else_=0)).label("total_mismatches"),
                func.sum(NotaFiscal.extraction_empty_description_count).label("descricoes_vazias"),
                func.sum(NotaFiscal.extraction_invalid_quantity_count).label("quantidades_invalidas"),
                func.sum(NotaFiscal.extraction_invalid_value_count).label("valores_invalidos"),
            )
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )

        if department_id:
            stmt = stmt.where(NotaFiscal.department_id == department_id)
        if start_date:
            stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date:
            stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        result = await self.db.execute(stmt)
        row = result.fetchone()

        if not row or not row.total_notas:
            return {
                "total_notas": 0,
                "notas_ok": 0,
                "notas_warning": 0,
                "notas_failed": 0,
                "percentual_saude": 100.0,
                "nivel": "ok",
                "total_itens": 0,
                "itens_sem_ean": 0,
                "total_mismatches": 0,
                "descricoes_vazias": 0,
                "quantidades_invalidas": 0,
                "valores_invalidos": 0,
            }

        total_notas = row.total_notas
        notas_ok = row.notas_ok or 0
        notas_warning = row.notas_warning or 0
        notas_failed = row.notas_failed or 0
        total_itens = int(row.total_itens or 0)
        itens_sem_ean = int(row.itens_sem_ean or 0)
        total_mismatches = int(row.total_mismatches or 0)
        descricoes_vazias = int(row.descricoes_vazias or 0)
        quantidades_invalidas = int(row.quantidades_invalidas or 0)
        valores_invalidos = int(row.valores_invalidos or 0)

        # Cálculo de saúde: Peso maior para notas failed
        # saúde = (ok * 1.0 + warning * 0.5 + failed * 0.0) / total
        percentual_saude = ((notas_ok + (notas_warning * 0.5)) / total_notas) * 100

        nivel = "ok"
        if percentual_saude < 70:
            nivel = "danger"
        elif percentual_saude < 90:
            nivel = "warning"

        return {
            "total_notas": total_notas,
            "notas_ok": notas_ok,
            "notas_warning": notas_warning,
            "notas_failed": notas_failed,
            "percentual_saude": round(percentual_saude, 1),
            "nivel": nivel,
            "total_itens": total_itens,
            "itens_sem_ean": itens_sem_ean,
            "total_mismatches": total_mismatches,
            "descricoes_vazias": descricoes_vazias,
            "quantidades_invalidas": quantidades_invalidas,
            "valores_invalidos": valores_invalidos,
        }
