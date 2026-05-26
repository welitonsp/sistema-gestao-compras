"""Rotas versionadas para importacao de notas fiscais."""

from __future__ import annotations

from typing import Any, Annotated
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, status, Request, Depends
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from backend.api.dependencies import DbSession, ArqPool, CurrentUser, HttpClient, RoleChecker
from backend.models.compras import User, UserRole
from backend.core.fiscal import validar_chave_acesso
from backend.schemas.importacao import (
    ArchiveImportacaoRequest,
    ArchiveImportacaoResponse,
    ChaveAcesso44,
    ImportacaoChaveRequest,
    ImportacaoNotaResponse,
    ProcessamentoLoteResponse,
)
from backend.services.import_archive_service import (
    ImportacaoJaArquivadaError,
    ImportacaoNaoEncontradaError,
    ImportArchiveError,
    archive_importacao_por_chave,
)
from backend.services.importador_sefaz import (
    ExtracaoDadosNotaError,
    ImportadorSefazService,
    NotaJaCadastradaError,
    SefazComunicacaoError,
)

from arq.jobs import Job

router = APIRouter(prefix="/notas", tags=["Notas Fiscais"])

DUPLICATE_NOTA_DETAIL = "Nota fiscal ja cadastrada."


def _mascarar_chave_acesso(chave_acesso: str) -> str:
    if len(chave_acesso) < 8:
        return "<chave-redigida>"
    return f"{chave_acesso[:4]}...{chave_acesso[-4:]}"


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
        # Validação P5: Dígito Verificador
        if not validar_chave_acesso(payload.chave_acesso):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dígito verificador da chave de acesso inválido."
            )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensagem": "Payload invalido para importacao por chave.",
                "erros": exc.errors(),
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
    except SefazComunicacaoError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
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
