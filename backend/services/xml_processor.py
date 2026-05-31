"""Service for processing XML procurement documents (NFe, NFCe, CFe)."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

from backend.services.repository import ProcurementRepository
from core.logger import get_logger, ContextAdapter
from backend.schemas.internal import ItemNotaDTO, NotaFiscalDTO, FornecedorDTO

logger = get_logger("services.xml_processor")

class XMLProcessorService:
    """Service to extract and process data from XML fiscal documents."""

    INVALID_GTIN = {"", "SEM GTIN", "SEMGTIN", "0", "0000000000000"}

    def __init__(self, repo: ProcurementRepository):
        self.repo = repo
        self._log = logger

    async def processar_arquivo(self, caminho_xml: Path, department_id: str | None = None) -> bool:
        """Process a single XML file and persist its data."""
        self._log = ContextAdapter(logger, {"arquivo": caminho_xml.name})
        self._log.info(f"Iniciando processamento de XML: {caminho_xml.name}")

        try:
            content = caminho_xml.read_text(encoding="utf-8-sig")
            nota_dto = self.parse_xml_to_dto(content)

            async with self.repo.db.begin():
                if await self.repo.nota_existe(nota_dto.chave_acesso, department_id=department_id):
                    self._log.warning(f"Nota {nota_dto.chave_acesso} já processada para este departamento.")
                    return True
                
                await self.repo.salvar_nota_completa(nota_dto.chave_acesso, nota_dto, department_id=department_id)
            
            self._log.info(f"XML processado com sucesso. Chave: {nota_dto.chave_acesso}")
            return True

        except Exception as e:
            self._log.error(f"Erro ao processar XML {caminho_xml.name}: {e}", exc_info=True)
            return False

    def parse_xml_to_dto(self, xml_content: str) -> NotaFiscalDTO:
        """Parses XML content into a NotaFiscalDTO."""
        try:
            root = ET.fromstring(xml_content.lstrip("\ufeff").strip())
            self._remover_namespaces(root)
        except ET.ParseError as e:
            raise ValueError(f"XML inválido: {e}")

        chave = self._extrair_chave(root)
        if not chave:
            raise ValueError("Chave de acesso não encontrada no XML.")

        data_emissao = self._detectar_data_compra(root)
        mercado_nome = self._detectar_mercado(root)
        # CNPJ e Número da Nota
        cnpj = root.findtext(".//emit/CNPJ") or "00.000.000/0000-00"
        numero_nota = root.findtext(".//ide/nNF") or root.findtext(".//ide/nCFe") or "0"

        itens = []
        for det in root.findall(".//det"):
            prod = det.find("prod")
            if prod is None: continue

            nome = (prod.findtext("xProd") or "").strip()
            codigo = (prod.findtext("cProd") or "").strip()
            ean = (prod.findtext("cEAN") or "").strip()

            if ean.upper() in self.INVALID_GTIN:
                ean = (prod.findtext("cEANTrib") or "").strip()
            if ean.upper() in self.INVALID_GTIN:
                # Fallback EAN determinístico
                digest = hashlib.sha1(f"{codigo}|{nome}".encode("utf-8")).hexdigest()[:12]
                ean = f"XML_{digest.upper()}"

            qtd = self._to_decimal(prod.findtext("qCom"), "1")
            vuni = self._to_decimal(prod.findtext("vUnCom"), "0")
            vtot = self._to_decimal(prod.findtext("vProd"), "0")
            
            if vtot == 0 and qtd > 0 and vuni > 0:
                vtot = qtd * vuni

            itens.append(ItemNotaDTO(
                ean=ean,
                descricao=nome,
                quantidade=qtd,
                valor_unitario=vuni,
                valor_total=vtot
            ))

        return NotaFiscalDTO(
            chave_acesso=chave,
            numero_nota=numero_nota,
            data_emissao=data_emissao.date() if isinstance(data_emissao, datetime) else data_emissao,
            fornecedor=FornecedorDTO(razao_social=mercado_nome, cnpj=cnpj),
            itens=itens,
            valor_total=sum(i.valor_total for i in itens)
        )

    def _remover_namespaces(self, root: ET.Element):
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

    def _extrair_chave(self, root: ET.Element) -> Optional[str]:
        for tag in ("infNFe", "infCFe"):
            info = root.find(f".//{tag}")
            if info is not None:
                id_attr = info.get("Id") or ""
                if len(id_attr) >= 44:
                    return id_attr[-44:]
        
        for caminho in (".//chNFe", ".//chave"):
            chave = (root.findtext(caminho) or "").strip()
            if len(chave) == 44:
                return chave
        return None

    def _detectar_data_compra(self, root: ET.Element) -> datetime:
        candidatos = [
            (root.findtext(".//ide/dhEmi") or "").strip(),
            (root.findtext(".//ide/dEmi") or "").strip(),
        ]
        for valor in candidatos:
            if not valor: continue
            try:
                # ISO Format 2024-03-15T10:00:00-03:00 or 2024-03-15
                return datetime.fromisoformat(valor.split("+")[0].split("-")[0] if "T" not in valor and len(valor) > 10 else valor.split("+")[0])
            except:
                for fmt in ("%Y%m%d", "%Y-%m-%d"):
                    try: return datetime.strptime(valor[:10], fmt)
                    except: continue
        return datetime.now()

    def _detectar_mercado(self, root: ET.Element) -> str:
        return (root.findtext(".//emit/xFant") or root.findtext(".//emit/xNome") or "MERCADO DESCONHECIDO").strip()

    def _to_decimal(self, valor: Optional[str], default: str) -> Decimal:
        try: return Decimal((valor or default).strip().replace(",", "."))
        except: return Decimal(default)
