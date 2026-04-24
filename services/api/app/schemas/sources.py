"""
Pydantic v2 response schemas for the sources / stores API.

Kept separate from SQLAlchemy models so the API contract can evolve
independently. All datetimes serialised as ISO 8601 strings.
"""

from __future__ import annotations

from datetime import datetime
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


class StoreListItem(StoreBase):
    """Compact representation for table listings."""

    @computed_field
    @property
    def health_status(self) -> str:
        """
        Derive a simple health label from available metadata.
        
        healthy   — active and successfully crawled within 2× crawl frequency
        stale     — active but crawl is overdue
        inactive  — active_flag is False
        unknown   — never crawled
        """
        if not self.active_flag:
            return "inactive"
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
