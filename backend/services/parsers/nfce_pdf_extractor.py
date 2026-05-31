"""Regex-based extractor for detailed NFC-e PDFs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any

from backend.core.fiscal import validar_chave_acesso

STOP_MARKERS = (
    "totais",
    "icms",
    "dados do transporte",
    "formas de pagamento",
)
ROWWISE_ITEM_RE = re.compile(
    r"^\s*(\d{1,4})\s+(.+)\s+(\d+,\d{1,4})\s+([A-Za-z]{1,8})\s+([0-9.]+,\d{2})\s*$"
)
ROWWISE_HEADER_PREFIXES = ("item ", "n item", "descricao", "codigo")
ROWWISE_LOOKAHEAD_TERMINAL_MARKERS = (
    "qr-code",
    "qr code",
    "url nfc-e",
    "chave de acesso",
    "protocolo de autorizacao",
)

def _mask_key(chave: str) -> str:
    digits = re.sub(r"\D", "", chave or "")
    if len(digits) < 8:
        return "<chave-redigida>"
    return f"{digits[:4]}...{digits[-4:]}"

def br_decimal(value: str) -> Decimal:
    normalized = (value or "").strip().replace(".", "").replace(",", ".")
    if not normalized:
        return Decimal("0.00")
    return Decimal(normalized)

def decimal_to_centavos(value: Decimal) -> int:
    return int((value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def fiscal_year_month(issue_date: date) -> str:
    return issue_date.strftime("%Y-%m")

@dataclass(frozen=True)
class RawPdfItem:
    numero_item: int
    descricao: str
    quantidade: Decimal
    unidade: str
    valor_total_item: Decimal

@dataclass(frozen=True)
class NfcePdfParseResult:
    chave_acesso: str
    modelo: str | None
    serie: str
    numero: str
    data_emissao: date
    emitente: str
    cnpj_emitente: str
    valor_total_nota: Decimal
    valor_total_produtos: Decimal | None
    valor_total_descontos: Decimal | None
    valor_total_frete: Decimal | None
    valor_total_seguro: Decimal | None
    valor_outras_despesas: Decimal | None
    url_qrcode: str | None
    itens: List[RawPdfItem]
    item_total: Decimal

class NfcePdfParser:
    """Deterministic parser for detailed NFC-e text layouts."""

    def parse(self, text: str) -> NfcePdfParseResult:
        if not self._is_nfce_detalhada_text(text):
             raise ValueError("PDF text does not look like a detailed SEFAZ NFC-e.")

        chave = self._extract_access_key(text)
        if not chave or not validar_chave_acesso(chave):
            raise ValueError("Invalid or missing access key in PDF.")

        itens = self._extract_items(text)
        if not itens:
            raise ValueError("No products found in PDF.")

        totals = self._extract_all_totals(text)
        valor_total_nota = totals.get("valor_total_nota")
        valor_total_produtos = totals.get("valor_total_produtos")
        item_total = sum((item.valor_total_item for item in itens), Decimal("0.00")).quantize(Decimal("0.01"))

        modelo, serie, numero = self._extract_nf_metadata(text)
        supplier = self._extract_supplier_metadata(text)

        return NfcePdfParseResult(
            chave_acesso=chave,
            modelo=modelo,
            serie=serie,
            numero=numero,
            data_emissao=self._extract_date(text),
            emitente=supplier["razao_social"],
            cnpj_emitente=supplier["cnpj"],
            valor_total_nota=valor_total_nota or valor_total_produtos or item_total,
            valor_total_produtos=valor_total_produtos,
            valor_total_descontos=totals.get("valor_total_descontos"),
            valor_total_frete=totals.get("valor_total_frete"),
            valor_total_seguro=totals.get("valor_total_seguro"),
            valor_outras_despesas=totals.get("valor_outras_despesas"),
            url_qrcode=self._extract_optional(text, r"(https?://\S+)"),
            itens=itens,
            item_total=item_total,
        )

    def reconcile_totals(self, parsed: NfcePdfParseResult, tolerance: Decimal = Decimal("0.01")) -> bool:
        if parsed.valor_total_produtos is None:
            return False

        desconto = parsed.valor_total_descontos or Decimal("0.00")
        frete = parsed.valor_total_frete or Decimal("0.00")
        seguro = parsed.valor_total_seguro or Decimal("0.00")
        outras = parsed.valor_outras_despesas or Decimal("0.00")
        calculated_note_total = (parsed.valor_total_produtos - desconto + frete + seguro + outras).quantize(Decimal("0.01"))

        return (
            abs(parsed.item_total - parsed.valor_total_produtos) <= tolerance
            and abs(calculated_note_total - parsed.valor_total_nota) <= tolerance
        )

    def build_deduplication_identity(self, parsed: NfcePdfParseResult) -> str:
        access_key = re.sub(r"\D", "", parsed.chave_acesso or "")
        if len(access_key) == 44:
            return f"chave:{access_key}"
        return "|".join(
            [
                "fallback",
                parsed.data_emissao.isoformat(),
                parsed.modelo or "",
                parsed.serie,
                parsed.numero,
                re.sub(r"\D", "", parsed.cnpj_emitente or ""),
                str(parsed.valor_total_nota.quantize(Decimal("0.01"))),
            ]
        )

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", normalized).strip().lower()

    def _is_nfce_detalhada_text(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        required = ("dados dos produtos e servicos", "chave de acesso", "valor total da nota fiscal")
        return all(marker in normalized for marker in required)

    def _extract_access_key(self, text: str) -> str:
        match = re.search(r"\b(\d{44})\b", re.sub(r"\s+", " ", text))
        return match.group(1) if match else ""

    def _extract_date(self, text: str) -> date:
        match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if not match: raise ValueError("Issue date missing.")
        return datetime.strptime(match.group(1), "%d/%m/%Y").date()

    def _extract_cnpj(self, text: str) -> str:
        match = re.search(r"CNPJ\s*[:\-]?\s*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", text, flags=re.I)
        if match: return re.sub(r"\D", "", match.group(1))
        raise ValueError("Supplier CNPJ missing.")

    def _extract_all_totals(self, text: str) -> Dict[str, Decimal | None]:
        labels = {
            "valor_total_nota": [r"Valor Total da Nota Fiscal", r"Valor Total da NF-?e"],
            "valor_total_produtos": [r"Valor Total dos Produtos"],
            "valor_total_descontos": [r"Valor Total dos Descontos"],
            "valor_total_frete": [r"Valor(?: Total)? do Frete"],
            "valor_total_seguro": [r"Valor(?: Total)? do Seguro"],
            "valor_outras_despesas": [r"Outras Despesas(?:\s+Acess[oó]rias)?", r"Valor Total Outras Despesas"],
        }
        results: Dict[str, Decimal | None] = {}
        for key, patterns in labels.items():
            results[key] = None
            for pattern in patterns:
                val = self._extract_money(text, pattern + r"\s*[:\-]?\s*([0-9.]+,\d{2})")
                if val is not None:
                    results[key] = val
                    break
        return results

    def _extract_money(self, text: str, pattern: str) -> Decimal | None:
        match = re.search(pattern, text, flags=re.I)
        if not match: return None
        return Decimal(match.group(1).replace(".", "").replace(",", "."))

    def _extract_optional(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.I)
        return match.group(1).strip() if match else None

    def _extract_nf_metadata(self, text: str) -> tuple[str | None, str, str]:
        modelo = self._extract_optional(text, r"Modelo\s*[:\-]?\s*(\d{2})")
        serie = self._extract_optional(text, r"S[ée]rie\s*[:\-]?\s*(\d+)")
        numero = self._extract_optional(text, r"N[úu]mero\s*[:\-]?\s*(\d+)")
        return modelo, serie or "0", numero or ""

    def _extract_supplier_metadata(self, text: str) -> Dict[str, str]:
        return {"cnpj": self._extract_cnpj(text), "razao_social": self._extract_optional(text, r"Emitente\s*[:\-]?\s*(.+)") or "EMITENTE DESCONHECIDO"}

    def _extract_items(self, text: str) -> List[RawPdfItem]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        items = []
        in_products = False
        for line in lines:
            if "dados dos produtos e servicos" in self._normalize_text(line):
                in_products = True
                continue
            if not in_products: continue
            if any(m in self._normalize_text(line) for m in STOP_MARKERS): break
            
            match = ROWWISE_ITEM_RE.match(line)
            if match:
                items.append(RawPdfItem(
                    numero_item=int(match.group(1)),
                    descricao=match.group(2).strip(),
                    quantidade=Decimal(match.group(3).replace(",", ".")),
                    unidade=match.group(4).upper(),
                    valor_total_item=Decimal(match.group(5).replace(".", "").replace(",", "."))
                ))
        return items
