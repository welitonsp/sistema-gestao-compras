"""Pydantic schemas for product canonization read-only previews."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CanonizationProduct(BaseModel):
    ean: str
    name: str
    category: str | None = None


class CanonizationMatch(CanonizationProduct):
    similarity: float = Field(ge=0, le=1)
    reason: str | None = None


class CanonizationCandidateGroup(BaseModel):
    primary: CanonizationProduct
    matches: list[CanonizationMatch]


class CanonizationCandidatesResponse(BaseModel):
    groups: list[CanonizationCandidateGroup]
    total_groups: int = Field(ge=0)
    threshold: float = Field(ge=0, le=1)
    limit: int = Field(ge=1)


class CanonizationMappingItem(BaseModel):
    department_id: UUID
    department_name: str | None = None
    ean_original: str
    original_name: str | None = None
    ean_canonico: str
    canonical_name: str | None = None
    status: str
    reason: str | None = None
    confidence_score: float | None = None
    confirmado_por: str | None = None
    confirmado_em: datetime | None = None
    revertido_por: str | None = None
    revertido_em: datetime | None = None
    revert_reason: str | None = None


class CanonizationMappingStatusCounts(BaseModel):
    all: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)
    reverted: int = Field(ge=0)


class CanonizationMappingsResponse(BaseModel):
    items: list[CanonizationMappingItem]
    total: int = Field(ge=0)
    status: str
    query: str | None = None
    sort_by: str
    sort_dir: str
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    counts: CanonizationMappingStatusCounts


class CanonizationConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ean_canonico: str
    eans_originais: list[str]
    reason: str | None = None
    department_id: UUID | None = None
    confirmed: bool | None = None


class CanonizationCreatedMapping(BaseModel):
    ean_original: str
    ean_canonico: str
    status: str


class CanonizationConfirmationResponse(BaseModel):
    summary: str
    created_count: int = Field(ge=0)
    ean_canonico: str
    department_id: UUID
    created_mappings: list[CanonizationCreatedMapping]


class CanonizationRevertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ean_original: str
    reason: str | None = None
    department_id: UUID | None = None
    confirmed: bool | None = None


class CanonizationRevertResponse(BaseModel):
    ean_original: str
    ean_canonico: str
    department_id: UUID
    status: str
    revertido_por: str
    revertido_em: datetime
    revert_reason: str | None = None
    message: str
