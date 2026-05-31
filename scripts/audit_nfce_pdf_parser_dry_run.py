from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

os.environ["DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.nfce_pdf_import import (  # noqa: E402
    ImportacaoSemProdutosError,
    NfcePdfImportError,
)
from backend.services.parsers.pdf_parser import PDFTextExtractor
from backend.services.parsers.nfce_pdf_extractor import NfcePdfParser


DEFAULT_PDF_DIR = Path("NOVAS_NOTAS")
TOLERANCE = Decimal("0.01")
STATUSES = ("OK", "DUPLICADA", "TOTAL_DIVERGENTE", "NAO_NFCE_DETALHADA", "SEM_TEXTO", "FALHA_PARSE")


def mask_access_key(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 8:
        return "-"
    return f"{digits[:4]}...{digits[-4:]}"


def sanitize_text(value: str | None, *, max_length: int = 60) -> str:
    text = value or "-"
    text = re.sub(r"https?://\S+", "<url-redigida>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{44}\b", "<chave-redigida>", text)
    text = re.sub(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", "<cnpj-redigido>", text)
    text = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "<cpf-redigido>", text)
    text = re.sub(r"\b\d{11,44}\b", "<numero-redigido>", text)
    return re.sub(r"\s+", " ", text).strip()[:max_length]


def money(value: Decimal | None) -> str:
    if value is None:
        return "-"
    return str(value.quantize(Decimal("0.01")))


def empty_row(path: Path, status: str = "FALHA_PARSE", error: str = "") -> dict[str, str]:
    return {
        "arquivo": path.name,
        "numero": "-",
        "chave": "-",
        "data": "-",
        "itens": "-",
        "total_produtos": "-",
        "item_total": "-",
        "total_nota": "-",
        "status": status,
        "motivo": sanitize_text(error),
    }


def classify_parse_error(exc: Exception) -> str:
    if isinstance(exc, NfcePdfImportError) and exc.error_code == "not_detailed_nfce_pdf":
        return "NAO_NFCE_DETALHADA"
    if isinstance(exc, ImportacaoSemProdutosError):
        return "FALHA_PARSE"
    return "FALHA_PARSE"


def audit_pdf(path: Path, seen_keys: set[str]) -> dict[str, str]:
    try:
        text = PDFTextExtractor.extract_text(path.read_bytes())
    except Exception as exc:
        return empty_row(path, error=f"{type(exc).__name__}: {exc}")

    if not text.strip():
        return empty_row(path, status="SEM_TEXTO", error="PDF sem texto extraivel.")

    try:
        parser = NfcePdfParser()
        parsed = parser.parse(text)
    except (NfcePdfImportError, ImportacaoSemProdutosError, ValueError) as exc:
        return empty_row(path, status=classify_parse_error(exc), error=str(exc))
    except Exception as exc:
        return empty_row(path, error=f"{type(exc).__name__}: {exc}")

    chave = re.sub(r"\D", "", parsed.chave_acesso or "")
    row = {
        "arquivo": path.name,
        "numero": sanitize_text(parsed.numero or "-", max_length=24),
        "chave": mask_access_key(chave),
        "data": parsed.data_emissao.isoformat(),
        "itens": str(len(parsed.itens)),
        "total_produtos": money(parsed.valor_total_produtos),
        "item_total": money(parsed.item_total),
        "total_nota": money(parsed.valor_total_nota),
        "status": "OK",
        "motivo": "",
    }

    if chave and chave in seen_keys:
        row["status"] = "DUPLICADA"
        row["motivo"] = "Chave repetida no lote."
    else:
        if chave:
            seen_keys.add(chave)
        if parsed.valor_total_produtos is not None and abs(parsed.item_total - parsed.valor_total_produtos) > TOLERANCE:
            row["status"] = "TOTAL_DIVERGENTE"
            row["motivo"] = "Soma dos itens diverge do total de produtos."

    return row


def format_table(rows: list[dict[str, str]]) -> str:
    columns = [
        "arquivo",
        "numero",
        "chave",
        "data",
        "itens",
        "total_produtos",
        "item_total",
        "total_nota",
        "status",
        "motivo",
    ]
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(row[column]))

    lines = []
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        lines.append(" | ".join(row[column].ljust(widths[column]) for column in columns))
    return "\n".join(lines)


def build_report(rows: list[dict[str, str]], pdf_dir: Path) -> str:
    counts = Counter(row["status"] for row in rows)
    lines = [
        f"Dry-run parser NFC-e PDF: {pdf_dir} ({len(rows)} arquivo(s))",
        "Sem importacao, sem escrita em banco, sem OCR/SEFAZ/IA.",
        "",
        format_table(rows),
        "",
        "Resumo:",
    ]
    lines.extend(f"- {status}: {counts.get(status, 0)}" for status in STATUSES)
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita PDFs NFC-e locais usando apenas o parser deterministico, sem importar dados.",
    )
    parser.add_argument(
        "pdf_dir",
        nargs="?",
        default=str(DEFAULT_PDF_DIR),
        help="Diretorio com PDFs para auditar. Padrao: NOVAS_NOTAS",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    seen_keys: set[str] = set()
    rows = [audit_pdf(path, seen_keys) for path in pdfs]

    print(build_report(rows, pdf_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
