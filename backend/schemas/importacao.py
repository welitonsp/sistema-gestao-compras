"""Schemas da importacao de notas fiscais por chave de acesso."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from backend.core.fiscal import classificar_identificador_importacao

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

    chave_acesso: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Chave de acesso, payload QR Code NFC-e ou URL completa do QR Code.",
        examples=[
            "52260412345678000123550010000012341000012345",
            "https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p=5226...|2|1|...",
        ],
    )

    @field_validator("chave_acesso", mode="before")
    @classmethod
    def normalizar_chave_acesso(cls, value: object) -> object:
        """Normaliza apenas chave pura; preserva URL/payload QR Code."""

        if not isinstance(value, str):
            return value
        identificador = value.strip()
        classificacao = classificar_identificador_importacao(identificador)
        if classificacao.kind == "plain_access_key":
            return classificacao.access_key
        return identificador


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
    extraction_quality_status: str | None = None
    extraction_parser_source: str | None = None
    extraction_item_count: int | None = None
    extraction_missing_ean_count: int | None = None
    extraction_empty_description_count: int | None = None
    extraction_invalid_quantity_count: int | None = None
    extraction_invalid_value_count: int | None = None
    extraction_total_itens: Decimal | None = None
    extraction_total_nota: Decimal | None = None
    extraction_total_mismatch: bool | None = None
    extraction_quality_details: str | None = None


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


class ImportacaoLoteChavesRequest(BaseModel):
    """Payload para importacao sequencial de um lote pequeno de chaves."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    chaves_acesso: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Lista de 1 a 5 chaves, payloads QR Code NFC-e ou URLs completas do QR Code.",
    )

    @field_validator("chaves_acesso", mode="before")
    @classmethod
    def normalizar_chaves_acesso(cls, value: object) -> object:
        """Normaliza apenas chaves puras; preserva URLs/payloads QR Code."""

        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if not isinstance(item, str):
                normalized.append(item)
                continue
            identificador = item.strip()
            classificacao = classificar_identificador_importacao(identificador)
            normalized.append(
                classificacao.access_key
                if classificacao.kind == "plain_access_key"
                else identificador
            )
        return normalized

    @field_validator("chaves_acesso")
    @classmethod
    def rejeitar_chaves_duplicadas(cls, value: list[str]) -> list[str]:
        identities = []
        for item in value:
            classificacao = classificar_identificador_importacao(item)
            identities.append(classificacao.access_key or classificacao.qrcode_payload or item)
        if len(set(identities)) != len(identities):
            raise ValueError("Chaves duplicadas no payload.")
        return value


class ImportacaoLoteResultadoResponse(BaseModel):
    """Resultado individual de uma chave processada em lote."""

    chave_acesso: str
    status: Literal["success", "duplicate", "failed"]
    mensagem: str
    nota_fiscal: NotaFiscalImportadaResponse | None = None
    error_code: str | None = None


class ImportacaoLoteChavesResponse(BaseModel):
    """Resultado agregado da importacao sequencial de chaves."""

    total: int
    success_count: int
    duplicate_count: int
    failed_count: int
    results: list[ImportacaoLoteResultadoResponse]


class ArchiveImportacaoRequest(BaseModel):
    """Payload para archive auditavel de uma importacao."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    motivo: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Motivo operacional para arquivar a importacao.",
    )


class ArchiveImportacaoResponse(BaseModel):
    """Resposta minima do archive de importacao."""

    mensagem: str
    status: str
    chave_acesso: str
    archived_at: datetime
    archived_by: str
    archive_reason: str


class ImportacaoHistoricoItemResponse(BaseModel):
    """Item operacional do historico de importacoes."""

    id: UUID
    chave_acesso: str
    numero_nota: str
    fornecedor: str
    data_emissao: date
    valor_total: Decimal
    status: str
    created_at: datetime
    imported_at: datetime
    extraction_quality_status: str | None = None
    extraction_parser_source: str | None = None
    extraction_item_count: int | None = None
    extraction_missing_ean_count: int | None = None
    extraction_total_mismatch: bool | None = None
    extraction_quality_details: str | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None
    archive_reason: str | None = None


class ImportacoesHistoricoResponse(BaseModel):
    """Resposta paginada simples para acompanhamento operacional de importacoes."""

    items: list[ImportacaoHistoricoItemResponse]
    total: int
    limit: int
    offset: int
    status: str
    quality_status: str


class ProcessamentoLoteResponse(BaseModel):
    """Resposta para o início de um processamento em lote."""
    mensagem: str
    total_arquivos: int
    job_ids: list[str]
