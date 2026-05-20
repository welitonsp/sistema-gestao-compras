"""Schemas da importacao de notas fiscais por chave de acesso."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ChaveAcesso44 = Annotated[
    str,
    StringConstraints(
        min_length=44,
        max_length=44,
        pattern=r"^\d{44}$",
    ),
]
"""Tipo reutilizavel para chave de acesso com 44 digitos numericos."""


class ImportacaoChaveRequest(BaseModel):
    """Payload de entrada para importacao de nota fiscal pela chave."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    chave_acesso: ChaveAcesso44 = Field(
        ...,
        description="Chave de acesso da nota fiscal com 44 digitos.",
        examples=["52260412345678000123550010000012341000012345"],
    )

    @field_validator("chave_acesso", mode="before")
    @classmethod
    def normalizar_chave_acesso(cls, value: object) -> object:
        """Remove mascaras visuais antes da validacao formal."""

        if not isinstance(value, str):
            return value
        return re.sub(r"\D", "", value)


class FornecedorImportadoResponse(BaseModel):
    """Dados resumidos do fornecedor retornados ao cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None


class NotaFiscalImportadaResponse(BaseModel):
    """Dados resumidos da nota fiscal importada."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero_nota: str
    chave_acesso: str
    data_emissao: date
    valor_total: Decimal


class ItemNotaFiscalImportadoResponse(BaseModel):
    """Item importado da nota fiscal."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo_produto: str = Field(..., alias="ean")
    descricao: str = Field(..., alias="descricao_original")
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal


class ImportacaoNotaResponse(BaseModel):
    """Resposta padronizada da importacao por chave de acesso."""

    model_config = ConfigDict(from_attributes=True)

    mensagem: str
    fornecedor: FornecedorImportadoResponse
    nota_fiscal: NotaFiscalImportadaResponse
    itens: list[ItemNotaFiscalImportadoResponse]
    total_itens: int


class ProcessamentoLoteResponse(BaseModel):
    """Resposta para o início de um processamento em lote."""
    mensagem: str
    total_arquivos: int
    job_ids: list[str]
