"""Pure deterministic product categorization helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import (
    ClassificacaoCache,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
)
from backend.schemas.produtos import (
    CategorySuggestionCandidate,
    CategorySuggestionCandidatesResponse,
)


CATEGORIAS_CANONICAS = (
    "HORTIFRUTI",
    "AÇOUGUE",
    "FRIOS E LATICÍNIOS",
    "PADARIA",
    "MERCEARIA",
    "BEBIDAS",
    "CONGELADOS",
    "DOCES E SOBREMESAS",
    "LIMPEZA",
    "HIGIENE E BELEZA",
    "UTILIDADES DOMÉSTICAS",
    "PET",
    "OUTROS",
)

ALLOWED_AI_CATEGORIES = [
    "Alimentos",
    "Bebidas",
    "Limpeza",
    "Higiene",
    "Medicamentos",
    "Material de Escritório",
    "Eletrônicos",
    "Manutenção",
    "Vestuário",
    "Outros",
]

ACTIVE_INVOICE_STATUS = "active"
UNCATEGORIZED_LABELS = {
    "",
    "outro",
    "outros",
    "nao classificado",
    "não classificado",
    "sem categoria",
    "sem categoria definida",
    "nao categorizado",
    "não categorizado",
}
AI_PROMPT_CONTROL_PATTERNS = (
    r"```",
    r"\{\{",
    r"\}\}",
    r"<script",
    r"\bsystem\s*:",
    r"\bassistant\s*:",
    r"\buser\s*:",
)
SENSITIVE_AI_INPUT_PATTERNS = (
    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
    r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
    r"\b\d{44}\b",
    r"https?://",
    r"\bwww\.",
    r"\bsefaz\b",
    r"\bqr[\s_-]*code\b",
    r"\bxml\b",
    r"\b\d{11,}\b",
)


@dataclass(frozen=True)
class ProdutoCategorizado:
    descricao_original: str
    descricao_normalizada: str
    produto_base: str
    categoria: str
    subcategoria: str | None
    origem_categorizacao: str
    confianca: float


@dataclass(frozen=True)
class RegraCategorizacaoProduto:
    padroes: tuple[str, ...]
    produto_base: str
    categoria: str
    subcategoria: str | None
    confianca: float = 0.95


REGRAS_DETERMINISTICAS: tuple[RegraCategorizacaoProduto, ...] = (
    RegraCategorizacaoProduto((r"\barroz\b",), "ARROZ", "MERCEARIA", "ARROZ"),
    RegraCategorizacaoProduto((r"\bfeijao\b",), "FEIJÃO", "MERCEARIA", "FEIJÃO"),
    RegraCategorizacaoProduto((r"\bqueijo\b", r"\bmussarela\b", r"\bmucarela\b"), "QUEIJO", "FRIOS E LATICÍNIOS", "QUEIJOS"),
    RegraCategorizacaoProduto((r"\biog\w*", r"\biogurte\b"), "IOGURTE", "FRIOS E LATICÍNIOS", "IOGURTES"),
    RegraCategorizacaoProduto((r"\bleite\b",), "LEITE", "FRIOS E LATICÍNIOS", "LEITES"),
    RegraCategorizacaoProduto((r"\bmacarrao\b", r"\bmassa\b", r"\bravioli\b", r"\bpenne\b", r"\bsemola\b"), "MASSA", "MERCEARIA", "MASSAS"),
    RegraCategorizacaoProduto((r"\bvinagre\b",), "VINAGRE", "MERCEARIA", "TEMPEROS"),
    RegraCategorizacaoProduto((r"\bazeite\b", r"\boleo\b"), "ÓLEO/AZEITE", "MERCEARIA", "ÓLEOS E AZEITES"),
    RegraCategorizacaoProduto((r"\bdesinf\w*", r"\blimp\w*", r"\bamac\w*"), "LIMPEZA", "LIMPEZA", None),
    RegraCategorizacaoProduto((r"\bshampoo\b", r"\bdesodorante\b", r"\bcreme dental\b", r"\benx bucal\b"), "HIGIENE", "HIGIENE E BELEZA", None),
    RegraCategorizacaoProduto((r"\brodo\b", r"\bfaqueiro\b"), "UTILIDADE DOMÉSTICA", "UTILIDADES DOMÉSTICAS", None),
)


def normalizar_descricao_produto(descricao: str) -> str:
    """Normalize product text for deterministic matching without mutating the original."""

    normalized = unicodedata.normalize("NFKD", descricao or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalizar_categoria(categoria: str | None) -> str:
    return normalizar_descricao_produto(categoria or "")


def _categoria_precisa_revisao(categoria: str | None) -> bool:
    return _normalizar_categoria(categoria) in UNCATEGORIZED_LABELS


def _clamp_confidence(value: float | Decimal | None) -> float:
    if value is None:
        return 0.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    if confidence > 0:
        return "low"
    return "insufficient_data"


def _contains_sensitive_ai_input(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return True

    if (
        (normalized.startswith("{") and normalized.endswith("}"))
        or (normalized.startswith("[") and normalized.endswith("]"))
    ):
        return True

    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in SENSITIVE_AI_INPUT_PATTERNS
    )


def _strip_prompt_control_tokens(value: str) -> str:
    sanitized = value
    for pattern in AI_PROMPT_CONTROL_PATTERNS:
        sanitized = re.sub(pattern, " ", sanitized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", sanitized).strip()


def sanitize_ai_category_product_name(product_name: str | None) -> str | None:
    """Sanitize the canonical product name allowed for a future AI fallback."""

    if product_name is None:
        return None

    normalized = re.sub(r"\s+", " ", str(product_name)).strip()
    if not normalized or _contains_sensitive_ai_input(normalized):
        return None

    sanitized = _strip_prompt_control_tokens(normalized)
    if not sanitized or _contains_sensitive_ai_input(sanitized):
        return None

    return sanitized[:80].strip() or None


def build_ai_category_prompt_payload(
    product_name: str | None,
    allowed_categories: list[str] | None = None,
) -> dict | None:
    """Build a minimal structured payload for future category fallback prompts."""

    sanitized_product_name = sanitize_ai_category_product_name(product_name)
    if sanitized_product_name is None:
        return None

    safe_allowed_categories = [
        category
        for category in (allowed_categories or ALLOWED_AI_CATEGORIES)
        if category in ALLOWED_AI_CATEGORIES
    ]

    return {
        "sanitized_product_name": sanitized_product_name,
        "allowed_categories": safe_allowed_categories,
    }


def _sanitize_ai_reason(value: object) -> str:
    if not isinstance(value, str):
        return "Sem justificativa segura."

    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return "Sem justificativa segura."

    sanitized = _strip_prompt_control_tokens(normalized)
    if not sanitized or _contains_sensitive_ai_input(sanitized):
        return "Justificativa removida por segurança."

    return sanitized[:160].strip() or "Sem justificativa segura."


def parse_ai_category_response(
    response: dict,
    allowed_categories: list[str] | None = None,
) -> dict:
    """Parse a future AI category response with allow-list and safe fallback."""

    safe_allowed_categories = [
        category
        for category in (allowed_categories or ALLOWED_AI_CATEGORIES)
        if category in ALLOWED_AI_CATEGORIES
    ]

    fallback = {
        "suggested_category": None,
        "confidence": 0.0,
        "confidence_level": "insufficient_data",
        "reason": "Resposta sem categoria permitida.",
        "source": "ai_fallback_contract",
    }

    if not isinstance(response, dict):
        return fallback

    suggested_category = response.get("suggested_category")
    if suggested_category not in safe_allowed_categories:
        return {
            **fallback,
            "reason": _sanitize_ai_reason(response.get("reason")),
        }

    confidence = _clamp_confidence(response.get("confidence"))

    return {
        "suggested_category": suggested_category,
        "confidence": confidence,
        "confidence_level": _confidence_level(confidence),
        "reason": _sanitize_ai_reason(response.get("reason")),
        "source": "ai_fallback_contract",
    }


def _cache_keys_for_product(product_name: str, descriptions: Iterable[str]) -> set[str]:
    keys = {
        normalizar_descricao_produto(product_name),
        (product_name or "").upper().strip(),
    }
    for description in descriptions:
        keys.add(normalizar_descricao_produto(description))
        keys.add((description or "").upper().strip())
    return {key for key in keys if key}


def categorizar_produto(descricao: str) -> ProdutoCategorizado:
    descricao_original = descricao or ""
    descricao_normalizada = normalizar_descricao_produto(descricao_original)

    for regra in REGRAS_DETERMINISTICAS:
        if any(re.search(padrao, descricao_normalizada) for padrao in regra.padroes):
            return ProdutoCategorizado(
                descricao_original=descricao_original,
                descricao_normalizada=descricao_normalizada,
                produto_base=regra.produto_base,
                categoria=regra.categoria,
                subcategoria=regra.subcategoria,
                origem_categorizacao="deterministica",
                confianca=regra.confianca,
            )

    return ProdutoCategorizado(
        descricao_original=descricao_original,
        descricao_normalizada=descricao_normalizada,
        produto_base="OUTROS",
        categoria="OUTROS",
        subcategoria=None,
        origem_categorizacao="sem_regra",
        confianca=0.2,
    )


def categorizar_produtos(descricoes: Iterable[str]) -> list[ProdutoCategorizado]:
    return [categorizar_produto(descricao) for descricao in descricoes]


async def get_category_suggestion_candidates(
    db: AsyncSession,
    department_id: UUID | None = None,
    limit: int = 25,
    min_confidence: float | Decimal | None = 0,
    category_filter: str | None = None,
    include_low_confidence: bool = True,
) -> CategorySuggestionCandidatesResponse:
    """Return read-only category review candidates from active fiscal items."""

    safe_limit = max(1, min(100, limit))
    confidence_floor = _clamp_confidence(min_confidence)

    stmt = (
        select(
            Produto.ean,
            Produto.nome_limpo,
            Produto.categoria,
            Produto.categoria_confirmada,
            ItemNotaFiscal.descricao_original,
            ItemNotaFiscal.categoria_sugerida,
            ItemNotaFiscal.categoria_sugerida_confidence,
            NotaFiscal.data_emissao,
        )
        .join(ItemNotaFiscal, ItemNotaFiscal.ean == Produto.ean)
        .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
        .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        .where(or_(Produto.categoria_confirmada == None, Produto.categoria_confirmada == ""))
    )

    if department_id is not None:
        stmt = stmt.where(NotaFiscal.department_id == department_id)

    if category_filter:
        stmt = stmt.where(Produto.categoria == category_filter)

    result = await db.execute(stmt)
    rows_by_ean: dict[str, list] = {}
    for row in result.fetchall():
        rows_by_ean.setdefault(row.ean, []).append(row)

    candidates: list[CategorySuggestionCandidate] = []
    for ean, rows in rows_by_ean.items():
        first = rows[0]
        current_category = first.categoria
        descriptions = [row.descricao_original for row in rows if row.descricao_original]

        item_suggestions: dict[str, list[float]] = {}
        for row in rows:
            if row.categoria_sugerida:
                item_suggestions.setdefault(row.categoria_sugerida, []).append(
                    _clamp_confidence(row.categoria_sugerida_confidence)
                )

        has_missing_or_low_item_suggestion = not item_suggestions or any(
            confidence < 0.5
            for confidences in item_suggestions.values()
            for confidence in confidences
        )
        if (
            not _categoria_precisa_revisao(current_category)
            and not has_missing_or_low_item_suggestion
        ):
            continue

        suggested_category: str | None = None
        confidence = 0.0
        source = "none"
        reason = "Dados insuficientes para sugerir uma categoria com segurança."

        if item_suggestions:
            chosen_category, confidences = sorted(
                item_suggestions.items(),
                key=lambda item: (
                    len(item[1]),
                    sum(item[1]) / len(item[1]) if item[1] else 0,
                    item[0],
                ),
                reverse=True,
            )[0]
            suggested_category = chosen_category
            confidence = _clamp_confidence(
                sum(confidences) / len(confidences) if confidences else 0.5
            )
            source = "item_suggestion"
            reason = (
                "Categoria sugerida recorrente em itens fiscais ativos do "
                "mesmo produto."
            )
        else:
            cache_keys = _cache_keys_for_product(first.nome_limpo, descriptions)
            cache_stmt = (
                select(ClassificacaoCache)
                .where(
                    or_(
                        ClassificacaoCache.descricao_original.in_(cache_keys),
                        ClassificacaoCache.produto_canonico == first.nome_limpo,
                    )
                )
                .order_by(ClassificacaoCache.verificado_usuario.desc())
                .limit(1)
            )
            cache_result = await db.execute(cache_stmt)
            cache_entry = cache_result.scalar_one_or_none()

            if cache_entry:
                suggested_category = cache_entry.categoria
                confidence = 0.85 if cache_entry.verificado_usuario else 0.65
                source = "classification_cache"
                reason = (
                    "Categoria recuperada do cache de classificação existente, "
                    "sem alteração de dados."
                )
            else:
                rule_result = categorizar_produto(first.nome_limpo)
                if rule_result.origem_categorizacao == "deterministica":
                    suggested_category = rule_result.categoria
                    confidence = _clamp_confidence(rule_result.confianca)
                    source = "rules"
                    reason = (
                        "Categoria sugerida por regra determinística aplicada "
                        "ao nome canônico do produto."
                    )

        confidence = _clamp_confidence(confidence)
        if confidence < confidence_floor:
            continue

        level = _confidence_level(confidence)
        if not include_low_confidence and level in {"low", "insufficient_data"}:
            continue

        candidates.append(
            CategorySuggestionCandidate(
                ean=ean,
                product_name=first.nome_limpo,
                current_category=current_category,
                suggested_category=suggested_category,
                confidence=confidence,
                confidence_level=level,
                source=source,
                reason=reason,
                occurrence_count=len(rows),
                last_seen=max(row.data_emissao for row in rows),
                can_confirm=suggested_category is not None and confidence > 0,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.can_confirm,
            candidate.confidence,
            candidate.occurrence_count,
            candidate.product_name,
        ),
        reverse=True,
    )

    return CategorySuggestionCandidatesResponse(
        total_candidates=len(candidates),
        returned_count=len(candidates[:safe_limit]),
        candidates=candidates[:safe_limit],
    )
