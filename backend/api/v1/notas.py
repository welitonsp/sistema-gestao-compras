"""Rotas versionadas para importacao de notas fiscais."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import ValidationError

from backend.api.dependencies import DbSession, ArqPool
from backend.schemas.importacao import ImportacaoChaveRequest, ImportacaoNotaResponse, ProcessamentoLoteResponse
from backend.services.importador_sefaz import (
    ExtracaoDadosNotaError,
    ImportadorSefazService,
    NotaJaCadastradaError,
    SefazComunicacaoError,
)

router = APIRouter(prefix="/notas", tags=["Notas Fiscais"])

@router.post(
    "/processar-lote",
    response_model=ProcessamentoLoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Processar todos os arquivos em NOVAS_NOTAS em background",
)
async def processar_lote_background(arq: ArqPool) -> ProcessamentoLoteResponse:
    """Detecta arquivos PDF/XML na pasta de entrada e enfileira para processamento."""
    pasta_input = Path("NOVAS_NOTAS")
    if not pasta_input.exists():
        raise HTTPException(status_code=404, detail="Pasta NOVAS_NOTAS não encontrada.")
        
    arquivos = list(pasta_input.glob("*.pdf")) + list(pasta_input.glob("*.xml")) + \
               list(pasta_input.glob("*.jpg")) + list(pasta_input.glob("*.jpeg")) + \
               list(pasta_input.glob("*.png"))
    job_ids = []
    
    for arquivo in arquivos:
        # Enfileira a tarefa no worker
        job = await arq.enqueue_job("processar_arquivo_background", str(arquivo))
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
    db: DbSession,
    payload_bruto: dict[str, Any] = Body(...),
) -> ImportacaoNotaResponse:
    """Executa o fluxo unico de importacao por chave de acesso."""

    try:
        payload = ImportacaoChaveRequest.model_validate(payload_bruto)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensagem": "Payload invalido para importacao por chave.",
                "erros": exc.errors(),
            },
        ) from exc

    try:
        async with ImportadorSefazService(db=db) as servico:
            return await servico.importar_por_chave(payload.chave_acesso)
    except NotaJaCadastradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except SefazComunicacaoError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ExtracaoDadosNotaError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
