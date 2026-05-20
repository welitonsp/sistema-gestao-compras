"""DTOs (Data Transfer Objects) for internal procurement flow."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field


class FornecedorDTO(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None


class ItemNotaDTO(BaseModel):
    codigo_produto: str = Field(..., alias="ean")
    descricao: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal

    class Config:
        populate_by_name = True


class NotaFiscalDTO(BaseModel):
    numero_nota: str
    data_emissao: date
    valor_total: Decimal
    itens: list[ItemNotaDTO]
    fornecedor: FornecedorDTO
