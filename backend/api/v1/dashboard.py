"""Routes for dashboard and price insights."""

from enum import Enum
from datetime import date, datetime
from typing import Any, Annotated
from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import StreamingResponse
import io
import csv
from backend.api.dependencies import DbSession, CurrentUser
from backend.core.csv_utils import sanitize_csv_cell
from backend.schemas.dashboard import (
    DashboardResumoResponse,
    AlertasPrecoResponse,
    DashboardComparisonResponse,
    ProductPriceHistoryResponse,
    SavingOpportunitiesSummary,
    SupplierDrilldownResponse,
)
from backend.services.insights_processor import PriceInsightsService
from sqlalchemy import select, func, desc
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import (
    HistoricoPreco,
    AuditLog,
    UserRole,
    User,
    NotaFiscal,
    ItemNotaFiscal,
)

from backend.services.notifications import dispatcher
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Insights"])

ACTIVE_INVOICE_STATUS = "active"


class ExportDataset(str, Enum):
    top_produtos = "top_produtos"
    top_fornecedores = "top_fornecedores"
    evolucao_mensal = "evolucao_mensal"
    alertas = "alertas"


@router.get(
    "/export",
    summary="Exportar dados do dashboard (CSV - Seguro)",
)
async def export_dashboard_csv(
    db: DbSession,
    user: CurrentUser,
    dataset: ExportDataset = Query(..., description="Dataset para exportação"),
    start_date: date | None = Query(None, description="Data inicial"),
    end_date: date | None = Query(None, description="Data final"),
) -> StreamingResponse:
    """
    Exporta visões agregadas do dashboard para CSV de forma segura.
    Aplica sanitização anti-injection e respeita isolamento de departamento.
    """
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dashboard_{dataset.value}_{timestamp}.csv"

    async def generate_csv():
        # UTF-8 com BOM para Excel reconhecer acentos em PT-BR imediatamente
        yield "\ufeff"

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        def yield_row(row_data: list[Any]):
            sanitized = [sanitize_csv_cell(cell) for cell in row_data]
            output.seek(0)
            output.truncate(0)
            writer.writerow(sanitized)
            return output.getvalue()

        if dataset == ExportDataset.top_produtos:
            yield yield_row(
                ["Produto", "EAN", "Quantidade Total", "Preço Médio", "Total Gasto"]
            )
            items = await service.obter_top_produtos_gasto(
                limit=1000,
                department_id=dept_id,
                start_date=start_date,
                end_date=end_date,
            )
            for item in items:
                yield yield_row(
                    [
                        item["produto"],
                        item["ean"],
                        item["quantidade_total"],
                        item["preco_medio"],
                        item["total"],
                    ]
                )

        elif dataset == ExportDataset.top_fornecedores:
            yield yield_row(
                ["Fornecedor", "Quantidade de Notas", "Ticket Médio", "Total Gasto"]
            )
            items = await service.obter_top_fornecedores_gasto(
                limit=1000,
                department_id=dept_id,
                start_date=start_date,
                end_date=end_date,
            )
            for item in items:
                yield yield_row(
                    [
                        item["fornecedor"],
                        item["quantidade_notas"],
                        item["ticket_medio"],
                        item["total"],
                    ]
                )

        elif dataset == ExportDataset.evolucao_mensal:
            yield yield_row(["Mês", "Total Gasto", "Quantidade de Notas"])
            items = await service.obter_evolucao_gastos_mensal(
                department_id=dept_id, start_date=start_date, end_date=end_date
            )
            for item in items:
                yield yield_row(
                    [item["mes"], item["total"], item["quantidade_notas"]]
                )

        elif dataset == ExportDataset.alertas:
            yield yield_row(["Tipo", "Nível", "Mensagem"])
            alertas = await service.obter_alertas_risco_basicos(
                department_id=dept_id, start_date=start_date, end_date=end_date
            )
            for a in alertas:
                yield yield_row([a["tipo"], a["severidade"], a["mensagem"]])

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/notifications", summary="Stream de notificações em tempo real (SSE)")
async def stream_notifications(user: CurrentUser):
    """
    Mantém uma conexão aberta para envio de eventos em tempo real para o frontend.
    """
    return StreamingResponse(dispatcher.subscribe(), media_type="text/event-stream")


@router.get(
    "/audit-logs/export",
    summary="Exportar logs de auditoria (CSV - Streamed)",
)
async def exportar_audit_logs(
    db: DbSession,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER]))],
) -> StreamingResponse:
    """Exporta a trilha de auditoria via streaming para suportar grandes volumes (Zero-OOM)."""

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
            ["Data/Hora", "Usuario", "Operacao", "Entidade", "Detalhes", "IP de Origem"]
        )

        # Stream do Banco via Async iterator do SQLAlchemy
        stmt = select(AuditLog)
        if user.role != UserRole.ADMIN:
            stmt = stmt.where(AuditLog.department_id == user.department_id)
        stmt = stmt.order_by(desc(AuditLog.created_at))
        result = await db.stream(stmt)  # Uso de stream() para carregar em chunks do DB

        async for row in result:
            log = row[0]
            data_str = (
                log.created_at.strftime("%d/%m/%Y %H:%M:%S") if log.created_at else ""
            )
            yield yield_row(
                [
                    data_str,
                    log.usuario,
                    log.operacao,
                    log.entidade,
                    log.detalhes,
                    log.ip_origem,
                ]
            )

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auditoria_logs.csv"},
    )


@router.get(
    "/audit-logs",
    summary="Listar logs de auditoria",
)
async def listar_audit_logs(
    db: DbSession,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER]))],
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retorna a trilha de auditoria do sistema com isolamento de departamento."""

    stmt = select(AuditLog)

    # RLS: Se não for ADMIN global, filtra pelo departamento do usuário
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(AuditLog.department_id == user.department_id)

    stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "usuario": log.usuario,
            "operacao": log.operacao,
            "entidade": log.entidade,
            "entidade_id": log.entidade_id,
            "detalhes": log.detalhes,
            "ip_origem": log.ip_origem,
            "criado_em": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get(
    "/resumo",
    response_model=DashboardResumoResponse,
    summary="Obter resumo de gastos consolidado",
)
async def obter_resumo_dashboard(
    db: DbSession,
    user: CurrentUser,
    start_date: date | None = Query(None, description="Data inicial do filtro"),
    end_date: date | None = Query(None, description="Data final do filtro"),
) -> DashboardResumoResponse:
    """Retorna o resumo consolidado de gastos com suporte a filtros de período."""
    service = PriceInsightsService(db)

    dept_id = user.department_id if user.role != UserRole.ADMIN else None

    # Total Geral filtrado
    stmt_total = (
        select(func.sum(ItemNotaFiscal.valor_total))
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
    )
    if dept_id:
        stmt_total = stmt_total.where(NotaFiscal.department_id == dept_id)

    if start_date:
        stmt_total = stmt_total.where(NotaFiscal.data_emissao >= start_date)
    if end_date:
        stmt_total = stmt_total.where(NotaFiscal.data_emissao <= end_date)

    total_geral = await db.scalar(stmt_total) or 0

    # Por Categoria
    resumo_categorias = await service.obter_resumo_gastos_por_categoria(
        department_id=dept_id, start_date=start_date, end_date=end_date
    )

    # Evolução Mensal
    evolucao_mensal = await service.obter_evolucao_gastos_mensal(
        department_id=dept_id, start_date=start_date, end_date=end_date
    )

    # Top Produtos
    top_produtos = await service.obter_top_produtos_gasto(
        limit=10, department_id=dept_id, start_date=start_date, end_date=end_date
    )

    # Top Fornecedores
    top_fornecedores = await service.obter_top_fornecedores_gasto(
        limit=10, department_id=dept_id, start_date=start_date, end_date=end_date
    )

    # Alertas de Risco (Geral)
    alertas_risco = await service.obter_alertas_risco_basicos(
        department_id=dept_id, start_date=start_date, end_date=end_date
    )

    # Saúde dos Dados
    saude_dados = await service.obter_saude_dados(
        department_id=dept_id, start_date=start_date, end_date=end_date
    )

    return DashboardResumoResponse(
        total_geral=total_geral,
        por_categoria=resumo_categorias,
        evolucao_mensal=evolucao_mensal,
        top_produtos=top_produtos,
        top_fornecedores=top_fornecedores,
        alertas_risco=alertas_risco,
        saude_dados=saude_dados,
    )


@router.get(
    "/oportunidades/economia",
    response_model=SavingOpportunitiesSummary,
    summary="Obter oportunidades de economia",
)
async def obter_oportunidades_economia(
    db: DbSession,
    user: CurrentUser,
    start_date: date | None = Query(None, description="Data inicial do filtro"),
    end_date: date | None = Query(None, description="Data final do filtro"),
    limit: int = Query(
        10, ge=1, le=50, description="Quantidade máxima de oportunidades"
    ),
) -> SavingOpportunitiesSummary:
    """Retorna oportunidades determinísticas de economia com isolamento de departamento."""
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be greater than or equal to start_date",
        )

    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None

    try:
        return await service.get_saving_opportunities(
            department_id=dept_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/comparativo",
    response_model=DashboardComparisonResponse,
    summary="Comparar indicadores do dashboard entre dois periodos",
)
async def obter_comparativo_dashboard(
    db: DbSession,
    user: CurrentUser,
    current_start: date = Query(..., description="Inicio do periodo atual"),
    current_end: date = Query(..., description="Fim do periodo atual"),
    previous_start: date = Query(..., description="Inicio do periodo anterior"),
    previous_end: date = Query(..., description="Fim do periodo anterior"),
    dimension: str = Query(
        "all",
        pattern="^(all|products|suppliers|categories|summary)$",
        description="Dimensao comparativa desejada",
    ),
    limit: int = Query(10, ge=1, le=50),
) -> DashboardComparisonResponse:
    """Retorna comparativo analitico sem expor dados fiscais sensiveis."""

    if current_end < current_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_end must be greater than or equal to current_start",
        )
    if previous_end < previous_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="previous_end must be greater than or equal to previous_start",
        )

    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_comparativo_dashboard(
        department_id=dept_id,
        current_start=current_start,
        current_end=current_end,
        previous_start=previous_start,
        previous_end=previous_end,
        dimension=dimension,
        limit=limit,
    )



@router.get(
    "/produtos/{ean}/historico",
    response_model=ProductPriceHistoryResponse,
    summary="Obter histórico de preço de um produto",
)
async def obter_historico_produto(
    ean: str,
    db: DbSession,
    user: CurrentUser,
) -> ProductPriceHistoryResponse:
    """Retorna a série histórica de compras de um produto (EAN)."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    res = await service.obter_historico_preco_produto(ean, department_id=dept_id)
    return ProductPriceHistoryResponse(**res)


@router.get(
    "/fornecedores/{fornecedor_id}/detalhes",
    response_model=SupplierDrilldownResponse,
    summary="Obter detalhes e histórico de um fornecedor",
)
async def obter_detalhes_fornecedor(
    fornecedor_id: str,
    db: DbSession,
    user: CurrentUser,
    start_date: date | None = Query(None, description="Data inicial do filtro"),
    end_date: date | None = Query(None, description="Data final do filtro"),
) -> SupplierDrilldownResponse | dict:
    """Retorna KPIs e histórico de notas de um fornecedor."""
    from fastapi import HTTPException

    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None

    res = await service.obter_detalhes_fornecedor(
        fornecedor_id=fornecedor_id,
        department_id=dept_id,
        start_date=start_date,
        end_date=end_date,
    )

    if not res:
        raise HTTPException(
            status_code=404, detail="Fornecedor não encontrado ou sem acesso."
        )

    return SupplierDrilldownResponse(**res)


@router.get(
    "/fornecedores/{fornecedor_id}/export",
    summary="Exportar produtos de um fornecedor (CSV)",
)
async def export_fornecedor_produtos_csv(
    fornecedor_id: str,
    db: DbSession,
    user: CurrentUser,
    start_date: date | None = Query(None, description="Data inicial"),
    end_date: date | None = Query(None, description="Data final"),
) -> StreamingResponse:
    """
    Exporta a lista de produtos comprados de um fornecedor específico em formato CSV.
    Respeita isolamento de departamento e aplica sanitização anti-injection.
    """
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitiza filename para evitar problemas com IDs estranhos
    safe_id = "".join(c for c in fornecedor_id if c.isalnum() or c in "-_")
    filename = f"fornecedor_{safe_id}_produtos_{timestamp}.csv"

    async def generate_csv():
        # UTF-8 com BOM para Excel reconhecer acentos em PT-BR imediatamente
        yield "\ufeff"

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
                "Produto",
                "EAN",
                "Quantidade Total",
                "Preço Médio",
                "Total Gasto",
                "Frequência Notas",
            ]
        )

        items = await service.obter_produtos_fornecedor_export(
            fornecedor_id=fornecedor_id,
            department_id=dept_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        for item in items:
            yield yield_row(
                [
                    item["produto"],
                    item["ean"],
                    item["quantidade_total"],
                    item["preco_medio"],
                    item["total_gasto"],
                    item["frequencia_notas"],
                ]
            )

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/alertas",
    response_model=AlertasPrecoResponse,
    summary="Obter alertas de variação de preço",
)
async def obter_alertas_preco(
    db: DbSession,
    user: CurrentUser,
    threshold: float = Query(
        15.0, description="Limiar percentual para detecção de anomalias"
    ),
) -> AlertasPrecoResponse:
    """Retorna produtos com variações de preço anômalas com isolamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    alertas = await service.detectar_variacoes_anomalas(
        threshold_percent=threshold, department_id=dept_id
    )
    return AlertasPrecoResponse(alertas=alertas)


@router.get(
    "/alertas/duplicidade",
    summary="Detectar possíveis notas duplicadas",
)
async def obter_duplicatas_suspeitas(
    db: DbSession,
    user: Annotated[
        User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))
    ],
) -> list[dict[str, Any]]:
    """Identifica notas duplicadas com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.detectar_notas_duplicadas_suspeitas(department_id=dept_id)


@router.get(
    "/alertas/estatisticos",
    summary="Detectar anomalias via Z-Score",
)
async def obter_anomalias_estatisticas(
    db: DbSession,
    user: Annotated[
        User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))
    ],
    z_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    """Identifica preços fora da curva com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.detectar_anomalias_estatisticas(
        z_threshold=z_threshold, department_id=dept_id
    )


@router.get(
    "/insights/tendencia",
    summary="Obter tendência de preços mensal",
)
async def obter_tendencia(
    db: DbSession,
    user: Annotated[
        User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))
    ],
) -> list[dict[str, Any]]:
    """Retorna a evolução dos preços médios por mês com isolamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_tendencia_precos(department_id=dept_id)


@router.get(
    "/insights/forecast",
    summary="Obter previsão de gastos para o próximo mês",
)
async def obter_forecast(
    db: DbSession,
    user: Annotated[
        User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))
    ],
) -> list[dict[str, Any]]:
    """Projeção de gastos com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_forecast_gastos(department_id=dept_id)


@router.get(
    "/insights/volatilidade",
    summary="Obter produtos com maior volatilidade de preço",
)
async def obter_volatilidade(
    db: DbSession,
    user: Annotated[
        User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR]))
    ],
) -> list[dict[str, Any]]:
    """Retorna volatilidade com isolamento de departamento."""
    service = PriceInsightsService(db)
    dept_id = user.department_id if user.role != UserRole.ADMIN else None
    return await service.obter_produtos_mais_volateis(department_id=dept_id)
