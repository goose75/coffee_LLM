"""Pydantic v2 schemas for the taste intelligence API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaggedNote(BaseModel):
    raw_note: str
    slug: str
    label: str
    confidence: float
    source: str


class FlavorFamilySummary(BaseModel):
    family_slug: str
    family_label: str
    colour: str
    tags: list[TaggedNote] = Field(default_factory=list)
    weight: int = 0   # number of tags — drives visualisation sizing


class TasteProfile(BaseModel):
    bean_id: UUID
    canonical_name: str
    raw_notes: list[str]
    families: list[FlavorFamilySummary] = Field(default_factory=list)
    has_structured_tags: bool
    tag_count: int


class SimilarCoffee(BaseModel):
    bean_id: UUID
    canonical_name: str
    origin_country: str | None
    process: str | None
    roast_level: str | None
    flavour_notes: list[str]
    similarity_score: float
    shared_families: list[str]


class FamilyDistributionRow(BaseModel):
    dimension_value: str
    family_counts: dict[str, int]
    total_tags: int


class FamilyDistribution(BaseModel):
    dimension_type: str
    rows: list[FamilyDistributionRow]


class TagReviewItem(BaseModel):
    tag_id: UUID
    bean_id: UUID
    bean_name: str
    raw_note: str
    slug: str
    label: str
    confidence: float
    source: str
    review_status: str
    llm_audit: dict | None
    created_at: datetime
