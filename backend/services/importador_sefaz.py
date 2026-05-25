"""Orquestrador de importação de notas fiscais SEFAZ GO."""

from __future__ import annotations

import re
import asyncio
from html import unescape
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.compras import NotaFiscal
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

        if identificador.startswith("<html") or "<html>" in identificador.lower() or "<body" in identificador.lower():
            # Caso 2: Usuário colou o HTML bruto
            html_pasted = identificador
            self._log.info("Processando importação via HTML colado.")
            operacao_tipo = "IMPORT_HTML_PASTE"
        else:
            operacao_tipo = "IMPORT_SEFAZ_GO"
            if identificador.startswith("http"):
                url_consulta = identificador
                match = re.search(r"p=([0-9]{44})", identificador)
                chave_acesso = match.group(1) if match else ""
            else:
                chave_acesso = re.sub(r"\D", "", identificador)
                url_consulta = self.URL_BASE_CONSULTA.format(chave=chave_acesso)

        # 2. Fetch/Preparação e Validação de Idempotência
        categorias_contexto = await self.repo.obter_categorias_unicas()
        
        if chave_acesso:
            self._log = ContextAdapter(logger, {"chave_acesso": chave_acesso})
            if await self.repo.nota_existe(chave_acesso):
                raise NotaJaCadastradaError(f"Nota {chave_acesso} já cadastrada.")
            
            if not html_pasted:
                html_content = await self._fetch_url(url_consulta)
            else:
                html_content = html_pasted
        else:
            html_content = html_pasted

        # 3. Extração (Parser Determinístico -> Fallback IA)
        nota_dto = self.parser.parse(html_content)
        
        if not nota_dto:
            texto_limpo = self._limpar_html(html_content)
            nota_dto = await self.ai.extrair_nota(texto_limpo, categorias_contexto=categorias_contexto)
            if chave_acesso: nota_dto.chave_acesso = chave_acesso
        else:
            # Enriquecimento: O parser determinístico não categoriza, chamamos IA para os itens
            # Isso garante que mesmo notas parseadas via CSS tenham categorias inteligentes
            nota_dto.itens = await self.ai.classificar_itens_lote(nota_dto.itens, categorias_contexto)

        chave_final = chave_acesso or nota_dto.chave_acesso

        # 4. Persistência Atômica com Auditoria
        # Removemos o begin() explícito daqui, pois a transação deve ser gerenciada
        # preferencialmente no nível do Caller (API ou script de teste) 
        # ou usamos a sessão injetada.
        
        # Re-valida existência
        if await self.repo.nota_existe(chave_final):
            raise NotaJaCadastradaError(f"Nota {chave_final} já cadastrada.")
        
        nota_db = await self.repo.salvar_nota_completa(chave_final, nota_dto, department_id=department_id)
        
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

        self._log.info(f"Nota {chave_final} importada e auditada com sucesso.")

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
        
        max_retries = 3
        backoff_factor = 2.0
        
        for attempt in range(max_retries):
            try:
                resp = await self._client.get(url)
                resp.raise_for_status()
                return resp.text
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                if attempt == max_retries - 1:
                    self._log.error(f"Falha definitiva após {max_retries} tentativas: {exc}")
                    raise SefazComunicacaoError(f"Falha ao consultar SEFAZ (Tentativas esgotadas): {exc}")
                
                wait_time = backoff_factor ** attempt
                self._log.warning(f"Erro na tentativa {attempt + 1}. Retentando em {wait_time}s... Erro: {exc}")
                await asyncio.sleep(wait_time)
        
        return "" # Unreachable

    def _limpar_html(self, html: str) -> str:
        """Sanitização equilibrada do HTML para reduzir tokens mantendo contexto."""
        # Remove scripts e estilos
        texto = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # Mantém algumas tags de estrutura ou apenas remove tags e colapsa espaços
        texto = re.sub(r"<[^>]+>", " ", texto)
        texto = unescape(texto)
        # Limita a 20.000 caracteres para dar mais margem à IA
        return re.sub(r"\s+", " ", texto).strip()[:20000]
