from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal

from backend.schemas.internal import NotaFiscalDTO


QualityStatus = Literal["ok", "warning", "failed"]
ParserSource = Literal["deterministic", "ai_fallback"]


@dataclass(frozen=True)
class ExtractionQuality:
    item_count: int
    extracted_item_count: int
    missing_ean_count: int
    empty_description_count: int
    invalid_quantity_count: int
    invalid_value_count: int
    total_itens: Decimal
    total_nota: Decimal
    total_mismatch: bool
    parser_source: ParserSource
    quality_status: QualityStatus

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json_dict(self) -> dict:
        data = self.to_dict()
        data["total_itens"] = str(self.total_itens)
        data["total_nota"] = str(self.total_nota)
        return data


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def build_extraction_quality(
    dto: NotaFiscalDTO,
    parser_source: ParserSource,
    expected_item_count: int | None = None,
    total_tolerance: Decimal | str = Decimal("0.01"),
) -> ExtractionQuality:
    total_itens = sum((item.valor_total for item in dto.itens), Decimal("0"))
    total_nota = dto.valor_total
    tolerance = _to_decimal(total_tolerance)
    total_mismatch = abs(total_itens - total_nota) > tolerance

    extracted_item_count = len(dto.itens)
    item_count = expected_item_count if expected_item_count is not None else extracted_item_count
    missing_ean_count = sum(
        1 for item in dto.itens if not item.codigo_produto or item.codigo_produto.startswith("SEM_EAN_")
    )
    empty_description_count = sum(1 for item in dto.itens if not item.descricao.strip())
    invalid_quantity_count = sum(1 for item in dto.itens if item.quantidade <= 0)
    invalid_value_count = sum(1 for item in dto.itens if item.valor_unitario < 0 or item.valor_total < 0)

    if (
        extracted_item_count == 0
        or extracted_item_count != item_count
        or empty_description_count
        or invalid_quantity_count
        or invalid_value_count
    ):
        quality_status: QualityStatus = "failed"
    elif total_mismatch or missing_ean_count:
        quality_status = "warning"
    else:
        quality_status = "ok"

    return ExtractionQuality(
        item_count=item_count,
        extracted_item_count=extracted_item_count,
        missing_ean_count=missing_ean_count,
        empty_description_count=empty_description_count,
        invalid_quantity_count=invalid_quantity_count,
        invalid_value_count=invalid_value_count,
        total_itens=total_itens.quantize(Decimal("0.01")),
        total_nota=total_nota.quantize(Decimal("0.01")),
        total_mismatch=total_mismatch,
        parser_source=parser_source,
        quality_status=quality_status,
    )
