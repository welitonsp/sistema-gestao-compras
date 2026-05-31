"""Import service for detailed NFC-e PDFs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from dataclasses import replace
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.compras import NotaFiscal
from backend.schemas.importacao import (
    FornecedorImportadoResponse,
    ImportacaoNotaResponse,
    ItemNotaFiscalImportadoResponse,
    NotaFiscalImportadaResponse,
)
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.extraction_quality import build_extraction_quality
from backend.services.importador_sefaz import ImportacaoSemProdutosError, NotaJaCadastradaError
from backend.services.parsers.pdf_parser import PDFTextExtractor
from backend.services.parsers.nfce_pdf_extractor import NfcePdfParser, NfcePdfParseResult
from backend.services.repository import ProcurementRepository
from core.logger import get_logger

logger = get_logger("services.nfce_import")

class NfcePdfImportError(Exception):
    def __init__(self, message: str, *, error_code: str = "pdf_import_error") -> None:
        super().__init__(message)
        self.error_code = error_code

class NfcePdfImportService:
    """Orchestrates the ingestion of detailed NFC-e PDFs."""
    
    def __init__(self, repo: ProcurementRepository) -> None:
        self.repo = repo
        self._log = logger

    async def importar_pdf_bytes(
        self,
        pdf_bytes: bytes,
        *,
        filename: str,
        usuario: str,
        ip_origem: str | None = None,
        department_id: str | None = None,
    ) -> ImportacaoNotaResponse:
        """Full flow: extract -> parse -> validate -> save."""
        
        # 1. Extraction & Parsing
        text = PDFTextExtractor.extract_text(pdf_bytes)
        parser = NfcePdfParser()
        try:
            parsed = parser.parse(text)
        except ValueError as e:
            raise NfcePdfImportError(str(e), error_code="invalid_pdf_content")

        # 2. Multi-tenant Idempotency Check
        if await self.repo.nota_existe(parsed.chave_acesso, department_id=department_id):
            raise NotaJaCadastradaError("Nota fiscal ja cadastrada.")

        # 3. Conversion to DTO
        dto = self._to_dto(parsed)
        
        # 4. Quality & Persistence
        details = {
            "filename": filename,
            "item_total": str(parsed.item_total),
            "data_emissao": parsed.data_emissao.isoformat(),
            "modelo": parsed.modelo,
            "serie": parsed.serie,
            "cnpj_emitente": parsed.cnpj_emitente,
        }
        
        extraction_quality = build_extraction_quality(
            dto,
            parser_source="deterministic_pdf",
            details=details
        )
        
        # Apply reconciliation logic for quality
        if parser.reconcile_totals(parsed) and extraction_quality.total_mismatch:
            extraction_quality = replace(extraction_quality, total_mismatch=False)

        # Rule: If only EANs are missing but totals match and other fields are ok, promote to 'ok'
        if (
            extraction_quality.quality_status == "warning"
            and extraction_quality.missing_ean_count == len(dto.itens)
            and not extraction_quality.total_mismatch
            and extraction_quality.empty_description_count == 0
            and extraction_quality.invalid_quantity_count == 0
            and extraction_quality.invalid_value_count == 0
        ):
            extraction_quality = replace(extraction_quality, quality_status="ok")

        if extraction_quality.extracted_item_count == 0:
            raise ImportacaoSemProdutosError("Não foi possível extrair produtos deste PDF.")

        self._log.info(
            "Importando NFC-e por PDF detalhado "
            f"(item_count={len(parsed.itens)}, "
            f"quality_status={extraction_quality.quality_status}, "
            f"chave={parsed.chave_acesso[:4]}...)."
        )

        nota_db = await self.repo.salvar_nota_completa(
            parsed.chave_acesso,
            dto,
            department_id=department_id,
            extraction_quality=extraction_quality,
        )
        
        await self.repo.registrar_auditoria(
            usuario=usuario,
            operacao="IMPORT_NFCE_PDF",
            entidade="NotaFiscal",
            entidade_id=parsed.chave_acesso,
            detalhes=f"Importação via PDF: {len(dto.itens)} itens.",
            ip=ip_origem,
            department_id=department_id
        )
        
        # 5. Result Loading
        await self.repo.db.flush()
        stmt = select(NotaFiscal).where(NotaFiscal.id == nota_db.id).options(
            selectinload(NotaFiscal.fornecedor),
            selectinload(NotaFiscal.itens)
        )
        res = await self.repo.db.execute(stmt)
        nota_db = res.scalar_one()

        return ImportacaoNotaResponse(
            mensagem="NFC-e importada por PDF com sucesso.",
            fornecedor=FornecedorImportadoResponse.model_validate(nota_db.fornecedor),
            nota_fiscal=NotaFiscalImportadaResponse.model_validate(nota_db),
            itens=[ItemNotaFiscalImportadoResponse.model_validate(item) for item in nota_db.itens],
            total_itens=len(nota_db.itens),
        )

    def _to_dto(self, parsed: NfcePdfParseResult) -> NotaFiscalDTO:
        itens = []
        for item in parsed.itens:
            valor_unitario = (
                item.valor_total_item / item.quantidade
                if item.quantidade > 0
                else Decimal("0.00")
            ).quantize(Decimal("0.0001"))
            
            itens.append(
                ItemNotaDTO(
                    ean=self._sem_ean_id(item.descricao),
                    descricao=item.descricao,
                    quantidade=item.quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=item.valor_total_item,
                )
            )
        return NotaFiscalDTO(
            chave_acesso=parsed.chave_acesso,
            numero_nota=parsed.numero,
            data_emissao=parsed.data_emissao,
            valor_total=parsed.valor_total_nota,
            fornecedor=FornecedorDTO(cnpj=parsed.cnpj_emitente, razao_social=parsed.emitente),
            itens=itens,
        )

    def _sem_ean_id(self, descricao: str) -> str:
        import hashlib
        import unicodedata
        import re
        texto = unicodedata.normalize("NFKD", descricao or "PRODUTO_SEM_EAN")
        texto = "".join(char for char in texto.upper() if not unicodedata.combining(char))
        texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip() or "PRODUTO_SEM_EAN"
        digest = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12].upper()
        return f"SEM_EAN_{digest}"
