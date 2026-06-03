"""Pydantic schemas for product canonization read-only previews."""

from __future__ import annotations

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
