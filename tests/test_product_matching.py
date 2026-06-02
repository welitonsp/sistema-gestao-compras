from __future__ import annotations

import pytest

from backend.services.product_matching import (
    ProductMatchInput,
    calculate_product_similarity,
    generate_product_match_groups,
)
from backend.services.product_normalization import strong_normalize_product_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ARROZ TIO JOAO TIPO 1 5 KG", "arroz tio joao tipo 1 5 kg"),
        ("Arroz Tio João Tp1 5kg", "arroz tio joao tipo 1 5 kg"),
        ("  LEITE--UHT, INTEGRAL 1 LT  ", "leite uht integral 1 l"),
        ("LEITE UHT INTEGRAL 1L", "leite uht integral 1 l"),
        ("BISCOITO CX c/10 UND", "biscoito cx com 10 un"),
        ("BISCOITO caixa c 10 unidades", "biscoito cx com 10 un"),
        ("CAFE pct 500 gr", "cafe pct 500 g"),
        ("CAFE pacote 500g", "cafe pct 500 g"),
        ("AGUA MINERAL 500ml", "agua mineral 500 ml"),
        ("FARINHA K G", "farinha kg"),
        ("", ""),
        (None, ""),
    ],
)
def test_strong_normalize_product_name(raw, expected):
    assert strong_normalize_product_name(raw) == expected


@pytest.mark.parametrize(
    ("name_a", "name_b"),
    [
        ("PRODUTO A 1KG", "PRODUTO A - 1 KG"),
        ("ARROZ TIO JOAO 5KG", "ARROZ TIO JOÃO 5 KG"),
        ("LEITE UHT INTEGRAL 1L", "leite uht integral 1 lt"),
        ("Arroz Tio Joao Tp1 5kg", "ARROZ TIO JOAO TIPO 1 5 KG"),
    ],
)
def test_calculate_product_similarity_positive(name_a, name_b):
    assert calculate_product_similarity(name_a, name_b) > 0.95


@pytest.mark.parametrize(
    ("name_a", "name_b"),
    [
        ("DOCE DE LEITE", "DOCE DE COCO"),
        ("LEITE", "ARROZ"),
        ("A", "A 1KG"),
        ("", "PRODUTO A"),
        (None, "PRODUTO A"),
    ],
)
def test_calculate_product_similarity_negative(name_a, name_b):
    assert calculate_product_similarity(name_a, name_b) < 0.90


def test_generate_product_match_groups_respeita_departamento_e_categoria():
    products = [
        ProductMatchInput(
            ean="1001",
            name="ARROZ TIO JOAO TIPO 1 5KG",
            category="MERCEARIA",
            department_id="dept-a",
        ),
        ProductMatchInput(
            ean="1002",
            name="ARROZ TIO JOAO TP1 5 KG",
            category="MERCEARIA",
            department_id="dept-a",
        ),
        ProductMatchInput(
            ean="1003",
            name="ARROZ TIO JOAO TIPO 1 5KG",
            category="MERCEARIA",
            department_id="dept-b",
        ),
        ProductMatchInput(
            ean="1004",
            name="ARROZ TIO JOAO TP1 5 KG",
            category="BEBIDAS",
            department_id="dept-a",
        ),
    ]

    groups, total_groups, threshold, limit = generate_product_match_groups(
        products,
        threshold=0.90,
        limit=10,
    )

    assert threshold == 0.90
    assert limit == 10
    assert total_groups == 1
    assert len(groups) == 1
    assert groups[0].primary.ean == "1001"
    assert [match.ean for match in groups[0].matches] == ["1002"]


def test_generate_product_match_groups_clamps_limit_e_threshold():
    products = [
        ProductMatchInput(ean="1001", name="PRODUTO A 1KG"),
        ProductMatchInput(ean="1002", name="PRODUTO A 1 KG"),
    ]

    groups, total_groups, threshold, limit = generate_product_match_groups(
        products,
        threshold=0.1,
        limit=500,
        include_reasons=False,
    )

    assert len(groups) == 1
    assert total_groups == 1
    assert threshold == 0.80
    assert limit == 100
    assert groups[0].matches[0].reason is None
