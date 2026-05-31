from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from backend.services.importador_sefaz import (
    NotaJaCadastradaError,
    SefazConsultaInvalidaError,
    SefazComunicacaoError,
    SefazTransportError,
    ImportacaoSemProdutosError,
)
from backend.services.nfce_pdf_import import NfcePdfImportError
from backend.services.import_archive_service import (
    ImportacaoJaArquivadaError,
    ImportacaoNaoEncontradaError,
)
from backend.services.import_delete_service import (
    ImportDeleteNotFoundError,
)

def register_error_handlers(app: FastAPI):
    """Mapeia exceções de domínio para respostas HTTP padronizadas."""

    @app.exception_handler(NotaJaCadastradaError)
    async def nota_ja_cadastrada_handler(request: Request, exc: NotaJaCadastradaError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc) or "Nota fiscal ja cadastrada."},
        )

    @app.exception_handler(SefazConsultaInvalidaError)
    async def sefaz_consulta_invalida_handler(request: Request, exc: SefazConsultaInvalidaError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "error_code": exc.error_code},
        )

    @app.exception_handler(SefazComunicacaoError)
    async def sefaz_comunicacao_handler(request: Request, exc: SefazComunicacaoError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc) or "Falha de comunicacao com a SEFAZ."},
        )

    @app.exception_handler(SefazTransportError)
    async def sefaz_transport_handler(request: Request, exc: SefazTransportError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": str(exc),
                "error_code": exc.error_code,
                "stage": exc.stage
            },
        )

    @app.exception_handler(ImportacaoSemProdutosError)
    async def importacao_sem_produtos_handler(request: Request, exc: ImportacaoSemProdutosError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "error_code": "no_items"},
        )

    @app.exception_handler(NfcePdfImportError)
    async def nfce_pdf_import_handler(request: Request, exc: NfcePdfImportError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "error_code": exc.error_code},
        )

    @app.exception_handler(ImportacaoNaoEncontradaError)
    @app.exception_handler(ImportDeleteNotFoundError)
    async def not_found_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ImportacaoJaArquivadaError)
    async def already_archived_handler(request: Request, exc: ImportacaoJaArquivadaError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )
