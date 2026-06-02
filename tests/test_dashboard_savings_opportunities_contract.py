from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas.dashboard import (
    OpportunityScoreBreakdown,
    SavingOpportunitiesSummary,
    SavingOpportunity,
)


def _valid_score(**overrides):
    data = {
        "financial_impact_score": 80,
        "confidence_score": 75,
        "recurrence_score": 60,
        "total_score": 72,
    }
    data.update(overrides)
    return OpportunityScoreBreakdown(**data)


def _valid_opportunity(**overrides):
    data = {
        "id": "opp-price-gap-789",
        "type": "price_gap",
        "title": "Comprar leite pelo fornecedor mais barato",
        "description": "Produto recorrente com preço unitário acima do benchmark.",
        "product_name": "Leite Integral 1L",
        "ean": "7891000000001",
        "category": "Laticinios",
        "current_supplier": "Fornecedor Atual",
        "suggested_supplier": "Fornecedor Referencia",
        "reference_date": date(2026, 6, 1),
        "current_unit_price": Decimal("7.50"),
        "benchmark_unit_price": Decimal("6.20"),
        "estimated_savings": Decimal("130.00"),
        "estimated_savings_percent": Decimal("17.33"),
        "confidence": "high",
        "score": _valid_score(),
        "reasons": ["Preco atual acima do historico recente."],
        "warnings": ["amostra pequena"],
    }
    data.update(overrides)
    return SavingOpportunity(**data)


def test_financial_saving_opportunity_by_ean_is_valid():
    opportunity = _valid_opportunity()

    assert opportunity.type == "price_gap"
    assert opportunity.ean == "7891000000001"
    assert opportunity.estimated_savings == Decimal("130.00")
    assert opportunity.score.total_score == 72


def test_data_quality_opportunity_accepts_null_ean():
    opportunity = _valid_opportunity(
        id="opp-data-quality-missing-ean",
        type="data_quality",
        title="Produto sem EAN",
        description="Produto comprado recentemente nao possui EAN cadastrado.",
        product_name=None,
        ean=None,
        current_supplier=None,
        suggested_supplier=None,
        current_unit_price=None,
        benchmark_unit_price=None,
        estimated_savings=Decimal("0"),
        estimated_savings_percent=None,
        confidence="insufficient_data",
        warnings=["dados insuficientes", "produto sem EAN"],
    )

    assert opportunity.type == "data_quality"
    assert opportunity.ean is None
    assert "produto sem EAN" in opportunity.warnings


def test_saving_opportunity_json_does_not_include_sensitive_fields():
    serialized = _valid_opportunity().model_dump_json()

    for forbidden in (
        "cnpj",
        "cpf",
        "chave_acesso",
        "numero_nota",
        "sefaz",
        "qr_code",
        "payload",
    ):
        assert forbidden not in serialized.lower()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("estimated_savings", Decimal("-0.01")),
        ("current_unit_price", Decimal("-0.01")),
        ("benchmark_unit_price", Decimal("-0.01")),
    ],
)
def test_negative_money_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        _valid_opportunity(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("financial_impact_score", -1),
        ("confidence_score", 101),
        ("recurrence_score", -1),
        ("total_score", 101),
    ],
)
def test_score_outside_zero_to_one_hundred_is_rejected(field, value):
    with pytest.raises(ValidationError):
        _valid_score(**{field: value})


def test_summary_accepts_empty_opportunities_and_zero_total():
    summary = SavingOpportunitiesSummary(
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        total_estimated_savings=Decimal("0"),
        opportunity_count=0,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        insufficient_data_count=0,
        opportunities=[],
    )

    assert summary.opportunity_count == 0
    assert summary.total_estimated_savings == Decimal("0")
    assert summary.opportunities == []


def test_summary_rejects_period_end_before_period_start():
    with pytest.raises(ValidationError):
        SavingOpportunitiesSummary(
            period_start=date(2026, 6, 30),
            period_end=date(2026, 6, 1),
            total_estimated_savings=Decimal("0"),
            opportunity_count=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            insufficient_data_count=0,
            opportunities=[],
        )
