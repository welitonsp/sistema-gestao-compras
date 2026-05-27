"""Rotas versionadas para importacao de notas fiscais."""

from __future__ import annotations

from typing import Any, Annotated, Literal
from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, Query, status, Request, Depends, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.dependencies import DbSession, ArqPool, CurrentUser, HttpClient, RoleChecker
from backend.models.compras import NotaFiscal, User, UserRole
from backend.core.fiscal import classificar_identificador_importacao, validar_chave_acesso
from backend.schemas.importacao import (
    ArchiveImportacaoRequest,
    ArchiveImportacaoResponse,
    ChaveAcesso44,
    ImportacaoChaveRequest,
    ImportacaoHistoricoItemResponse,
    ImportacaoLoteChavesRequest,
    ImportacaoLoteChavesResponse,
    ImportacaoLoteResultadoResponse,
    ImportacaoNotaResponse,
    ImportacoesHistoricoResponse,
    ProcessamentoLoteResponse,
)
from backend.services.import_archive_service import (
    ImportacaoJaArquivadaError,
    ImportacaoNaoEncontradaError,
    ImportArchiveError,
    archive_importacao_por_chave,
)
from backend.services.nfce_pdf_import import NfcePdfImportError, NfcePdfImportService
from backend.services.repository import ProcurementRepository
from backend.services.importador_sefaz import (
    ExtracaoDadosNotaError,
    ImportacaoSemProdutosError,
    ImportadorSefazService,
    NotaJaCadastradaError,
    SefazConsultaInvalidaError,
    SefazComunicacaoError,
    SefazTransportError,
)

from arq.jobs import Job

router = APIRouter(prefix="/notas", tags=["Notas Fiscais"])

DUPLICATE_NOTA_DETAIL = "Nota fiscal ja cadastrada."


def _mascarar_chave_acesso(chave_acesso: str) -> str:
    if len(chave_acesso) < 8:
        return "<chave-redigida>"
    return f"{chave_acesso[:4]}...{chave_acesso[-4:]}"


def _mascarar_identificador_importacao(identificador: str) -> str:
    classificacao = classificar_identificador_importacao(identificador)
    if classificacao.access_key:
        return _mascarar_chave_acesso(classificacao.access_key)
    if classificacao.qrcode_payload:
        return "<payload-redigido>"
    return "<identificador-redigido>"


def _validar_identificador_importacao(identificador: str) -> tuple[str, str]:
    classificacao = classificar_identificador_importacao(identificador)
    if classificacao.kind == "invalid":
        return "failed", classificacao.error_code or "invalid_identifier"
    if not classificacao.access_key:
        return "failed", classificacao.error_code or "missing_access_key"
    if not validar_chave_acesso(classificacao.access_key):
        return "failed", "invalid_access_key_check_digit"
    return "ok", ""


def _is_chave_acesso_integrity_error(exc: IntegrityError) -> bool:
    """Return whether an IntegrityError came from the invoice access-key uniqueness guard."""

    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
    message = f"{constraint_name} {exc}".lower()
    return (
        "uq_notas_fiscais_chave_acesso" in message
        or "notas_fiscais.chave_acesso" in message
        or "notas_fiscais_chave_acesso" in message
        or ("unique" in message and "chave_acesso" in message)
    )


@router.get(
    "/jobs/{job_id}",
    summary="Consultar status de uma tarefa de background",
)
async def consultar_job(
    job_id: str,
    arq: ArqPool,
    user: CurrentUser,
) -> dict[str, Any]:
    """Retorna o estado atual de um job no processador de tarefas (ARQ)."""
    job = Job(job_id, arq)
    status_job = await job.status()
    result = await job.result_info()
    
    return {
        "job_id": job_id,
        "status": status_job,
        "success": result.success if result else None,
        "result": result.result if result else None,
        "start_time": result.enqueue_time if result else None,
    }

@router.post(
    "/processar-lote",
    response_model=ProcessamentoLoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Processar todos os arquivos em NOVAS_NOTAS em background",
)
async def processar_lote_background(
    arq: ArqPool,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER]))],
) -> ProcessamentoLoteResponse:
    """Detecta arquivos PDF/XML na pasta de entrada e enfileira para processamento."""
    pasta_input = Path("NOVAS_NOTAS")
    if not pasta_input.exists():
        raise HTTPException(status_code=404, detail="Pasta NOVAS_NOTAS não encontrada.")
        
    arquivos = list(pasta_input.glob("*.pdf")) + list(pasta_input.glob("*.xml")) + \
               list(pasta_input.glob("*.jpg")) + list(pasta_input.glob("*.jpeg")) + \
               list(pasta_input.glob("*.png"))
    job_ids = []
    
    for arquivo in arquivos:
        # Enfileira a tarefa no worker com o department_id
        job = await arq.enqueue_job("processar_arquivo_background", str(arquivo), user.department_id)
        job_ids.append(job.job_id)
        
    return ProcessamentoLoteResponse(
        mensagem=f"Processamento de {len(arquivos)} arquivos iniciado em background.",
        total_arquivos=len(arquivos),
        job_ids=job_ids
    )


@router.get(
    "/importacoes",
    response_model=ImportacoesHistoricoResponse,
    summary="Listar historico operacional de importacoes",
)
async def listar_importacoes(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Literal["active", "archived", "all"] = Query("active", alias="status"),
    quality_status: Literal["ok", "warning", "failed", "all"] = Query("all"),
) -> ImportacoesHistoricoResponse:
    """Retorna importacoes recentes com status e qualidade sem expor chave completa."""

    filters = []
    if status_filter != "all":
        filters.append(NotaFiscal.status == status_filter)
    if quality_status != "all":
        filters.append(NotaFiscal.extraction_quality_status == quality_status)
    if user.department_id:
        filters.append(NotaFiscal.department_id == user.department_id)

    total_stmt = select(func.count()).select_from(NotaFiscal).where(*filters)
    total = await db.scalar(total_stmt) or 0

    stmt = (
        select(NotaFiscal)
        .options(selectinload(NotaFiscal.fornecedor))
        .where(*filters)
        .order_by(NotaFiscal.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    notas = result.scalars().all()

    return ImportacoesHistoricoResponse(
        items=[
            ImportacaoHistoricoItemResponse(
                id=nota.id,
                chave_acesso=_mascarar_chave_acesso(nota.chave_acesso),
                numero_nota=nota.numero_nota,
                fornecedor=nota.fornecedor.razao_social,
                data_emissao=nota.data_emissao,
                valor_total=nota.valor_total,
                status=nota.status,
                created_at=nota.created_at,
                imported_at=nota.created_at,
                extraction_quality_status=nota.extraction_quality_status,
                extraction_parser_source=nota.extraction_parser_source,
                extraction_item_count=nota.extraction_item_count,
                extraction_missing_ean_count=nota.extraction_missing_ean_count,
                extraction_total_mismatch=nota.extraction_total_mismatch,
                extraction_quality_details=nota.extraction_quality_details,
                archived_at=nota.archived_at,
                archived_by=nota.archived_by,
                archive_reason=nota.archive_reason,
            )
            for nota in notas
        ],
        total=total,
        limit=limit,
        offset=offset,
        status=status_filter,
        quality_status=quality_status,
    )

@router.post(
    "/importacao-por-chave",
    response_model=ImportacaoNotaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar nota fiscal por chave de acesso",
    description=(
        "Consulta a SEFAZ GO pela chave de acesso, extrai os dados da nota "
        "e persiste fornecedor, nota fiscal e itens de forma atomica."
    ),
)
async def importar_nota_por_chave(
    request: Request,
    db: DbSession,
    client: HttpClient,
    user: CurrentUser,
    payload_bruto: dict[str, Any] = Body(...),
) -> ImportacaoNotaResponse:
    """Executa o fluxo unico de importacao por chave de acesso."""

    try:
        payload = ImportacaoChaveRequest.model_validate(payload_bruto)
        validation_status, _validation_error = _validar_identificador_importacao(payload.chave_acesso)
        if validation_status != "ok":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identificador invalido para importacao por chave.",
            )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensagem": "Payload invalido para importacao por chave.",
                "erros": "Formato invalido.",
            },
        ) from exc

    try:
        servico = ImportadorSefazService(db=db, http_client=client)
        resultado = await servico.importar_por_chave(
            identificador=payload.chave_acesso,
            usuario=user.username,
            ip_origem=request.client.host if request.client else None,
            department_id=user.department_id
        )
        await db.commit()
        return resultado
    except NotaJaCadastradaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_NOTA_DETAIL,
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        if _is_chave_acesso_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DUPLICATE_NOTA_DETAIL,
            ) from exc
        raise
    except SefazTransportError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except SefazComunicacaoError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except SefazConsultaInvalidaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except ImportacaoSemProdutosError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except ExtracaoDadosNotaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception:
        await db.rollback()
        raise


@router.post(
    "/importacao-pdf-nfce",
    response_model=ImportacaoNotaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar NFC-e detalhada por PDF",
    description=(
        "Extrai dados de uma NFC-e detalhada baixada em PDF pelo usuario, "
        "sem consultar SEFAZ, OCR externo ou IA."
    ),
)
async def importar_nfce_pdf(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    arquivo: UploadFile = File(...),
) -> ImportacaoNotaResponse:
    """Importa uma NFC-e detalhada a partir do PDF salvo pelo usuario."""

    filename = arquivo.filename or "nfce.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo PDF invalido para importacao NFC-e.",
        )

    try:
        conteudo = await arquivo.read()
        if not conteudo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo PDF vazio.",
            )
        servico = NfcePdfImportService(ProcurementRepository(db))
        resultado = await servico.importar_pdf_bytes(
            conteudo,
            filename=filename,
            usuario=user.username,
            ip_origem=request.client.host if request.client else None,
            department_id=user.department_id,
        )
        await db.commit()
        return resultado
    except NotaJaCadastradaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_NOTA_DETAIL,
        ) from exc
    except ImportacaoSemProdutosError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NfcePdfImportError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        if _is_chave_acesso_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DUPLICATE_NOTA_DETAIL,
            ) from exc
        raise
    except Exception:
        await db.rollback()
        raise


@router.post(
    "/importacao-lote-chaves",
    response_model=ImportacaoLoteChavesResponse,
    status_code=status.HTTP_200_OK,
    summary="Importar lote pequeno de notas fiscais por chave de acesso",
    description=(
        "Processa sequencialmente ate 5 chaves de acesso, com transacao "
        "isolada por chave e resultado operacional individual."
    ),
)
async def importar_lote_chaves(
    request: Request,
    db: DbSession,
    client: HttpClient,
    user: CurrentUser,
    payload_bruto: dict[str, Any] = Body(...),
) -> ImportacaoLoteChavesResponse:
    """Executa importacao sequencial e controlada de um lote pequeno de chaves."""

    try:
        payload = ImportacaoLoteChavesRequest.model_validate(payload_bruto)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Payload invalido para importacao em lote.",
        ) from exc

    results: list[ImportacaoLoteResultadoResponse] = []

    for chave in payload.chaves_acesso:
        chave_mascarada = _mascarar_identificador_importacao(chave)
        validation_status, validation_error = _validar_identificador_importacao(chave)
        if validation_status != "ok":
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem="Identificador invalido para importacao.",
                    error_code=validation_error,
                )
            )
            continue
        try:
            servico = ImportadorSefazService(db=db, http_client=client)
            resultado = await servico.importar_por_chave(
                identificador=chave,
                usuario=user.username,
                ip_origem=request.client.host if request.client else None,
                department_id=user.department_id,
            )
            await db.commit()
            nota_mascarada = resultado.nota_fiscal.model_copy(
                update={"chave_acesso": chave_mascarada}
            )
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="success",
                    mensagem="Nota fiscal importada com sucesso.",
                    nota_fiscal=nota_mascarada,
                )
            )
        except NotaJaCadastradaError:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="duplicate",
                    mensagem=DUPLICATE_NOTA_DETAIL,
                    error_code="duplicate",
                )
            )
        except IntegrityError as exc:
            await db.rollback()
            if _is_chave_acesso_integrity_error(exc):
                results.append(
                    ImportacaoLoteResultadoResponse(
                        chave_acesso=chave_mascarada,
                        status="duplicate",
                        mensagem=DUPLICATE_NOTA_DETAIL,
                        error_code="duplicate",
                    )
                )
                continue
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem="Falha ao importar esta chave.",
                    error_code="integrity_error",
                )
            )
        except SefazTransportError as exc:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem=str(exc),
                    error_code=exc.error_code,
                )
            )
        except SefazComunicacaoError:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem="Falha ao consultar SEFAZ para esta chave.",
                    error_code="sefaz_error",
                )
            )
        except SefazConsultaInvalidaError as exc:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem=str(exc),
                    error_code=exc.error_code,
                )
            )
        except ImportacaoSemProdutosError as exc:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem=str(exc),
                    error_code="no_items",
                )
            )
        except ExtracaoDadosNotaError:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem="Falha ao extrair dados da nota.",
                    error_code="extraction_error",
                )
            )
        except Exception:
            await db.rollback()
            results.append(
                ImportacaoLoteResultadoResponse(
                    chave_acesso=chave_mascarada,
                    status="failed",
                    mensagem="Falha inesperada ao importar esta chave.",
                    error_code="unexpected_error",
                )
            )

    return ImportacaoLoteChavesResponse(
        total=len(results),
        success_count=sum(1 for result in results if result.status == "success"),
        duplicate_count=sum(1 for result in results if result.status == "duplicate"),
        failed_count=sum(1 for result in results if result.status == "failed"),
        results=results,
    )


@router.post(
    "/{chave_acesso}/archive",
    response_model=ArchiveImportacaoResponse,
    status_code=status.HTTP_200_OK,
    summary="Arquivar importacao por chave de acesso",
    description=(
        "Arquiva uma importacao sem excluir dados fiscais, catalogo, historico "
        "ou trilha de auditoria."
    ),
)
async def arquivar_importacao_por_chave(
    chave_acesso: ChaveAcesso44,
    payload: ArchiveImportacaoRequest,
    db: DbSession,
    user: Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER]))],
) -> ArchiveImportacaoResponse:
    """Arquiva uma importacao existente usando transacao controlada pelo endpoint."""

    if not validar_chave_acesso(chave_acesso):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digito verificador da chave de acesso invalido.",
        )

    try:
        resultado = await archive_importacao_por_chave(
            chave_acesso=chave_acesso,
            usuario=user.username,
            motivo=payload.motivo,
            db=db,
        )
        await db.commit()
        return ArchiveImportacaoResponse(
            mensagem="Importacao arquivada com sucesso.",
            status=resultado.status,
            chave_acesso=_mascarar_chave_acesso(resultado.chave_acesso),
            archived_at=resultado.archived_at,
            archived_by=user.username,
            archive_reason=payload.motivo,
        )
    except ImportacaoNaoEncontradaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Importacao nao encontrada.",
        ) from exc
    except ImportacaoJaArquivadaError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Importacao ja arquivada.",
        ) from exc
    except ImportArchiveError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao arquivar importacao.",
        ) from exc
