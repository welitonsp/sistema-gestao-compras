from __future__ import annotations
from pydantic import BaseModel, ConfigDict, field_validator

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
