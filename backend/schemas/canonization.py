"""Pydantic schemas for product canonization read-only previews."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
