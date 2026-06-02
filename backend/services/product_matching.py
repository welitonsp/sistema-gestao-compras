"""Pure product similarity and canonization candidate helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from rapidfuzz import fuzz

from backend.services.product_normalization import strong_normalize_product_name


DEFAULT_CANONIZATION_THRESHOLD = 0.90
MIN_CANONIZATION_THRESHOLD = 0.80
MAX_CANONIZATION_THRESHOLD = 1.0
DEFAULT_CANONIZATION_LIMIT = 100
MAX_CANONIZATION_LIMIT = 100
MAX_PRODUCTS_TO_COMPARE = 500
_GENERIC_TOKENS = {"de", "da", "do", "das", "dos", "e"}


@dataclass(frozen=True)
class ProductMatchInput:
    ean: str
    name: str
    category: str | None = None
    department_id: object | None = None


@dataclass(frozen=True)
class ProductMatch:
    ean: str
    name: str
    category: str | None
    similarity: float
    reason: str | None = "Nome normalizado similar"


@dataclass(frozen=True)
class ProductMatchGroup:
    primary: ProductMatchInput
    matches: list[ProductMatch]


def _safe_threshold(threshold: float | None) -> float:
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        value = DEFAULT_CANONIZATION_THRESHOLD
    return max(MIN_CANONIZATION_THRESHOLD, min(MAX_CANONIZATION_THRESHOLD, value))


def _safe_limit(limit: int | None) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_CANONIZATION_LIMIT
    return max(1, min(MAX_CANONIZATION_LIMIT, value))


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in strong_normalize_product_name(value).split()
        if token not in _GENERIC_TOKENS
    }


def calculate_product_similarity(name_a: str | None, name_b: str | None) -> float:
    """Return a conservative RapidFuzz similarity score between 0.0 and 1.0."""

    normalized_a = strong_normalize_product_name(name_a)
    normalized_b = strong_normalize_product_name(name_b)
    if not normalized_a or not normalized_b:
        return 0.0
    if normalized_a == normalized_b:
        return 1.0

    tokens_a = _meaningful_tokens(normalized_a)
    tokens_b = _meaningful_tokens(normalized_b)
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return 0.0

    overlap = len(tokens_a & tokens_b)
    essential_overlap = overlap / max(len(tokens_a), len(tokens_b))
    if overlap == 0 or essential_overlap < 0.5:
        return 0.0

    token_sort = fuzz.token_sort_ratio(normalized_a, normalized_b) / 100
    token_set = fuzz.token_set_ratio(normalized_a, normalized_b) / 100
    ratio = fuzz.ratio(normalized_a, normalized_b) / 100
    score = (token_sort * 0.45) + (token_set * 0.35) + (ratio * 0.20)

    if essential_overlap < 0.75:
        score *= essential_overlap

    return round(max(0.0, min(1.0, score)), 4)


def _category_key(category: str | None) -> str:
    normalized = strong_normalize_product_name(category)
    return normalized or "__uncategorized__"


def generate_product_match_groups(
    products: Iterable[ProductMatchInput],
    threshold: float | None = DEFAULT_CANONIZATION_THRESHOLD,
    limit: int | None = DEFAULT_CANONIZATION_LIMIT,
    include_reasons: bool = True,
) -> tuple[list[ProductMatchGroup], int, float, int]:
    """Generate read-only candidate groups from already scoped products."""

    safe_threshold = _safe_threshold(threshold)
    safe_limit = _safe_limit(limit)
    scoped_products = [
        product
        for product in products
        if product.ean and strong_normalize_product_name(product.name)
    ][:MAX_PRODUCTS_TO_COMPARE]

    buckets: dict[tuple[object | None, str], list[ProductMatchInput]] = defaultdict(list)
    for product in scoped_products:
        buckets[(product.department_id, _category_key(product.category))].append(product)

    groups: list[ProductMatchGroup] = []
    consumed_primary_eans: set[tuple[object | None, str]] = set()

    for bucket_products in buckets.values():
        ordered = sorted(
            bucket_products,
            key=lambda product: (
                strong_normalize_product_name(product.name),
                product.ean,
            ),
        )

        for index, primary in enumerate(ordered):
            primary_key = (primary.department_id, primary.ean)
            if primary_key in consumed_primary_eans:
                continue

            matches: list[ProductMatch] = []
            for candidate in ordered[index + 1 :]:
                similarity = calculate_product_similarity(primary.name, candidate.name)
                if similarity >= safe_threshold:
                    matches.append(
                        ProductMatch(
                            ean=candidate.ean,
                            name=candidate.name,
                            category=candidate.category,
                            similarity=similarity,
                            reason=(
                                "Nome normalizado similar"
                                if include_reasons
                                else None
                            ),
                        )
                    )

            if matches:
                groups.append(ProductMatchGroup(primary=primary, matches=matches))
                consumed_primary_eans.add(primary_key)
                for match in matches:
                    consumed_primary_eans.add((primary.department_id, match.ean))

    groups.sort(
        key=lambda group: (
            max(match.similarity for match in group.matches),
            len(group.matches),
            group.primary.name,
        ),
        reverse=True,
    )

    return groups[:safe_limit], len(groups), safe_threshold, safe_limit
