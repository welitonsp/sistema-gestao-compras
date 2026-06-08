"""Routes for product catalog management."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import csv
import json
from typing import Any, Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.responses import StreamingResponse
import io
import pandas as pd
from sqlalchemy import func, select, or_
from sqlalchemy.orm import aliased
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.core.csv_utils import sanitize_csv_cell
from backend.models.compras import AuditLog, CanonizacaoProduto, Department, Produto, ClassificacaoCache, UserRole, User, ItemNotaFiscal, NotaFiscal
from backend.schemas.canonization import (
    CanonizationCandidateGroup,
    CanonizationCandidatesResponse,
    CanonizationConfirmationRequest,
    CanonizationConfirmationResponse,
    CanonizationMatch,
    CanonizationMappingItem,
    CanonizationMappingStatusCounts,
    CanonizationMappingsResponse,
    CanonizationProduct,
    CanonizationRevertRequest,
    CanonizationRevertResponse,
)
from backend.schemas.produtos import (
    CategorySuggestionCandidatesResponse,
    ProdutoResponse,
    ProdutoUpdate,
)

from backend.services.catalog_healer import CatalogHealerService
from backend.services.product_matching import (
    DEFAULT_CANONIZATION_LIMIT,
    DEFAULT_CANONIZATION_THRESHOLD,
    MAX_PRODUCTS_TO_COMPARE,
    ProductMatchInput,
    generate_product_match_groups,
)
from backend.services.product_canonization import (
    ProductCanonizationConflictError,
    ProductCanonizationNotFoundError,
    ProductCanonizationService,
    ProductCanonizationValidationError,
)
from backend.services.product_categorization import get_category_suggestion_candidates

router = APIRouter(prefix="/produtos", tags=["Produtos"])

ACTIVE_INVOICE_STATUS = "active"
CATEGORY_CONFIRMED_OPERATION = "CATEGORY_CONFIRMED"
CANONIZATION_MAPPING_STATUSES = ("active", "inactive", "reverted")
CANONIZATION_MAPPING_SORT_FIELDS = {
    "updated_at",
    "confirmed_at",
    "reverted_at",
    "ean_original",
    "ean_canonico",
    "status",
    "department",
    "original_name",
    "canonical_name",
}
SENSITIVE_AUDIT_TERMS = (
    "c" + "pf",
    "cn" + "pj",
    "chave" + "_acesso",
    "qr" + "_code",
    "url" + "_sefaz",
    "x" + "ml",
    "json" + "_bruto",
    "payload" + "_bruto",
    "descricao" + "_original",
)
PRODUCT_AUDIT_ALLOWED_DETAIL_KEYS = {
    "categoria_anterior",
    "categoria_nova",
    "origem",
    "usuario",
    "produto",
    "categorias_sugeridas_relacionadas",
}


def _categoria_para_comparacao(categoria: str | None) -> str:
    return (categoria or "").strip()


def _safe_product_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    safe_details: dict[str, Any] = {}
    for key in PRODUCT_AUDIT_ALLOWED_DETAIL_KEYS:
        value = details.get(key)
        if isinstance(value, list):
            safe_details[key] = [
                _safe_product_audit_value(item)
                for item in value[:5]
            ]
        else:
            safe_details[key] = _safe_product_audit_value(value)
    return safe_details


def _safe_product_audit_value(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    lowered = text.lower()
    if any(term in lowered for term in SENSITIVE_AUDIT_TERMS):
        return "[redacted]"
    return text[:200]


def _produto_operacional_filter():
    item_exists = select(ItemNotaFiscal.id).where(ItemNotaFiscal.ean == Produto.ean).exists()
    active_item_exists = (
        select(ItemNotaFiscal.id)
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(
            ItemNotaFiscal.ean == Produto.ean,
            NotaFiscal.status == ACTIVE_INVOICE_STATUS,
        )
        .exists()
    )
    return or_(~item_exists, active_item_exists)


def _canonization_mapping_item(row: Any) -> CanonizationMappingItem:
    mapping = row.CanonizacaoProduto
    return CanonizationMappingItem(
        department_id=mapping.department_id,
        department_name=row.department_name,
        ean_original=mapping.ean_original,
        original_name=row.original_name,
        ean_canonico=mapping.ean_canonico,
        canonical_name=row.canonical_name,
        status=mapping.status,
        reason=mapping.reason,
        confidence_score=(
            float(mapping.confidence_score)
            if mapping.confidence_score is not None
            else None
        ),
        confirmado_por=mapping.confirmado_por,
        confirmado_em=mapping.confirmado_em,
        revertido_por=mapping.revertido_por,
        revertido_em=mapping.revertido_em,
        revert_reason=mapping.revert_reason,
    )


def _resolve_canonization_department(
    user: User,
    department_id: UUID | None,
) -> UUID | None:
    if user.role == UserRole.ADMIN:
        return department_id
    if user.department_id is None:
        return None
    if department_id is not None and department_id != user.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario nao pode consultar mapeamentos de outro departamento.",
        )
    return user.department_id


def _canonization_mapping_filters(
    original_product: Any,
    canonical_product: Any,
    effective_department_id: UUID | None,
    search: str | None,
) -> list[Any]:
    filters = []
    if effective_department_id is not None:
        filters.append(CanonizacaoProduto.department_id == effective_department_id)

    safe_search = (search or "").strip()
    if safe_search:
        pattern = f"%{safe_search}%"
        filters.append(
            or_(
                CanonizacaoProduto.ean_original.ilike(pattern),
                CanonizacaoProduto.ean_canonico.ilike(pattern),
                CanonizacaoProduto.confirmado_por.ilike(pattern),
                CanonizacaoProduto.revertido_por.ilike(pattern),
                Department.name.ilike(pattern),
                original_product.nome_limpo.ilike(pattern),
                canonical_product.nome_limpo.ilike(pattern),
            )
        )

    return filters


def _canonization_mapping_base_stmt(original_product: Any, canonical_product: Any):
    return (
        select(
            CanonizacaoProduto,
            Department.name.label("department_name"),
            original_product.nome_limpo.label("original_name"),
            canonical_product.nome_limpo.label("canonical_name"),
        )
        .join(Department, Department.id == CanonizacaoProduto.department_id)
        .join(original_product, original_product.ean == CanonizacaoProduto.ean_original)
        .join(canonical_product, canonical_product.ean == CanonizacaoProduto.ean_canonico)
    )


def _canonization_mapping_count_from(original_product: Any, canonical_product: Any):
    return (
        CanonizacaoProduto.__table__
        .join(Department.__table__, Department.id == CanonizacaoProduto.department_id)
        .join(original_product, original_product.ean == CanonizacaoProduto.ean_original)
        .join(canonical_product, canonical_product.ean == CanonizacaoProduto.ean_canonico)
    )


def _canonization_mapping_order(
    sort_by: str,
    sort_dir: str,
    original_product: Any,
    canonical_product: Any,
) -> list[Any]:
    sort_columns = {
        "updated_at": CanonizacaoProduto.updated_at,
        "confirmed_at": CanonizacaoProduto.confirmado_em,
        "reverted_at": CanonizacaoProduto.revertido_em,
        "ean_original": CanonizacaoProduto.ean_original,
        "ean_canonico": CanonizacaoProduto.ean_canonico,
        "status": CanonizacaoProduto.status,
        "department": Department.name,
        "original_name": original_product.nome_limpo,
        "canonical_name": canonical_product.nome_limpo,
    }
    column = sort_columns.get(sort_by, CanonizacaoProduto.updated_at)
    ordered = column.asc() if sort_dir == "asc" else column.desc()
    return [ordered, CanonizacaoProduto.ean_original.asc()]

@router.get(
    "/maintenance",
    summary="Obter sugestões de manutenção do catálogo",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER]))]
)
async def obter_sugestoes_manutencao(db: DbSession):
    """Retorna inconsistências detectadas pela IA no catálogo."""
    service = CatalogHealerService(db)
    return await service.get_maintenance_suggestions()

@router.post(
    "/{ean}/heal",
    summary="Aplicar correção de autocura",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def aplicar_autocura(ean: str, payload: dict, db: DbSession):
    """Aplica uma sugestão de unificação ou correção sugerida pela IA."""
    service = CatalogHealerService(db)
    await service.apply_healing(ean, payload)
    return {"status": "success"}

@router.get(
    "/export",
    summary="Exportar catálogo de produtos (CSV - Streamed)",
)
async def exportar_produtos(
    db: DbSession, 
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER]))]
) -> StreamingResponse:
    """Exporta o catálogo de produtos via streaming (Zero-OOM)."""
    
    async def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        def yield_row(row_data: list[Any]):
            sanitized = [sanitize_csv_cell(cell) for cell in row_data]
            output.seek(0)
            output.truncate(0)
            writer.writerow(sanitized)
            return output.getvalue()

        yield yield_row(["EAN/Codigo", "Descricao Canonica", "Marca", "Categoria", "Unidade"])
        
        stmt = select(Produto).where(_produto_operacional_filter()).order_by(Produto.nome_limpo)
        result = await db.stream(stmt)
        
        async for row in result:
            p = row[0]
            yield yield_row([p.ean, p.nome_limpo, p.marca, p.categoria, p.unidade])

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=catalogo_produtos.csv"}
    )

@router.get(
    "",
    response_model=list[ProdutoResponse],
    summary="Listar catálogo de produtos",
)
async def listar_produtos(
    db: DbSession,
    user: CurrentUser,
    search: str | None = Query(None, description="Busca por nome ou EAN"),
    categoria: str | None = Query(None, description="Filtrar por categoria"),
    limit: int = 100,
    offset: int = 0,
) -> Any:
    """Retorna a lista de produtos cadastrados no sistema."""
    stmt = select(Produto).where(_produto_operacional_filter())
    department_id = user.department_id

    if department_id is not None:
        from backend.models.compras import CanonizacaoProduto

        stmt = stmt.outerjoin(
            CanonizacaoProduto,
            (
                (CanonizacaoProduto.department_id == department_id)
                & (CanonizacaoProduto.ean_original == Produto.ean)
                & (CanonizacaoProduto.status == "active")
            ),
        ).add_columns(
            CanonizacaoProduto.ean_original.label("canon_ean_original"),
            CanonizacaoProduto.ean_canonico.label("canon_ean_canonico"),
            CanonizacaoProduto.status.label("canon_status"),
            CanonizacaoProduto.reason.label("canon_reason"),
            CanonizacaoProduto.confidence_score.label("canon_confidence_score"),
        )
    
    if search:
        stmt = stmt.where(
            or_(
                Produto.nome_limpo.ilike(f"%{search}%"),
                Produto.ean.ilike(f"%{search}%")
            )
        )
    
    if categoria:
        stmt = stmt.where(Produto.categoria == categoria)
        
    stmt = stmt.order_by(Produto.nome_limpo).limit(limit).offset(offset)
    result = await db.execute(stmt)
    if department_id is None:
        return result.scalars().all()

    products = []
    for row in result.fetchall():
        produto = row.Produto
        canonizacao = None
        if row.canon_ean_original is not None:
            canonizacao = {
                "status": row.canon_status,
                "ean_original": row.canon_ean_original,
                "ean_canonico": row.canon_ean_canonico,
                "reason": row.canon_reason,
                "confidence_score": (
                    float(row.canon_confidence_score)
                    if row.canon_confidence_score is not None
                    else None
                ),
            }
        products.append(
            ProdutoResponse(
                ean=produto.ean,
                nome_limpo=produto.nome_limpo,
                marca=produto.marca,
                categoria=produto.categoria,
                unidade=produto.unidade,
                canonizacao=canonizacao,
            )
        )
    return products


@router.get(
    "/categorization/candidates",
    response_model=CategorySuggestionCandidatesResponse,
    summary="Listar candidatos para categorização assistida",
)
async def listar_candidatos_categorizacao(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(25, ge=1, le=100),
    min_confidence: Decimal = Query(Decimal("0"), ge=0, le=1),
    category_filter: str | None = Query(None),
    include_low_confidence: bool = Query(True),
    enable_ai: bool = Query(False),
    ai_limit: int = Query(3, ge=0, le=5),
) -> CategorySuggestionCandidatesResponse:
    """Retorna candidatos read-only para revisão humana de categoria."""
    department_id = user.department_id if user.role != UserRole.ADMIN else None
    return await get_category_suggestion_candidates(
        db=db,
        department_id=department_id,
        limit=limit,
        min_confidence=min_confidence,
        category_filter=category_filter,
        include_low_confidence=include_low_confidence,
        enable_ai=enable_ai,
        ai_limit=ai_limit,
    )


@router.get(
    "/canonization/candidates",
    response_model=CanonizationCandidatesResponse,
    summary="Listar candidatos read-only para canonizacao de produtos",
)
async def listar_candidatos_canonizacao(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(DEFAULT_CANONIZATION_LIMIT, ge=1, le=100),
    threshold: float = Query(DEFAULT_CANONIZATION_THRESHOLD, ge=0.8, le=1.0),
    category: str | None = Query(None),
    include_reasons: bool = Query(True),
) -> CanonizationCandidatesResponse:
    """Retorna grupos de produtos similares sem gravar ou expor dados fiscais."""

    is_admin = user.role == UserRole.ADMIN
    if not is_admin and user.department_id is None:
        groups, total_groups, safe_threshold, safe_limit = generate_product_match_groups(
            products=[],
            threshold=threshold,
            limit=limit,
            include_reasons=include_reasons,
        )
        return CanonizationCandidatesResponse(
            groups=groups,
            total_groups=total_groups,
            threshold=safe_threshold,
            limit=safe_limit,
        )

    department_id = None if is_admin else user.department_id
    stmt = (
        select(
            Produto.ean,
            Produto.nome_limpo,
            Produto.categoria,
            NotaFiscal.department_id,
        )
        .join(ItemNotaFiscal, ItemNotaFiscal.ean == Produto.ean)
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        .distinct()
        .order_by(Produto.nome_limpo)
        .limit(MAX_PRODUCTS_TO_COMPARE)
    )

    if not is_admin:
        stmt = stmt.where(NotaFiscal.department_id == department_id)

    if category:
        stmt = stmt.where(Produto.categoria == category)

    result = await db.execute(stmt)
    products = [
        ProductMatchInput(
            ean=row.ean,
            name=row.nome_limpo,
            category=row.categoria,
            department_id=row.department_id,
        )
        for row in result.fetchall()
    ]

    groups, total_groups, safe_threshold, safe_limit = generate_product_match_groups(
        products=products,
        threshold=threshold,
        limit=limit,
        include_reasons=include_reasons,
    )

    return CanonizationCandidatesResponse(
        groups=[
            CanonizationCandidateGroup(
                primary=CanonizationProduct(
                    ean=group.primary.ean,
                    name=group.primary.name,
                    category=group.primary.category,
                ),
                matches=[
                    CanonizationMatch(
                        ean=match.ean,
                        name=match.name,
                        category=match.category,
                        similarity=match.similarity,
                        reason=match.reason,
                    )
                    for match in group.matches
                ],
            )
            for group in groups
        ],
        total_groups=total_groups,
        threshold=safe_threshold,
        limit=safe_limit,
    )


@router.get(
    "/canonization/mappings",
    response_model=CanonizationMappingsResponse,
    summary="Listar mapeamentos read-only de canonizacao",
)
async def listar_mapeamentos_canonizacao(
    db: DbSession,
    user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER])),
    status_filter: str = Query(
        "all",
        alias="status",
        pattern="^(all|active|inactive|reverted)$",
    ),
    q: str | None = Query(None, max_length=120),
    department_id: UUID | None = Query(None),
    sort_by: str = Query("updated_at", pattern="^(updated_at|confirmed_at|reverted_at|ean_original|ean_canonico|status|department|original_name|canonical_name)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> CanonizationMappingsResponse:
    """Retorna mapeamentos de canonizacao sem expor dados fiscais."""

    effective_department_id = _resolve_canonization_department(user, department_id)
    safe_query = (q or "").strip() or None
    empty_counts = CanonizationMappingStatusCounts(
        all=0,
        active=0,
        inactive=0,
        reverted=0,
    )
    if user.role != UserRole.ADMIN and user.department_id is None:
        return CanonizationMappingsResponse(
            items=[],
            total=0,
            status=status_filter,
            query=safe_query,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
            counts=empty_counts,
        )

    original_product = aliased(Produto)
    canonical_product = aliased(Produto)

    base_filters = _canonization_mapping_filters(
        original_product,
        canonical_product,
        effective_department_id,
        safe_query,
    )
    filters = [*base_filters]
    if status_filter != "all":
        filters.append(CanonizacaoProduto.status == status_filter)

    count_from = _canonization_mapping_count_from(original_product, canonical_product)
    count_stmt = select(func.count()).select_from(count_from).where(*filters)
    total = await db.scalar(count_stmt)

    status_counts_stmt = (
        select(CanonizacaoProduto.status, func.count())
        .select_from(count_from)
        .where(*base_filters)
        .group_by(CanonizacaoProduto.status)
    )
    status_counts_result = await db.execute(status_counts_stmt)
    status_counts = {status_name: 0 for status_name in CANONIZATION_MAPPING_STATUSES}
    for status_name, count in status_counts_result.fetchall():
        if status_name in status_counts:
            status_counts[status_name] = count

    stmt = (
        _canonization_mapping_base_stmt(original_product, canonical_product)
        .where(*filters)
        .order_by(
            *_canonization_mapping_order(
                sort_by,
                sort_dir,
                original_product,
                canonical_product,
            )
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)

    return CanonizationMappingsResponse(
        items=[_canonization_mapping_item(row) for row in result.fetchall()],
        total=total or 0,
        status=status_filter,
        query=safe_query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
        counts=CanonizationMappingStatusCounts(
            all=sum(status_counts.values()),
            active=status_counts["active"],
            inactive=status_counts["inactive"],
            reverted=status_counts["reverted"],
        ),
    )


@router.get(
    "/canonization/mappings/export",
    summary="Exportar mapeamentos de canonizacao sanitizados",
)
async def exportar_mapeamentos_canonizacao(
    db: DbSession,
    user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER])),
    status_filter: str = Query(
        "all",
        alias="status",
        pattern="^(all|active|inactive|reverted)$",
    ),
    q: str | None = Query(None, max_length=120),
    department_id: UUID | None = Query(None),
    sort_by: str = Query("updated_at", pattern="^(updated_at|confirmed_at|reverted_at|ean_original|ean_canonico|status|department|original_name|canonical_name)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> StreamingResponse:
    """Exporta somente metadados seguros dos mapeamentos de canonizacao."""

    effective_department_id = _resolve_canonization_department(user, department_id)
    safe_query = (q or "").strip() or None

    async def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        def yield_row(row_data: list[Any]):
            sanitized = [sanitize_csv_cell(cell) for cell in row_data]
            output.seek(0)
            output.truncate(0)
            writer.writerow(sanitized)
            return output.getvalue()

        yield yield_row(
            [
                "Departamento",
                "Status",
                "EAN Original",
                "Produto Original",
                "EAN Canonico",
                "Produto Canonico",
                "Confianca",
                "Confirmado Por",
                "Confirmado Em",
                "Revertido Por",
                "Revertido Em",
                "Motivo",
                "Motivo Reversao",
            ]
        )

        if user.role != UserRole.ADMIN and user.department_id is None:
            return

        original_product = aliased(Produto)
        canonical_product = aliased(Produto)
        filters = _canonization_mapping_filters(
            original_product,
            canonical_product,
            effective_department_id,
            safe_query,
        )
        if status_filter != "all":
            filters.append(CanonizacaoProduto.status == status_filter)

        stmt = (
            _canonization_mapping_base_stmt(original_product, canonical_product)
            .where(*filters)
            .order_by(
                *_canonization_mapping_order(
                    sort_by,
                    sort_dir,
                    original_product,
                    canonical_product,
                )
            )
            .limit(5000)
        )
        result = await db.stream(stmt)

        async for row in result:
            item = _canonization_mapping_item(row)
            yield yield_row(
                [
                    item.department_name,
                    item.status,
                    item.ean_original,
                    item.original_name,
                    item.ean_canonico,
                    item.canonical_name,
                    item.confidence_score,
                    item.confirmado_por,
                    item.confirmado_em,
                    item.revertido_por,
                    item.revertido_em,
                    item.reason,
                    item.revert_reason,
                ]
            )

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=canonizacao_mapeamentos.csv"
        },
    )


@router.post(
    "/canonization/confirm",
    response_model=CanonizationConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirmar canonizacao manual de produtos",
)
async def confirmar_canonizacao_produtos(
    payload: CanonizationConfirmationRequest,
    db: DbSession,
    user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER])),
) -> CanonizationConfirmationResponse:
    """Cria mapeamentos logicos de canonizacao sem alterar produtos ou dados fiscais."""

    if payload.confirmed is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmacao explicita e obrigatoria.",
        )

    department_id = payload.department_id
    if user.role == UserRole.MANAGER:
        if user.department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sem departamento vinculado.",
            )
        if department_id is not None and department_id != user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MANAGER nao pode confirmar canonizacao para outro departamento.",
            )
        department_id = user.department_id
    elif department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department_id e obrigatorio para ADMIN.",
        )

    service = ProductCanonizationService(db)
    try:
        result = await service.confirm_canonization(
            ean_canonico=payload.ean_canonico,
            eans_originais=payload.eans_originais,
            department_id=department_id,
            usuario_executor=user.username,
            reason=payload.reason,
        )
    except ProductCanonizationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProductCanonizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProductCanonizationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return CanonizationConfirmationResponse(
        summary=result.summary,
        created_count=result.created_count,
        ean_canonico=result.ean_canonico,
        department_id=result.department_id,
        created_mappings=[
            {
                "ean_original": mapping.ean_original,
                "ean_canonico": mapping.ean_canonico,
                "status": mapping.status,
            }
            for mapping in result.created_mappings
        ],
    )


@router.post(
    "/canonization/revert",
    response_model=CanonizationRevertResponse,
    summary="Reverter canonizacao manual de produto",
)
async def reverter_canonizacao_produto(
    payload: CanonizationRevertRequest,
    db: DbSession,
    user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER])),
) -> CanonizationRevertResponse:
    """Reverte logicamente um mapeamento de canonizacao ativo."""

    if payload.confirmed is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmacao explicita e obrigatoria.",
        )
    revert_reason = (payload.reason or "").strip()
    if not revert_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Motivo da reversao e obrigatorio.",
        )

    department_id = payload.department_id
    if user.role == UserRole.MANAGER:
        if user.department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sem departamento vinculado.",
            )
        if department_id is not None and department_id != user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MANAGER nao pode reverter canonizacao para outro departamento.",
            )
        department_id = user.department_id
    elif department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department_id e obrigatorio para ADMIN.",
        )

    service = ProductCanonizationService(db)
    try:
        result = await service.revert_canonization(
            ean_original=payload.ean_original,
            department_id=department_id,
            usuario_executor=user.username,
            reason=revert_reason,
        )
    except ProductCanonizationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProductCanonizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProductCanonizationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return CanonizationRevertResponse(
        ean_original=result.ean_original,
        ean_canonico=result.ean_canonico,
        department_id=result.department_id,
        status=result.status,
        revertido_por=result.revertido_por,
        revertido_em=result.revertido_em,
        revert_reason=result.revert_reason,
        message=result.summary,
    )


@router.patch(
    "/{ean}",
    response_model=ProdutoResponse,
    summary="Atualizar dados de um produto",
)
async def atualizar_produto(
    ean: str,
    payload: ProdutoUpdate,
    db: DbSession,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER]))],
) -> Any:
    """Atualiza categoria, marca ou nome de um produto e limpa o cache de IA relacionado."""
    stmt = select(Produto).where(Produto.ean == ean)
    result = await db.execute(stmt)
    produto = result.scalar_one_or_none()
    
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    # Atualiza campos
    update_data = payload.model_dump(exclude_unset=True)
    categoria_anterior = produto.categoria
    categoria_nova = update_data.get("categoria")
    categoria_alterada = (
        "categoria" in update_data
        and _categoria_para_comparacao(categoria_anterior) != _categoria_para_comparacao(categoria_nova)
    )

    for field, value in update_data.items():
        setattr(produto, field, value)

    if "categoria" in update_data:
        produto.categoria_confirmada = update_data["categoria"]
        produto.categoria_confirmada_por = user.username
        produto.categoria_confirmada_em = datetime.now(timezone.utc)
        produto.categoria_confirmada_origem = "manual"
    
    # Sincroniza com ClassificacaoCache
    # Isso garante que futuras importações do mesmo item já venham corrigidas.
    # Como o cache é baseado na 'descricao_original', e um produto pode vir de várias descrições,
    # limpamos as entradas antigas no cache que resultavam neste EAN para que a IA re-classifique
    # ou simplesmente atualizamos o cache para a nova categoria preferida.
    
    if "categoria" in update_data:
        # Busca descrições originais vinculadas a este EAN através dos itens de nota
        from backend.models.compras import ItemNotaFiscal
        from core.classificador_regras import _normalizar
        
        # Encontra descrições originais que levaram a este produto
        stmt_desc = select(ItemNotaFiscal.descricao_original).where(ItemNotaFiscal.ean == ean).distinct()
        res_desc = await db.execute(stmt_desc)
        descricoes = res_desc.scalars().all()
        
        for desc in descricoes:
            desc_norm = _normalizar(desc)
            # Atualiza ou insere no cache com a nova verdade definida pelo humano
            cache_stmt = select(ClassificacaoCache).where(ClassificacaoCache.descricao_original == desc_norm)
            cache_res = await db.execute(cache_stmt)
            cache_entry = cache_res.scalar_one_or_none()
            
            if cache_entry:
                cache_entry.categoria = update_data["categoria"]
                if "marca" in update_data:
                    cache_entry.marca = update_data["marca"]
                cache_entry.produto_canonico = produto.nome_limpo
                cache_entry.verificado_usuario = True
            else:
                # Se não existia no cache, cria para blindar futuras importações
                new_cache = ClassificacaoCache(
                    descricao_original=desc_norm,
                    produto_canonico=produto.nome_limpo,
                    categoria=update_data["categoria"],
                    marca=update_data.get("marca", produto.marca),
                    unidade=produto.unidade,
                    verificado_usuario=True
                )
                db.add(new_cache)

    if categoria_alterada:
        stmt_sugestoes = (
            select(ItemNotaFiscal.categoria_sugerida)
            .where(
                ItemNotaFiscal.ean == ean,
                ItemNotaFiscal.categoria_sugerida.is_not(None),
            )
            .distinct()
            .limit(5)
        )
        res_sugestoes = await db.execute(stmt_sugestoes)
        categorias_sugeridas = [categoria for categoria in res_sugestoes.scalars().all() if categoria]
        detalhes = {
            "categoria_anterior": categoria_anterior,
            "categoria_nova": categoria_nova,
            "origem": "manual",
            "usuario": user.username,
            "produto": produto.nome_limpo,
            "categorias_sugeridas_relacionadas": categorias_sugeridas,
        }
        db.add(
            AuditLog(
                usuario=user.username,
                operacao=CATEGORY_CONFIRMED_OPERATION,
                entidade="Produto",
                entidade_id=ean,
                detalhes=json.dumps(
                    _safe_product_audit_details(detalhes),
                    ensure_ascii=True,
                    default=str,
                ),
                department_id=user.department_id,
            )
        )

    await db.commit()
    await db.refresh(produto)
    return produto
