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
    # accepted_by_system_flag removed from model — use review_status == "accepted"
    reviewed_by: str | None = None          # maps to model's reviewed_by column
    review_status: str
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    match_signals_json: dict | None = None  # actual column name in model

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


class BulkReviewRequest(BaseModel):
    """Bulk-accept/reject by explicit IDs OR by filter. Provide one or the other."""
    match_ids: list[UUID] | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    match_method: str | None = None
    notes: str | None = None
    user_id: str | None = None
    limit: int = 1000


class BulkReviewResponse(BaseModel):
    outcome: str            # "accepted" | "rejected"
    affected: int
    skipped: list[str]      # match IDs that were not pending or not found


# ── Data-quality issues ───────────────────────────────────────────────────────

class FieldDisagreement(BaseModel):
    field: str
    canonical_value: str | None
    listing_majority_value: str | None
    listings_disagreeing: int
    total_listings: int


class DataQualityIssue(BaseModel):
    """A flag against one canonical bean. Multiple issues per bean possible."""
    issue_type: str         # "field_disagreement" | "duplicate_suspect" | "stale_auto_accept" | "very_sparse"
    bean_id: UUID
    canonical_name: str
    severity: str           # "low" | "medium" | "high"
    summary: str            # human-readable one-liner
    field_disagreements: list[FieldDisagreement] = []
    duplicate_of_bean_id: UUID | None = None       # if issue_type == duplicate_suspect
    duplicate_of_name: str | None = None
    stale_match_id: UUID | None = None             # if issue_type == stale_auto_accept


class DataQualityReport(BaseModel):
    issues: list[DataQualityIssue]
    counts_by_type: dict[str, int]
    total: int


# ── Field enhancement / enrichment ────────────────────────────────────────────

class FieldSuggestion(BaseModel):
    field: str
    current_value: str | None              # what the canonical has now
    suggested_value: str | None            # extractor's proposal
    confidence: float
    source_summary: str                    # e.g. "5 of 7 listings agree"


class EnhancementProposal(BaseModel):
    """The diff produced by the LLM enhancer for one canonical bean."""
    bean_id: UUID
    canonical_name: str
    current_completeness: float
    listings_considered: int
    suggestions: list[FieldSuggestion]
    notes: str | None = None


class EnhancementApplyRequest(BaseModel):
    """Apply selected suggestions to the canonical bean."""
    accepted_fields: list[str]             # field names to copy from suggestion → canonical
    user_id: str | None = None


class EnhancementApplyResponse(BaseModel):
    bean_id: UUID
    fields_updated: list[str]
    new_completeness: float


class BulkEnhancementSummary(BaseModel):
    """Result of running enhancement across many beans."""
    beans_examined: int
    beans_updated: int
    fields_updated_total: int
    skipped_no_listings: int
    skipped_no_suggestions: int
    errors: list[str] = []


# ── Merge ─────────────────────────────────────────────────────────────────────

class MergeRequest(BaseModel):
    """Merge `source_bean_id` into `target_bean_id`."""
    source_bean_id: UUID
    target_bean_id: UUID
    delete_source: bool = True   # soft-delete via active_flag would need a column; we hard-delete
    user_id: str | None = None


class MergeResult(BaseModel):
    target_bean_id: UUID
    relinked_listings: int
    relinked_matches: int
    fields_copied: list[str]
    source_deleted: bool


class MatchDecisionSchema(BaseModel):
    """Response from POST /admin/review/run-matching."""
    outcome: str
    listing_id: UUID
    canonical_match_id: UUID | None
    canonical_bean_id: UUID | None
    confidence: float
    signals: dict | None
    error: str | None


# ── Review analytics ──────────────────────────────────────────────────────────

class HistogramBin(BaseModel):
    bin_label: str          # e.g. "0.7-0.8"
    bin_min: float
    bin_max: float
    count: int


class FieldCoverage(BaseModel):
    field: str              # origin_country | process | varietal | farm_or_estate
    matched: int            # field_matches[field] is True
    mismatched: int         # field_matches[field] is False
    skipped: int            # one side blank


class TopBlocker(BaseModel):
    """A pattern that's keeping matches stuck in pending."""
    label: str
    count: int
    description: str


class ReviewAnalytics(BaseModel):
    """Aggregate analytics over the canonical-match queue."""
    pending_count: int
    accepted_count: int
    rejected_count: int

    # Confidence distribution for pending matches (10 bins, 0.0–1.0)
    pending_confidence_histogram: list[HistogramBin]

    # Distribution of each per-signal score, pending only
    exact_score_histogram: list[HistogramBin]
    fuzzy_score_histogram: list[HistogramBin]
    embedding_score_histogram: list[HistogramBin]

    # Field-match coverage across pending matches
    field_coverage: list[FieldCoverage]

    # Match method breakdown for pending
    method_breakdown: dict[str, int]

    # Top patterns that are blocking pending → accepted transitions
    top_blockers: list[TopBlocker]

    # Canonical bean catalogue completeness — distribution buckets
    catalogue_completeness_histogram: list[HistogramBin]
    canonical_bean_count: int
    avg_canonical_completeness: float
