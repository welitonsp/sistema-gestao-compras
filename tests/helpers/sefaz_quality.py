from __future__ import annotations

from backend.services.extraction_quality import (
    ExtractionQuality,
    ParserSource,
    QualityStatus,
    build_extraction_quality as _build_extraction_quality,
)


def build_extraction_quality(dto, expected: dict, parser_source: ParserSource) -> ExtractionQuality:
    return _build_extraction_quality(
        dto,
        parser_source=parser_source,
        expected_item_count=int(expected["expected_item_count"]),
        total_tolerance=expected.get("total_tolerance", "0.01"),
    )
