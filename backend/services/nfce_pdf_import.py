"""Import NFC-e GO detailed PDFs without external SEFAZ/Gemini calls."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.fiscal import validar_chave_acesso
from backend.models.compras import NotaFiscal
from backend.schemas.importacao import (
    FornecedorImportadoResponse,
    ImportacaoNotaResponse,
    ItemNotaFiscalImportadoResponse,
    NotaFiscalImportadaResponse,
)
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.extraction_quality import build_extraction_quality
from backend.services.importador_sefaz import (
    ImportacaoSemProdutosError,
    NotaJaCadastradaError,
)
from backend.services.product_categorization import categorizar_produto
from backend.services.repository import ProcurementRepository
from core.logger import get_logger


logger = get_logger("services.nfce_pdf_import")

NFCE_PDF_SOURCE = "nfce_pdf_detalhado"
NFCE_PDF_NO_PRODUCTS_MESSAGE = "Não foi possível extrair produtos deste PDF. A importação não foi concluída."
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


@dataclass(frozen=True)
class NfcePdfItem:
    numero_item: int
    descricao: str
    quantidade: Decimal
    unidade: str
    valor_total_item: Decimal
    categoria: str
    subcategoria: str | None
    produto_base: str
    origem_categorizacao: str
    confianca: Decimal


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
    itens: list[NfcePdfItem]
    item_total: Decimal


class NfcePdfImportError(Exception):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _mask_key(chave: str) -> str:
    digits = re.sub(r"\D", "", chave or "")
    if len(digits) < 8:
        return "<chave-redigida>"
    return f"{digits[:4]}...{digits[-4:]}"


def _mask_filename(filename: str) -> str:
    suffix = Path(filename or "arquivo.pdf").suffix.lower() or ".pdf"
    digest = hashlib.sha1((filename or "arquivo.pdf").encode("utf-8")).hexdigest()[:8]
    return f"pdf-{digest}{suffix}"


def br_decimal(value: str) -> Decimal:
    normalized = (value or "").strip().replace(".", "").replace(",", ".")
    if not normalized:
        return Decimal("0.00")
    return Decimal(normalized)


def decimal_to_centavos(value: Decimal) -> int:
    return int((value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fiscal_year(issue_date: date) -> int:
    return issue_date.year


def fiscal_month(issue_date: date) -> int:
    return issue_date.month


def fiscal_year_month(issue_date: date) -> str:
    return issue_date.strftime("%Y-%m")


def build_pdf_deduplication_identity(
    *,
    chave_acesso: str | None,
    data_emissao: date,
    modelo: str | None,
    serie: str,
    numero: str,
    cnpj_emitente: str,
    valor_total_nota: Decimal,
) -> str:
    access_key = re.sub(r"\D", "", chave_acesso or "")
    if len(access_key) == 44:
        return f"chave:{access_key}"
    return "|".join(
        [
            "fallback",
            data_emissao.isoformat(),
            modelo or "",
            serie,
            numero,
            re.sub(r"\D", "", cnpj_emitente or ""),
            str(valor_total_nota.quantize(Decimal("0.01"))),
        ]
    )


def is_nfce_detalhada_text(text: str) -> bool:
    normalized = _normalize_text(text)
    required = (
        "dados dos produtos e servicos",
        "chave de acesso",
        "valor total da nota fiscal",
    )
    return all(marker in normalized for marker in required) and (
        "qr-code" in normalized or "qr code" in normalized or "url nfc-e" in normalized
    )


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception as exc:  # pragma: no cover - depends on deployment packaging
        raise NfcePdfImportError(
            "Leitor de PDF textual indisponível no ambiente.",
            error_code="pdf_text_reader_unavailable",
        ) from exc

    try:
        return extract_text(io.BytesIO(pdf_bytes)) or ""
    except Exception as exc:
        raise NfcePdfImportError(
            "Não foi possível extrair texto do PDF informado.",
            error_code="pdf_text_extraction_failed",
        ) from exc


def parse_nfce_detalhada_text(text: str) -> NfcePdfParseResult:
    if not is_nfce_detalhada_text(text):
        raise NfcePdfImportError("PDF não parece ser uma NFC-e detalhada da SEFAZ.", error_code="not_detailed_nfce_pdf")

    chave = _extract_access_key(text)
    if not chave or not validar_chave_acesso(chave):
        raise NfcePdfImportError("Chave de acesso inválida ou ausente no PDF.", error_code="invalid_access_key")

    itens = _extract_items(text)
    if not itens:
        raise ImportacaoSemProdutosError(NFCE_PDF_NO_PRODUCTS_MESSAGE)

    valor_total_nota = _extract_money(text, r"Valor Total da Nota Fiscal\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_total_nota = valor_total_nota or _extract_money(text, r"Valor Total da NF-?e\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_total_produtos = _extract_money(text, r"Valor Total dos Produtos\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_total_descontos = _extract_money(text, r"Valor Total dos Descontos\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_total_frete = _extract_money(text, r"Valor Total do Frete\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_total_seguro = _extract_money(text, r"Valor Total do Seguro\s*[:\-]?\s*([0-9.]+,\d{2})")
    valor_outras_despesas = _extract_money(text, r"Outras Despesas(?:\s+Acess[oó]rias)?\s*[:\-]?\s*([0-9.]+,\d{2})")
    item_total = sum((item.valor_total_item for item in itens), Decimal("0.00")).quantize(Decimal("0.01"))

    modelo, serie, numero = _extract_nf_metadata(text)
    supplier = _extract_supplier_metadata(text)

    return NfcePdfParseResult(
        chave_acesso=chave,
        modelo=modelo,
        serie=serie,
        numero=numero,
        data_emissao=_extract_date(text),
        emitente=supplier["razao_social"],
        cnpj_emitente=supplier["cnpj"],
        valor_total_nota=valor_total_nota or valor_total_produtos or item_total,
        valor_total_produtos=valor_total_produtos,
        valor_total_descontos=valor_total_descontos,
        valor_total_frete=valor_total_frete,
        valor_total_seguro=valor_total_seguro,
        valor_outras_despesas=valor_outras_despesas,
        url_qrcode=_extract_optional(text, r"(https?://\S+)"),
        itens=itens,
        item_total=item_total,
    )


def _extract_access_key(text: str) -> str:
    chave_contextual = re.search(r"Chave de Acesso\s*[:\-]?\s*([\d\s]{44,80})", text, flags=re.I)
    if chave_contextual:
        digits = re.sub(r"\D", "", chave_contextual.group(1))
        if len(digits) >= 44:
            return digits[:44]
    match = re.search(r"\b(\d{44})\b", re.sub(r"\s+", " ", text))
    return match.group(1) if match else ""


def _extract_optional(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    return match.group(1).strip()


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _line_value_after_label(lines: list[str], label: str, *, max_distance: int = 12) -> str | None:
    normalized_label = _normalize_text(label)
    ignored_labels = {
        "cnpj",
        "cpf",
        "nome / razao social",
        "nome fantasia",
        "inscricao estadual",
        "endereco",
        "cep",
        "telefone",
        "pais",
        "bairro / distrito",
        "modelo",
        "serie",
        "numero",
        "data de emissao",
        "data saida/entrada",
        "valor total da nota fiscal",
    }
    for index, line in enumerate(lines):
        if _normalize_text(line) != normalized_label:
            continue
        for candidate in lines[index + 1 : index + 1 + max_distance]:
            normalized_candidate = _normalize_text(candidate)
            if normalized_candidate in ignored_labels:
                continue
            if re.fullmatch(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", candidate):
                continue
            if re.fullmatch(r"\d+", candidate):
                continue
            return candidate.strip()
    return None


def _extract_nf_metadata(text: str) -> tuple[str | None, str, str]:
    lines = _non_empty_lines(text)
    modelo = _extract_optional(text, r"Modelo\s*[:\-]?\s*(\d{2})")
    serie = _extract_optional(text, r"S[ée]rie\s*[:\-]?\s*(\d+)")
    numero = _extract_optional(text, r"N[úu]mero\s+NF-e\s*[:\-]?\s*(\d+)") or _extract_optional(text, r"N[úu]mero\s*[:\-]?\s*(\d+)")

    if not (modelo and serie and numero):
        labels = ["modelo", "serie", "numero"]
        label_indexes = [
            index
            for index, line in enumerate(lines)
            if _normalize_text(line) in labels
        ]
        numeric_values = [
            line
            for line in lines[label_indexes[-1] + 1 : label_indexes[-1] + 12]
            if re.fullmatch(r"\d+", line)
        ] if len(label_indexes) >= 3 else []
        if len(numeric_values) >= 3:
            modelo = modelo or numeric_values[0]
            serie = serie or numeric_values[1]
            numero = numero or numeric_values[2]

    return modelo, serie or "0", numero or ""


def _extract_supplier_metadata(text: str) -> dict[str, str]:
    lines = _non_empty_lines(text)
    cnpj = _extract_cnpj(text)
    razao_social = _extract_optional(text, r"Emitente\s*[:\-]?\s*(.+)")
    if not razao_social or _normalize_text(razao_social) in {"cnpj", "nome / razao social"}:
        razao_social = _line_value_after_label(lines, "Nome / Razão Social")

    if not razao_social or _normalize_text(razao_social) in {"cnpj", "nome / razao social"}:
        razao_social = "EMITENTE NAO IDENTIFICADO"

    return {"cnpj": cnpj, "razao_social": razao_social}


def _extract_money(text: str, pattern: str) -> Decimal | None:
    value = _extract_optional(text, pattern)
    return br_decimal(value) if value else None


def _extract_date(text: str) -> date:
    match = re.search(
        r"Data\s+(?:de\s+)?Emiss[aã]o\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.I,
    )
    if not match:
        raise NfcePdfImportError("Data de emissão ausente no PDF.", error_code="missing_issue_date")
    return datetime.strptime(match.group(1), "%d/%m/%Y").date()


def _extract_cnpj(text: str) -> str:
    match = re.search(r"CNPJ\s*[:\-]?\s*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", text, flags=re.I)
    if match:
        return re.sub(r"\D", "", match.group(1))

    lines = _non_empty_lines(text)
    for index, line in enumerate(lines):
        if _normalize_text(line) != "cnpj":
            continue
        for candidate in lines[index + 1 : index + 13]:
            if re.fullmatch(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", candidate):
                return re.sub(r"\D", "", candidate)

    raise NfcePdfImportError("CNPJ do emitente ausente no PDF.", error_code="missing_supplier_cnpj")


def _extract_items(text: str) -> list[NfcePdfItem]:
    lines = [line.strip() for line in text.splitlines()]
    columnar_items = _extract_items_columnar(lines)
    row_items = _extract_items_rowwise(lines)
    return columnar_items if len(columnar_items) > len(row_items) else row_items


def _match_rowwise_item(line: str) -> re.Match[str] | None:
    match = ROWWISE_ITEM_RE.match(line)
    if match and match.group(4).upper() in {"DE", "POR"}:
        return None
    return match


def _is_stop_marker(normalized_line: str) -> bool:
    return any(marker in normalized_line for marker in STOP_MARKERS)


def _is_rowwise_header_line(normalized_line: str) -> bool:
    if normalized_line.startswith(("item ", "n item", "n. item", "num.", "codigo")):
        return True
    keywords = {
        "descricao",
        "quantidade",
        "qtd.",
        "qtd",
        "unidade",
        "unid",
        "valor",
        "vlr",
        "total",
        "comercial",
        "valor(r$)",
    }
    if normalized_line in keywords:
        return True
    found_count = 0
    for kw in keywords:
        if kw in normalized_line:
            found_count += 1
    return found_count >= 2


def _is_rowwise_lookahead_ignored_line(normalized_line: str) -> bool:
    return (
        not normalized_line
        or _is_rowwise_header_line(normalized_line)
        or normalized_line.startswith("pagina ")
        or "dados dos produtos e servicos" in normalized_line
        or normalized_line == "informacoes adicionais"
        or normalized_line.startswith("informacoes complementares")
        or normalized_line.startswith("informacoes suplementares")
        or _is_stop_marker(normalized_line)
    )


def _is_rowwise_lookahead_terminal_line(normalized_line: str) -> bool:
    return any(marker in normalized_line for marker in ROWWISE_LOOKAHEAD_TERMINAL_MARKERS)


def _has_next_consecutive_rowwise_item(
    lines: list[str],
    start_index: int,
    item_number: int,
) -> bool:
    for raw_line in lines[start_index:]:
        line = raw_line.strip()
        normalized = _normalize_text(line)
        if _is_rowwise_lookahead_terminal_line(normalized):
            return False
        if _is_rowwise_lookahead_ignored_line(normalized):
            continue

        match = _match_rowwise_item(line)
        if match:
            return int(match.group(1)) == item_number + 1
        return False

    return False


def _is_single_final_item_before_terminal(lines: list[str], start_index: int) -> bool:
    for raw_line in lines[start_index:]:
        line = raw_line.strip()
        normalized = _normalize_text(line)
        if _is_rowwise_lookahead_terminal_line(normalized):
            return True
        if _is_rowwise_lookahead_ignored_line(normalized):
            continue
        return False

    return False


def _has_future_rowwise_item_continuation(
    lines: list[str],
    start_index: int,
    last_item_number: int,
) -> bool:
    saw_additional_info = False
    for index, raw_line in enumerate(lines[start_index:], start=start_index):
        line = raw_line.strip()
        normalized = _normalize_text(line)
        if _is_rowwise_lookahead_terminal_line(normalized):
            return False
        if normalized == "informacoes adicionais":
            saw_additional_info = True
        if _is_rowwise_lookahead_ignored_line(normalized):
            continue

        match = _match_rowwise_item(line)
        if match:
            numero_item = int(match.group(1))
            if numero_item != last_item_number + 1:
                return False
            if saw_additional_info and last_item_number > 0:
                return (
                    _has_next_consecutive_rowwise_item(lines, index + 1, numero_item)
                    or _is_single_final_item_before_terminal(lines, index + 1)
                )
            return True
        if last_item_number == 0:
            continue
        return False

    return False


def _match_columnar_description_item(line: str) -> re.Match[str] | None:
    if _match_rowwise_item(line):
        return None
    return re.match(r"^\s*(\d{1,4})\s+(.+?)\s*$", line)


def _has_future_columnar_item_continuation(
    lines: list[str],
    start_index: int,
    last_item_number: int,
) -> bool:
    expected_number = last_item_number + 1
    found_description = False

    for raw_line in lines[start_index:]:
        line = raw_line.strip()
        normalized = _normalize_text(line)
        if _is_rowwise_lookahead_terminal_line(normalized):
            return False
        if _is_rowwise_lookahead_ignored_line(normalized):
            continue

        if found_description and re.fullmatch(r"\d+,\d{1,4}", line):
            return True

        match = _match_columnar_description_item(line)
        if match:
            numero_item = int(match.group(1))
            if numero_item != expected_number:
                return False
            found_description = True
            expected_number += 1
            continue

        if last_item_number == 0:
            continue

        return False

    return False


def _match_rowwise_item_from_lines(lines: list[str], start_index: int) -> tuple[re.Match[str] | None, int]:
    combined_parts: list[str] = []
    for index in range(start_index, min(len(lines), start_index + 5)):
        line = lines[index].strip()
        normalized = _normalize_text(line)
        if index > start_index and (
            not line
            or _is_rowwise_lookahead_terminal_line(normalized)
            or _is_stop_marker(normalized)
            or _is_rowwise_header_line(normalized)
            or "dados dos produtos e servicos" in normalized
        ):
            break
        if index > start_index and re.match(r"^\s*\d{1,4}\s+", line):
            break

        combined_parts.append(line)
        match = _match_rowwise_item(" ".join(combined_parts))
        if match:
            return match, index

    return None, start_index


def _extract_items_rowwise(lines: list[str]) -> list[NfcePdfItem]:
    in_products = False
    items: list[NfcePdfItem] = []
    last_item_number = 0
    skip_until_index = -1

    for index, line in enumerate(lines):
        if index <= skip_until_index:
            continue
        normalized = _normalize_text(line)
        if "dados dos produtos e servicos" in normalized:
            in_products = True
            continue
        if not in_products or not line:
            continue
        if _is_rowwise_lookahead_terminal_line(normalized):
            break
        if _is_stop_marker(normalized):
            if _has_future_rowwise_item_continuation(lines, index + 1, last_item_number):
                continue
            break
        if normalized.startswith(ROWWISE_HEADER_PREFIXES):
            continue

        match, matched_until_index = _match_rowwise_item_from_lines(lines, index)
        if not match:
            continue
        skip_until_index = matched_until_index

        numero_item = int(match.group(1))
        descricao = re.sub(r"\s+", " ", match.group(2)).strip()
        quantidade = br_decimal(match.group(3))
        unidade = match.group(4).upper()
        valor_total = br_decimal(match.group(5)).quantize(Decimal("0.01"))
        categoria = categorizar_produto(descricao)
        items.append(
            NfcePdfItem(
                numero_item=numero_item,
                descricao=descricao,
                quantidade=quantidade,
                unidade=unidade,
                valor_total_item=valor_total,
                categoria=categoria.categoria,
                subcategoria=categoria.subcategoria,
                produto_base=categoria.produto_base,
                origem_categorizacao=categoria.origem_categorizacao,
                confianca=Decimal(str(categoria.confianca)),
            )
        )
        last_item_number = max(last_item_number, numero_item)

    return items


def _extract_items_columnar(lines: list[str]) -> list[NfcePdfItem]:
    in_products = False
    state = "desc"
    descriptions: list[tuple[int, str]] = []
    quantities: list[Decimal] = []
    units: list[str] = []
    values: list[Decimal] = []
    items: list[NfcePdfItem] = []
    last_item_number = 0

    def flush_group() -> None:
        nonlocal descriptions, quantities, units, values, last_item_number
        count = min(len(descriptions), len(quantities), len(units), len(values))
        for idx in range(count):
            numero_item, descricao = descriptions[idx]
            categoria = categorizar_produto(descricao)
            items.append(
                NfcePdfItem(
                    numero_item=numero_item,
                    descricao=descricao,
                    quantidade=quantities[idx],
                    unidade=units[idx],
                    valor_total_item=values[idx],
                    categoria=categoria.categoria,
                    subcategoria=categoria.subcategoria,
                    produto_base=categoria.produto_base,
                    origem_categorizacao=categoria.origem_categorizacao,
                    confianca=Decimal(str(categoria.confianca)),
                )
            )
            last_item_number = max(last_item_number, numero_item)
        descriptions = descriptions[count:]
        quantities = quantities[count:]
        units = units[count:]
        values = values[count:]

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        normalized = _normalize_text(line)
        if "dados dos produtos e servicos" in normalized:
            in_products = True
            state = "desc"
            continue
        if not in_products or not line:
            continue
        if _is_rowwise_lookahead_terminal_line(normalized):
            flush_group()
            break
        if _is_stop_marker(normalized):
            if descriptions and not quantities:
                state = "qty"
                continue
            flush_group()
            pending_last_item_number = max(
                [last_item_number, *(numero_item for numero_item, _ in descriptions)],
                default=last_item_number,
            )
            if _has_future_rowwise_item_continuation(lines, index + 1, pending_last_item_number):
                continue
            if _has_future_columnar_item_continuation(lines, index + 1, pending_last_item_number):
                state = "desc"
                continue
            break
        if normalized.startswith(ROWWISE_HEADER_PREFIXES):
            continue

        item_match = re.match(r"^\s*(\d{1,4})\s+(.+?)\s*$", line)
        if state == "value" and item_match and len(values) >= len(descriptions):
            flush_group()
            state = "desc"

        if normalized.startswith("qtd"):
            state = "qty"
            continue
        if normalized.startswith(("unid", "unidade")):
            state = "unit"
            continue
        if "valor" in normalized and "r$" in normalized:
            state = "value"
            continue

        if state == "desc":
            if descriptions and re.fullmatch(r"\d+,\d{1,4}", line):
                state = "qty"
                quantities.append(br_decimal(line))
                continue
            if item_match:
                descriptions.append((int(item_match.group(1)), re.sub(r"\s+", " ", item_match.group(2)).strip()))
            continue
        if state == "qty" and re.fullmatch(r"\d+,\d{1,4}", line):
            quantities.append(br_decimal(line))
            continue
        if state == "qty" and re.fullmatch(r"[A-Za-z]{1,8}", line) and len(quantities) >= len(descriptions):
            state = "unit"
            units.append(line.upper())
            continue
        if state == "unit" and re.fullmatch(r"[A-Za-z]{1,8}", line):
            units.append(line.upper())
            continue
        if state == "unit" and re.fullmatch(r"[0-9.]+,\d{2}", line) and len(units) >= len(descriptions):
            state = "value"
            values.append(br_decimal(line).quantize(Decimal("0.01")))
            continue
        if state == "value" and re.fullmatch(r"[0-9.]+,\d{2}", line):
            values.append(br_decimal(line).quantize(Decimal("0.01")))

    flush_group()
    deduped: dict[int, NfcePdfItem] = {}
    for item in items:
        deduped.setdefault(item.numero_item, item)
    return list(deduped.values())


def _sem_ean_id(descricao: str) -> str:
    texto = unicodedata.normalize("NFKD", descricao or "PRODUTO_SEM_EAN")
    texto = "".join(char for char in texto.upper() if not unicodedata.combining(char))
    texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip() or "PRODUTO_SEM_EAN"
    digest = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12].upper()
    return f"SEM_EAN_{digest}"


def _to_dto(parsed: NfcePdfParseResult) -> NotaFiscalDTO:
    itens = []
    for item in parsed.itens:
        valor_unitario = (
            item.valor_total_item / item.quantidade
            if item.quantidade > 0
            else Decimal("0.00")
        ).quantize(Decimal("0.0001"))
        itens.append(
            ItemNotaDTO(
                ean=_sem_ean_id(item.descricao),
                descricao=item.descricao,
                quantidade=item.quantidade,
                valor_unitario=valor_unitario,
                valor_total=item.valor_total_item,
                categoria=item.categoria,
                categoria_sugerida_origem=item.origem_categorizacao,
                categoria_sugerida_confidence=item.confianca,
                categoria_sugerida_modelo="deterministic-product-categorization-v1",
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


def _fiscal_totals_reconcile(parsed: NfcePdfParseResult, *, tolerance: Decimal = Decimal("0.01")) -> bool:
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


class NfcePdfImportService:
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
        text = extract_text_from_pdf_bytes(pdf_bytes)
        parsed = parse_nfce_detalhada_text(text)

        if await self.repo.nota_existe(parsed.chave_acesso):
            raise NotaJaCadastradaError("Nota fiscal ja cadastrada.")
        if not parsed.itens:
            raise ImportacaoSemProdutosError(NFCE_PDF_NO_PRODUCTS_MESSAGE)

        dto = _to_dto(parsed)
        quality_details: dict[str, Any] = {
            "source": NFCE_PDF_SOURCE,
            "modelo": parsed.modelo,
            "serie": parsed.serie,
            "data_emissao": parsed.data_emissao.isoformat(),
            "ano": fiscal_year(parsed.data_emissao),
            "mes": fiscal_month(parsed.data_emissao),
            "ano_mes": fiscal_year_month(parsed.data_emissao),
            "valor_total_produtos": str(parsed.valor_total_produtos) if parsed.valor_total_produtos is not None else None,
            "valor_total_descontos": str(parsed.valor_total_descontos) if parsed.valor_total_descontos is not None else None,
            "valor_total_frete": str(parsed.valor_total_frete) if parsed.valor_total_frete is not None else None,
            "valor_total_seguro": str(parsed.valor_total_seguro) if parsed.valor_total_seguro is not None else None,
            "valor_outras_despesas": str(parsed.valor_outras_despesas) if parsed.valor_outras_despesas is not None else None,
            "item_total": str(parsed.item_total),
            "item_total_centavos": decimal_to_centavos(parsed.item_total),
            "has_qrcode_url": parsed.url_qrcode is not None,
            "categorization_origin": "deterministica",
            "deduplication_identity_kind": "chave"
            if build_pdf_deduplication_identity(
                chave_acesso=parsed.chave_acesso,
                data_emissao=parsed.data_emissao,
                modelo=parsed.modelo,
                serie=parsed.serie,
                numero=parsed.numero,
                cnpj_emitente=parsed.cnpj_emitente,
                valor_total_nota=parsed.valor_total_nota,
            ).startswith("chave:")
            else "fallback",
        }
        extraction_quality = build_extraction_quality(
            dto,
            parser_source="deterministic",
            details=quality_details,
        )
        if _fiscal_totals_reconcile(parsed) and extraction_quality.total_mismatch:
            quality_details["pdf_fiscal_total_reconciled"] = True
            extraction_quality = replace(
                extraction_quality,
                total_mismatch=False,
                details=quality_details,
            )
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
            raise ImportacaoSemProdutosError(NFCE_PDF_NO_PRODUCTS_MESSAGE)

        self._log.info(
            "Importando NFC-e por PDF detalhado "
            f"(filename={_mask_filename(filename)}, item_count={len(parsed.itens)}, "
            f"total_centavos={decimal_to_centavos(parsed.item_total)}, "
            f"quality_status={extraction_quality.quality_status}, chave={_mask_key(parsed.chave_acesso)})."
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
            entidade_id=_mask_key(parsed.chave_acesso),
            detalhes=f"Importacao NFC-e PDF com {len(parsed.itens)} itens.",
            ip=ip_origem,
            department_id=department_id,
        )
        await self.repo.db.flush()

        stmt = select(NotaFiscal).where(NotaFiscal.id == nota_db.id).options(
            selectinload(NotaFiscal.fornecedor),
            selectinload(NotaFiscal.itens),
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
