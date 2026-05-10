"""
Pydantic v2 response schemas for the sources / stores API.

Kept separate from SQLAlchemy models so the API contract can evolve
independently. All datetimes serialised as ISO 8601 strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ─── Source page sub-schema ───────────────────────────────────────────────────

class SourcePageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    page_type: str
    parser_strategy: str
    discovered_at: datetime
    last_fetched_at: datetime | None = None
    status_code: int | None = None
    changed_flag: bool


# ─── Store / Source schemas ───────────────────────────────────────────────────

class StoreBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str
    homepage_url: str
    source_type: str
    parser_strategy: str
    country_code: str
    uk_region: str | None
    roaster_flag: bool
    cafe_flag: bool
    ecommerce_flag: bool
    active_flag: bool
    crawl_frequency_hours: int
    last_successful_crawl_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LastRunSummary(BaseModel):
    """Compact summary of the most recent ingestion run for a store."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str               # running | completed | partial | failed
    started_at: datetime
    completed_at: datetime | None = None
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    error_count: int = 0
    warning_count: int = 0
    top_errors: list[str] = Field(default_factory=list)   # first ~3 error messages
    top_error_buckets: dict[str, int] = Field(default_factory=dict)  # message → count


class StoreListItem(StoreBase):
    """Compact representation for table listings."""

    last_run: Optional[LastRunSummary] = None

    @computed_field
    @property
    def health_status(self) -> str:
        """
        Derive a health label from crawl recency AND latest run outcome.

        Order of precedence:
          inactive    — active_flag is False
          no_pipeline — parser_strategy isn't one we ingest yet (only shopify
                        has a pipeline today). Old runs from a previous
                        strategy aren't treated as current failures.
          failing     — last run.status == failed
          degraded    — last run.status == partial (had errors)
          unknown     — never crawled and no run on record
          stale       — last successful crawl older than 2× frequency
          healthy     — recent successful crawl, no errors
        """
        if not self.active_flag:
            return "inactive"

        if self.parser_strategy != "shopify":
            return "no_pipeline"

        if self.last_run is not None:
            if self.last_run.status == "failed":
                return "failing"
            if self.last_run.status == "partial" or self.last_run.error_count > 0:
                return "degraded"

        if self.last_successful_crawl_at is None:
            return "unknown"

        from datetime import timezone
        now = datetime.now(timezone.utc)
        last = self.last_successful_crawl_at
        if last.tzinfo is None:
            from datetime import timezone as tz
            last = last.replace(tzinfo=tz.utc)
        hours_since = (now - last).total_seconds() / 3600
        threshold = self.crawl_frequency_hours * 2
        return "healthy" if hours_since <= threshold else "stale"


class StoreDetail(StoreBase):
    """Full store detail including source pages."""
    source_pages: list[SourcePageSummary] = []


# ─── Import / detection schemas ───────────────────────────────────────────────

class DetectionSignalInfo(BaseModel):
    signal: str
    detail: str | None = None


class StoreDetectionSummary(BaseModel):
    """Returned by rescan endpoint."""
    domain: str
    parser_strategy: str
    reachable: bool
    pages_upserted: int
    signals: list[str]


class ImportReport(BaseModel):
    """Returned by CSV import endpoint."""
    total: int
    inserted: int
    updated: int
    failed: int
    unreachable: int
    strategies: dict[str, int]
    errors: list[dict]


# ─── Paginated list wrapper ───────────────────────────────────────────────────

class PaginatedStores(BaseModel):
    data: list[StoreListItem]
    total: int
    page: int
    page_size: int
    has_next: bool
    filters_applied: dict = Field(default_factory=dict)
