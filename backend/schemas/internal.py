"""DTOs (Data Transfer Objects) for internal procurement flow."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class FornecedorDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None


class ItemNotaDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    codigo_produto: str = Field(..., alias="ean")
    descricao: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal
    marca: str | None = None
    categoria: str | None = None
    categoria_sugerida_origem: str | None = None
    categoria_sugerida_confidence: Decimal | None = None
    categoria_sugerida_modelo: str | None = None


class NotaFiscalDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chave_acesso: str
    numero_nota: str
    data_emissao: date
    valor_total: Decimal
    itens: list[ItemNotaDTO]
    fornecedor: FornecedorDTO
