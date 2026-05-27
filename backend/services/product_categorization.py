"""Pure deterministic product categorization helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


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
