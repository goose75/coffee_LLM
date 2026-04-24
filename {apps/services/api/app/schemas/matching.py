"""Pydantic v2 schemas for the canonical match review API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class CanonicalBeanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    origin_country: str | None
    origin_region: str | None
    farm_or_estate: str | None
    process: str | None
    roast_level: str | None
    varietal: list[str]
    flavour_notes: list[str]
    harvest_year: int | None
    data_completeness_score: float


class BeanListingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_title: str
    raw_description: str | None
    origin_label_raw: str | None
    process_label_raw: str | None
    roast_label_raw: str | None
    varietal_label_raw: str | None
    active_flag: bool
    first_seen_at: datetime
    store_id: UUID


class MatchSignalsSchema(BaseModel):
    exact_score: float = 0.0
    fuzzy_score: float = 0.0
    embedding_score: float = 0.0
    harvest_score: float = 1.0
    field_matches: dict = {}
    combined: float = 0.0


class CanonicalMatchItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bean_listing_id: UUID
    proposed_canonical_bean_id: UUID
    match_method: str
    confidence_score: float
    accepted_by_system_flag: bool
    reviewed_by_user_id: str | None
    review_status: str
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    match_signals: dict | None

    # Hydrated sub-objects (populated via API join)
    bean_listing: BeanListingSummary | None = None
    proposed_canonical_bean: CanonicalBeanSummary | None = None

    @computed_field
    @property
    def confidence_band(self) -> str:
        if self.confidence_score >= 0.92:
            return "auto_accept"
        if self.confidence_score >= 0.75:
            return "review"
        return "new_canonical"


class PaginatedMatches(BaseModel):
    data: list[CanonicalMatchItem]
    total: int
    page: int
    page_size: int
    has_next: bool
    pending_count: int = 0


class ReviewActionRequest(BaseModel):
    notes: str | None = None
    user_id: str | None = None


class MatchActionResponse(BaseModel):
    match_id: UUID
    outcome: str
    canonical_bean_id: UUID | None
    review_status: str


class MatchDecisionSchema(BaseModel):
    """Response from POST /admin/review/run-matching."""
    outcome: str
    listing_id: UUID
    canonical_match_id: UUID | None
    canonical_bean_id: UUID | None
    confidence: float
    signals: dict | None
    error: str | None
