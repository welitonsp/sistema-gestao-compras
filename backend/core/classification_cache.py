"""Tenant-aware helpers for product classification cache reads and writes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import ClassificacaoCache


def classification_cache_scope_filter(department_id: UUID | None):
    """Return cache rows visible for a department with global fallback."""
    if department_id is None:
        return ClassificacaoCache.department_id.is_(None)
    return or_(
        ClassificacaoCache.department_id == department_id,
        ClassificacaoCache.department_id.is_(None),
    )


def classification_cache_scope_order(department_id: UUID | None):
    """Prefer tenant-specific cache over global cache, then human-verified rows."""
    if department_id is None:
        return [ClassificacaoCache.verificado_usuario.desc()]
    return [
        case(
            (ClassificacaoCache.department_id == department_id, 0),
            (ClassificacaoCache.department_id.is_(None), 1),
            else_=2,
        ).asc(),
        ClassificacaoCache.verificado_usuario.desc(),
    ]


async def get_classification_cache_entry(
    db: AsyncSession,
    *,
    descricao_original: str | None = None,
    produto_canonico: str | None = None,
    department_id: UUID | None = None,
) -> ClassificacaoCache | None:
    filters: list[Any] = [classification_cache_scope_filter(department_id)]
    if descricao_original is not None:
        filters.append(ClassificacaoCache.descricao_original == descricao_original)
    if produto_canonico is not None:
        filters.append(ClassificacaoCache.produto_canonico == produto_canonico)

    stmt = (
        select(ClassificacaoCache)
        .where(*filters)
        .order_by(*classification_cache_scope_order(department_id))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def upsert_classification_cache_entry(
    db: AsyncSession,
    *,
    descricao_original: str,
    produto_canonico: str,
    categoria: str,
    department_id: UUID | None = None,
    marca: str | None = None,
    unidade: str | None = "un",
    verificado_usuario: bool = False,
) -> ClassificacaoCache:
    stmt = select(ClassificacaoCache).where(
        ClassificacaoCache.department_id == department_id,
        ClassificacaoCache.descricao_original == descricao_original,
    )
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        entry = ClassificacaoCache(
            department_id=department_id,
            descricao_original=descricao_original,
            produto_canonico=produto_canonico,
            categoria=categoria,
            marca=marca,
            unidade=unidade or "un",
            verificado_usuario=verificado_usuario,
        )
        db.add(entry)
        return entry

    entry.produto_canonico = produto_canonico
    entry.categoria = categoria
    entry.marca = marca
    entry.unidade = unidade or "un"
    entry.verificado_usuario = verificado_usuario
    return entry
