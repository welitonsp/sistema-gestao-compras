"""Routes for product catalog management."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Annotated
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.responses import StreamingResponse
import io
import pandas as pd
from sqlalchemy import select, or_
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import AuditLog, Produto, ClassificacaoCache, UserRole, User, ItemNotaFiscal, NotaFiscal
from backend.schemas.produtos import ProdutoResponse, ProdutoUpdate

from backend.services.catalog_healer import CatalogHealerService

router = APIRouter(prefix="/produtos", tags=["Produtos"])

ACTIVE_INVOICE_STATUS = "active"
CATEGORY_CONFIRMED_OPERATION = "CATEGORY_CONFIRMED"


def _categoria_para_comparacao(categoria: str | None) -> str:
    return (categoria or "").strip()


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
        yield "EAN/Codigo;Descricao Canonica;Marca;Categoria;Unidade\n"
        
        stmt = select(Produto).where(_produto_operacional_filter()).order_by(Produto.nome_limpo)
        result = await db.stream(stmt)
        
        async for row in result:
            p = row[0]
            marca = (p.marca or "").replace(";", ",")
            nome = p.nome_limpo.replace(";", ",")
            yield f"{p.ean};{nome};{marca};{p.categoria};{p.unidade}\n"

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
    return result.scalars().all()

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
                detalhes=json.dumps(detalhes, ensure_ascii=True, default=str),
                department_id=user.department_id,
            )
        )

    await db.commit()
    await db.refresh(produto)
    return produto
