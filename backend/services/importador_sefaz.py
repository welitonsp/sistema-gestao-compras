"""Orquestrador de importação de notas fiscais SEFAZ GO."""

from __future__ import annotations

import re
import asyncio
import ssl
from dataclasses import dataclass
from html import unescape
from typing import Any, Literal
from urllib.parse import quote, unquote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.core.fiscal import classificar_identificador_importacao
from backend.models.compras import NotaFiscal
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.extraction_quality import build_extraction_quality
from backend.services.repository import ProcurementRepository
from backend.services.parsers.sefaz_go import SefazGoParser
from backend.services.sefaz_diagnostics import (
    classify_sefaz_html_response,
    summarize_fallback_text,
    summarize_sefaz_html,
)
from core.logger import get_logger, ContextAdapter
from backend.schemas.importacao import (
    FornecedorImportadoResponse,
    ImportacaoNotaResponse,
    ItemNotaFiscalImportadoResponse,
    NotaFiscalImportadaResponse,
)

logger = get_logger("services.importador")
RETRYABLE_SEFAZ_STATUS_CODES = {429, 502, 503, 504}
AI_FALLBACK_TEXT_LIMIT = 20000
SEFAZ_GO_DANFE_NFCE_URL = "https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={payload}"
SEFAZ_ACCESS_KEY_UNSUPPORTED_MESSAGE = (
    "Consulta automatica por chave de acesso NFC-e GO nao esta disponivel sem QR Code completo. "
    "Use a URL completa do QR Code NFC-e, importe PDF/HTML/XML quando suportado, "
    "ou consulte manualmente no portal SEFAZ GO."
)
SEFAZ_NO_INVOICE_CONTENT_MESSAGE = "SEFAZ retornou pagina sem conteudo fiscal suficiente para extracao."
SEFAZ_QRCODE_INCOMPLETE_MESSAGE = "QR Code NFC-e incompleto ou invalido para consulta SEFAZ GO."
IMPORTACAO_SEM_PRODUTOS_MESSAGE = "Não foi possível extrair produtos desta nota. A importação não foi concluída."


@dataclass(frozen=True)
class SefazGoQueryStrategy:
    kind: Literal["access_key", "qrcode_payload", "unsupported"]
    chave_acesso: str
    url: str
    error_code: str | None = None
    error_message: str | None = None


def _mascarar_chave(chave: str) -> str:
    chave = re.sub(r"\D", "", chave or "")
    if len(chave) < 8:
        return "<chave-redigida>"
    return f"{chave[:4]}...{chave[-4:]}"


def _redigir_chaves(texto: str) -> str:
    redigido = re.sub(r"\d{44}", "<chave-redigida>", str(texto))
    redigido = re.sub(r"([?&]p=)[^\s&]+", r"\1<payload-redigido>", redigido)
    redigido = re.sub(r"(chaveAcesso=)[^\s&]+", r"\1<chave-redigida>", redigido)
    return redigido


def _safe_log_info(log, message: str) -> None:
    log_method = getattr(log, "info", None) or getattr(log, "debug", None)
    if log_method:
        log_method(message)


def is_access_key_44_digits(value: str) -> bool:
    return bool(re.fullmatch(r"\d{44}", re.sub(r"\D", "", value or ""))) and "|" not in (value or "")


def is_qrcode_payload(value: str) -> bool:
    return "|" in unquote(value or "")


def _extract_access_key_from_text(value: str) -> str:
    match = re.search(r"\d{44}", value or "")
    return match.group(0) if match else ""


def _extract_qrcode_payload_from_url(value: str) -> str:
    return classificar_identificador_importacao(value).qrcode_payload


def build_sefaz_go_query_strategy(identificador: str) -> SefazGoQueryStrategy:
    raw = (identificador or "").strip()
    classificacao = classificar_identificador_importacao(raw)
    candidate = classificacao.qrcode_payload if classificacao.kind == "qrcode_url" else raw

    if classificacao.kind in {"qrcode_payload", "qrcode_url"}:
        chave_acesso = classificacao.access_key
        if not chave_acesso:
            return SefazGoQueryStrategy(
                kind="unsupported",
                chave_acesso="",
                url="",
                error_code=classificacao.error_code or "sefaz_qrcode_payload_incomplete",
                error_message=SEFAZ_QRCODE_INCOMPLETE_MESSAGE,
            )
        payload_encoded = quote(classificacao.qrcode_payload, safe="")
        return SefazGoQueryStrategy(
            kind="qrcode_payload",
            chave_acesso=chave_acesso,
            url=SEFAZ_GO_DANFE_NFCE_URL.format(payload=payload_encoded),
        )

    if classificacao.kind == "plain_access_key":
        chave_acesso = classificacao.access_key
        return SefazGoQueryStrategy(
            kind="access_key",
            chave_acesso=chave_acesso,
            url="",
            error_code="plain_access_key_not_supported_for_go",
            error_message=SEFAZ_ACCESS_KEY_UNSUPPORTED_MESSAGE,
        )

    return SefazGoQueryStrategy(
        kind="unsupported",
        chave_acesso=classificacao.access_key,
        url="",
        error_code=classificacao.error_code or "sefaz_unsupported_identifier",
        error_message="Identificador SEFAZ GO nao suportado para consulta.",
    )


class NotaJaCadastradaError(Exception):
    """Erro levantado quando a chave de acesso ja existe na base."""


class SefazComunicacaoError(Exception):
    """Erro de comunicacao ou indisponibilidade do servico externo."""


class SefazTransportError(SefazComunicacaoError):
    """Erro de transporte, SSL ou timeout ao consultar a SEFAZ."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "sefaz_transport_error",
        stage: str = "fetch_url",
        chave_mascarada: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.stage = stage
        self.chave_mascarada = chave_mascarada


class SefazConsultaInvalidaError(Exception):
    """Erro controlado para resposta SEFAZ sem conteudo fiscal util."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ExtracaoDadosNotaError(Exception):
    """Erro interno ao estruturar os dados extraidos da consulta externa."""


class ImportacaoSemProdutosError(Exception):
    """Erro levantado quando a extracao nao trouxe produtos importaveis."""


class ImportadorSefazService:
    """Orquestrador (Facade) para importação de notas fiscais."""

    URL_BASE_CONSULTA = SEFAZ_GO_DANFE_NFCE_URL
    USER_AGENT = "SistemaGestaoCompras/2.0 (Procurement AI Agent)"

    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient) -> None:
        self.repo = ProcurementRepository(db)
        self.ai = AIStructuredExtractor()
        self.parser = SefazGoParser()
        self._client = http_client
        self._log = logger

    async def importar_por_chave(
        self, 
        identificador: str, 
        usuario: str = "sistema", 
        ip_origem: str | None = None,
        department_id: str | None = None
    ) -> ImportacaoNotaResponse:
        """Executa o fluxo completo de importação (Chave, URL ou HTML Bruto)."""
        
        # 1. Identificação e Sanitização
        url_consulta = ""
        chave_acesso = ""
        html_pasted = ""
        strategy_error_code: str | None = None
        strategy_error_message: str | None = None

        if identificador.startswith("<html") or "<html>" in identificador.lower() or "<body" in identificador.lower():
            # Caso 2: Usuário colou o HTML bruto
            html_pasted = identificador
            self._log.info("Processando importação via HTML colado.")
            operacao_tipo = "IMPORT_HTML_PASTE"
        else:
            strategy = build_sefaz_go_query_strategy(identificador)
            operacao_tipo = "IMPORT_SEFAZ_GO_QRCODE" if strategy.kind == "qrcode_payload" else "IMPORT_SEFAZ_GO"
            chave_acesso = strategy.chave_acesso
            url_consulta = strategy.url
            strategy_error_code = strategy.error_code
            strategy_error_message = strategy.error_message

        # 2. Fetch/Preparação e Validação de Idempotência
        if chave_acesso:
            self._log = ContextAdapter(logger, {"chave_acesso": _mascarar_chave(chave_acesso)})
            if await self.repo.nota_existe(chave_acesso):
                raise NotaJaCadastradaError("Nota fiscal ja cadastrada.")
            if strategy_error_code:
                raise SefazConsultaInvalidaError(
                    strategy_error_message or "Consulta SEFAZ GO invalida.",
                    error_code=strategy_error_code,
                )
            
            if not html_pasted:
                _safe_log_info(self._log, f"Consultando SEFAZ GO: {_redigir_chaves(url_consulta)}")
                html_content = await self._fetch_url(url_consulta)
            else:
                html_content = html_pasted
        else:
            if strategy_error_code:
                raise SefazConsultaInvalidaError(
                    strategy_error_message or "Consulta SEFAZ GO invalida.",
                    error_code=strategy_error_code,
                )
            html_content = html_pasted

        html_summary = summarize_sefaz_html(html_content)
        _safe_log_info(self._log, f"Diagnostico sanitizado do HTML SEFAZ: {html_summary}")
        html_error_code = classify_sefaz_html_response(html_summary)
        if html_error_code:
            message = (
                SEFAZ_ACCESS_KEY_UNSUPPORTED_MESSAGE
                if html_error_code == "sefaz_invalid_parameters"
                else SEFAZ_NO_INVOICE_CONTENT_MESSAGE
            )
            raise SefazConsultaInvalidaError(message, error_code=html_error_code)

        # 3. Extração (Parser Determinístico -> Fallback IA)
        if department_id is None:
            categorias_contexto = await self.repo.obter_categorias_unicas()
        else:
            categorias_contexto = await self.repo.obter_categorias_unicas(
                department_id=department_id
            )
        nota_dto = self.parser.parse(html_content)
        
        if not nota_dto:
            parser_source = "ai_fallback"
            texto_limpo, html_truncated, clean_text_length = self._limpar_html_com_metadados(html_content)
            fallback_summary = summarize_fallback_text(
                texto_limpo,
                html_truncated=html_truncated,
                clean_text_length=clean_text_length,
                text_limit=AI_FALLBACK_TEXT_LIMIT,
            )
            _safe_log_info(self._log, f"Diagnostico sanitizado do texto enviado ao fallback IA: {fallback_summary}")
            quality_details: dict[str, Any] = {}
            if html_truncated:
                quality_details = {
                    "html_truncated": True,
                    "clean_text_length": clean_text_length,
                    "ai_fallback_text_limit": AI_FALLBACK_TEXT_LIMIT,
                }
                self._log.warning(
                    "HTML limpo para fallback IA excedeu o limite e foi truncado "
                    f"(limite={AI_FALLBACK_TEXT_LIMIT}, tamanho_limpo={clean_text_length})."
                )
            ai_scope = {"department_id": department_id} if department_id is not None else {}
            nota_dto = await self.ai.extrair_nota(
                texto_limpo,
                categorias_contexto=categorias_contexto,
                **ai_scope,
            )
            if chave_acesso: nota_dto.chave_acesso = chave_acesso
        else:
            parser_source = "deterministic"
            quality_details = {}
            # Enriquecimento: O parser determinístico não categoriza, chamamos IA para os itens
            # Isso garante que mesmo notas parseadas via CSS tenham categorias inteligentes
            ai_scope = {"department_id": department_id} if department_id is not None else {}
            nota_dto.itens = await self.ai.classificar_itens_lote(
                nota_dto.itens,
                categorias_contexto,
                **ai_scope,
            )

        chave_final = chave_acesso or nota_dto.chave_acesso
        extraction_quality = build_extraction_quality(
            nota_dto,
            parser_source=parser_source,
            details=quality_details,
        )

        if (
            not nota_dto.itens
            or extraction_quality.item_count == 0
            or (
                extraction_quality.quality_status == "failed"
                and extraction_quality.extracted_item_count == 0
            )
        ):
            self._log.warning(
                "Importacao bloqueada porque nenhum produto foi extraido "
                f"(chave={_mascarar_chave(chave_final)}, origem={parser_source})."
            )
            raise ImportacaoSemProdutosError(IMPORTACAO_SEM_PRODUTOS_MESSAGE)

        # 4. Persistência Atômica com Auditoria
        # Removemos o begin() explícito daqui, pois a transação deve ser gerenciada
        # preferencialmente no nível do Caller (API ou script de teste) 
        # ou usamos a sessão injetada.
        
        # Re-valida existência
        if await self.repo.nota_existe(chave_final):
            raise NotaJaCadastradaError("Nota fiscal ja cadastrada.")
        
        nota_db = await self.repo.salvar_nota_completa(
            chave_final,
            nota_dto,
            department_id=department_id,
            extraction_quality=extraction_quality,
        )
        
        # Registrar auditoria
        await self.repo.registrar_auditoria(
            usuario=usuario,
            operacao=operacao_tipo,
            entidade="NotaFiscal",
            entidade_id=chave_final,
            detalhes=f"Importação de {len(nota_dto.itens)} itens. Total: {nota_dto.valor_total}",
            ip=ip_origem,
            department_id=department_id
        )

        # Flush garante que os IDs foram gerados sem fechar a transação
        await self.repo.db.flush()

        # Recarrega a nota com relacionamentos para evitar erro de lazy-loading no async
        stmt = select(NotaFiscal).where(NotaFiscal.id == nota_db.id).options(
            selectinload(NotaFiscal.fornecedor),
            selectinload(NotaFiscal.itens)
        )
        res = await self.repo.db.execute(stmt)
        nota_db = res.scalar_one()

        self._log.info(f"Nota {_mascarar_chave(chave_final)} importada e auditada com sucesso.")

        # 6. Resposta Formatada
        return ImportacaoNotaResponse(
            mensagem="Nota fiscal importada com sucesso.",
            fornecedor=FornecedorImportadoResponse.model_validate(nota_db.fornecedor),
            nota_fiscal=NotaFiscalImportadaResponse.model_validate(nota_db),
            itens=[
                ItemNotaFiscalImportadoResponse.model_validate(item)
                for item in nota_db.itens
            ],
            total_itens=len(nota_db.itens),
        )

    async def _fetch_url(self, url: str) -> str:
        if not self._client:
            raise RuntimeError("Cliente HTTP não iniciado.")

        chave_mascarada = _mascarar_chave(_extract_access_key_from_text(url))
        max_retries = settings.sefaz_max_retries
        timeout_seconds = settings.sefaz_request_timeout_seconds
        backoff_base = settings.sefaz_backoff_base_seconds

        for attempt in range(1, max_retries + 1):
            try:
                resp = await self._client.get(
                    url,
                    timeout=timeout_seconds,
                    headers={"User-Agent": self.USER_AGENT},
                )
                resp.raise_for_status()
                _safe_log_info(
                    self._log,
                    "Resposta SEFAZ recebida "
                    f"(status_code={resp.status_code}, content_length={len(resp.text)}, url={_redigir_chaves(str(resp.url))})."
                )
                return resp.text
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code not in RETRYABLE_SEFAZ_STATUS_CODES:
                    self._log.warning(
                        "Falha nao transitoria ao consultar SEFAZ "
                        f"(tentativa {attempt}/{max_retries}, status={status_code}): {_redigir_chaves(str(exc))}"
                    )
                    raise SefazComunicacaoError("Falha ao consultar SEFAZ.")
                if attempt == max_retries:
                    self._log.error(
                        "Falha transitoria definitiva ao consultar SEFAZ "
                        f"apos {max_retries} tentativas (status={status_code}): {_redigir_chaves(str(exc))}"
                    )
                    raise SefazComunicacaoError("Falha ao consultar SEFAZ (tentativas esgotadas).")
            except httpx.TimeoutException as exc:
                if attempt == max_retries:
                    self._log.error(
                        "Timeout definitivo ao consultar SEFAZ "
                        f"apos {max_retries} tentativas: {_redigir_chaves(str(exc))}"
                    )
                    raise SefazTransportError(
                        "Falha ao consultar SEFAZ (timeout).",
                        error_code="sefaz_timeout",
                        stage="fetch_url",
                        chave_mascarada=chave_mascarada,
                    )
            except (httpx.TransportError, ssl.SSLError) as exc:
                if attempt == max_retries:
                    self._log.error(
                        "Falha de transporte definitiva ao consultar SEFAZ "
                        f"apos {max_retries} tentativas: {_redigir_chaves(str(exc))}"
                    )
                    raise SefazTransportError(
                        "Falha de transporte ao consultar SEFAZ.",
                        error_code="sefaz_transport_error",
                        stage="fetch_url",
                        chave_mascarada=chave_mascarada,
                    )

            wait_time = backoff_base * (2 ** (attempt - 1))
            self._log.warning(
                f"Falha transitoria ao consultar SEFAZ na tentativa {attempt}/{max_retries}. "
                f"Retentando em {wait_time}s."
            )
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        return "" # Unreachable

    def _limpar_html(self, html: str) -> str:
        texto_limpo, _html_truncated, _clean_text_length = self._limpar_html_com_metadados(html)
        return texto_limpo

    def _limpar_html_com_metadados(self, html: str) -> tuple[str, bool, int]:
        """Sanitização equilibrada do HTML para reduzir tokens mantendo contexto."""
        # Remove scripts e estilos
        texto = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # Mantém algumas tags de estrutura ou apenas remove tags e colapsa espaços
        texto = re.sub(r"<[^>]+>", " ", texto)
        texto = unescape(texto)
        # Limita a 20.000 caracteres para dar mais margem à IA
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto[:AI_FALLBACK_TEXT_LIMIT], len(texto) > AI_FALLBACK_TEXT_LIMIT, len(texto)
