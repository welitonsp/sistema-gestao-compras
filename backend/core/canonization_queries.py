"""SQL helpers for tenant-scoped product canonization reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from backend.models.compras import CanonizacaoProduto


ACTIVE_CANONIZATION_STATUS = "active"


@dataclass(frozen=True)
class CanonicalEanJoin:
    """Parts needed to read item rows through the canonical EAN view."""

    ean_expr: ColumnElement[Any]
    mapping_alias: Any | None
    join_condition: ColumnElement[bool] | None


def build_canonical_item_ean_join(
    item_ean_column: ColumnElement[Any],
    department_id: UUID | None,
) -> CanonicalEanJoin:
    """Build a tenant-scoped canonical EAN expression for read-only queries."""

    if department_id is None:
        return CanonicalEanJoin(
            ean_expr=item_ean_column,
            mapping_alias=None,
            join_condition=None,
        )

    mapping_alias = aliased(CanonizacaoProduto, name="active_product_canonization")
    return CanonicalEanJoin(
        ean_expr=func.coalesce(mapping_alias.ean_canonico, item_ean_column),
        mapping_alias=mapping_alias,
        join_condition=and_(
            mapping_alias.department_id == department_id,
            mapping_alias.ean_original == item_ean_column,
            mapping_alias.status == ACTIVE_CANONIZATION_STATUS,
        ),
    )
