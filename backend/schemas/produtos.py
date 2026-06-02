from __future__ import annotations
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.text_sanitizer import UnsafeLabelError, sanitize_manual_brand, sanitize_manual_category

class ProdutoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome_limpo: str | None = None
    marca: str | None = None
    categoria: str | None = None
    unidade: str | None = None

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, value: str | None) -> str | None:
        try:
            return sanitize_manual_category(value)
        except UnsafeLabelError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("marca")
    @classmethod
    def validar_marca(cls, value: str | None) -> str | None:
        try:
            return sanitize_manual_brand(value)
        except UnsafeLabelError as exc:
            raise ValueError(str(exc)) from exc

class ProdutoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ean: str
    nome_limpo: str
    marca: str | None
    categoria: str
    unidade: str


class CategorySuggestionCandidate(BaseModel):
    ean: str
    product_name: str
    current_category: str | None
    suggested_category: str | None
    confidence: float = Field(ge=0, le=1)
    confidence_level: Literal["high", "medium", "low", "insufficient_data"]
    source: Literal["item_suggestion", "classification_cache", "rules", "none"]
    reason: str
    occurrence_count: int = Field(ge=0)
    last_seen: date | None
    can_confirm: bool


class CategorySuggestionCandidatesResponse(BaseModel):
    total_candidates: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    candidates: list[CategorySuggestionCandidate]
