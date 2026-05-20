"""Orquestrador de importação de notas fiscais SEFAZ GO."""

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.ai_processor import AIStructuredExtractor
from backend.services.repository import ProcurementRepository
from backend.services.parsers.sefaz_go import SefazGoParser
from core.logger import get_logger, ContextAdapter
from backend.schemas.importacao import (
    FornecedorImportadoResponse,
    ImportacaoNotaResponse,
    ItemNotaFiscalImportadoResponse,
    NotaFiscalImportadaResponse,
)

logger = get_logger("services.importador")


class NotaJaCadastradaError(Exception):
    """Erro levantado quando a chave de acesso ja existe na base."""


class SefazComunicacaoError(Exception):
    """Erro de comunicacao ou indisponibilidade do servico externo."""


class ExtracaoDadosNotaError(Exception):
    """Erro interno ao estruturar os dados extraidos da consulta externa."""


class ImportadorSefazService:
    """Orquestrador (Facade) para importação de notas fiscais."""

    URL_BASE_CONSULTA = "https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p={chave}"
    USER_AGENT = "SistemaGestaoCompras/2.0 (Procurement AI Agent)"

    def __init__(self, db: AsyncSession, timeout: float = 30.0) -> None:
        self.repo = ProcurementRepository(db)
        self.ai = AIStructuredExtractor()
        self.parser = SefazGoParser()
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._log = logger

    async def __aenter__(self) -> ImportadorSefazService:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout), follow_redirects=True)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()

    async def importar_por_chave(self, identificador: str) -> ImportacaoNotaResponse:
        """Executa o fluxo completo de importação (Chave, URL ou HTML Bruto)."""
        
        # 1. Identificação e Sanitização
        url_consulta = ""
        chave_acesso = ""
        html_pasted = ""

        if identificador.startswith("<html") or "<html>" in identificador.lower() or "<body" in identificador.lower():
            # Caso 2: Usuário colou o HTML bruto (após consulta manual com CAPTCHA)
            html_pasted = identificador
            self._log.info("Processando importação via HTML colado (Pasted HTML).")
        elif identificador.startswith("http"):
            # Caso 1: É uma URL do QR Code
            url_consulta = identificador
            match = re.search(r"p=([0-9]{44})", identificador)
            if match:
                chave_acesso = match.group(1)
            else:
                match_digits = re.search(r"(\d{44})", identificador)
                if match_digits:
                    chave_acesso = match_digits.group(1)
                else:
                    raise ExtracaoDadosNotaError("URL inválida ou chave de acesso não encontrada na URL.")
        else:
            # Caso 3: É apenas a chave (gera URL de consulta padrão)
            chave_acesso = re.sub(r"\D", "", identificador)
            if len(chave_acesso) != 44:
                raise ExtracaoDadosNotaError(f"Chave de acesso inválida (tamanho: {len(chave_acesso)}).")
            url_consulta = self.URL_BASE_CONSULTA.format(chave=chave_acesso)

        # 2. Fetch/Preparação do HTML
        if html_pasted:
            html_content = html_pasted
        else:
            # Contextualiza os logs para esta importação
            self._log = ContextAdapter(logger, {"chave_acesso": chave_acesso})
            # Validação de Idempotência
            if await self.repo.nota_existe(chave_acesso):
                self._log.warning("Nota fiscal já cadastrada no sistema.")
                raise NotaJaCadastradaError(f"Nota {chave_acesso} já cadastrada.")
            
            self._log.debug(f"Consultando portal SEFAZ GO. URL: {url_consulta[:60]}...")
            html_content = await self._fetch_url(url_consulta)

        # 3. Extração (Tentativa Determinística -> Fallback IA)
        self._log.debug("Iniciando extração de dados.")
        
        nota_dto = self.parser.parse(html_content)
        
        # Se for HTML colado, a chave_acesso pode ter vindo do parser
        if not chave_acesso and nota_dto:
            chave_acesso = nota_dto.chave_acesso

        # Validação de Idempotência para HTML colado
        if html_pasted and chave_acesso and await self.repo.nota_existe(chave_acesso):
            self._log.warning("Nota fiscal (do HTML colado) já cadastrada.")
            raise NotaJaCadastradaError(f"Nota {chave_acesso} já cadastrada.")

        if nota_dto:
            self._log.info(f"Dados extraídos via Parser Determinístico. Fornecedor: {nota_dto.fornecedor.razao_social}")
        else:
            self._log.info("Parser determinístico falhou ou incompleto. Iniciando processamento via IA.")
            texto_limpo = self._limpar_html(html_content)
            try:
                nota_dto = await self.ai.extrair_nota(texto_limpo)
                if chave_acesso: nota_dto.chave_acesso = chave_acesso
                self._log.info(f"Dados extraídos via IA. Fornecedor: {nota_dto.fornecedor.razao_social}")
            except Exception as exc:
                self._log.error(f"Falha crítica na extração via IA: {exc}", exc_info=True)
                raise ExtracaoDadosNotaError(f"Falha na extração por IA: {exc}") from exc

        # 4. Persistência Atômica
        chave_final = chave_acesso or nota_dto.chave_acesso
        self._log.debug(f"Persistindo dados da nota {chave_final}.")
        async with self.repo.db.begin():
            if await self.repo.nota_existe(chave_final):
                raise NotaJaCadastradaError(f"Nota {chave_final} já cadastrada.")
            nota_db = await self.repo.salvar_nota_completa(chave_final, nota_dto)

        self._log.info("Nota fiscal e itens importados com sucesso para o banco de dados.")

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
            raise RuntimeError("Cliente HTTP não iniciado. Use 'async with'.")
        
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            self._log.error(f"Erro de comunicação com SEFAZ GO: {exc}")
            raise SefazComunicacaoError(f"Falha ao consultar SEFAZ: {exc}")

    def _limpar_html(self, html: str) -> str:
        """Sanitização básica do HTML para reduzir tokens."""
        texto = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        texto = re.sub(r"<[^>]+>", " ", texto)
        texto = unescape(texto)
        return re.sub(r"\s+", " ", texto).strip()[:16000]
