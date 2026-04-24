"""Pydantic v2 schemas for ingestion run API responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class IngestionRunItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_type: str
    store_id: UUID | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    records_seen: int
    records_created: int
    records_updated: int
    records_unchanged: int
    pages_fetched: int
    pages_failed: int
    warnings: list[dict]
    errors: list[dict]

    @computed_field
    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at and self.started_at:
            return round((self.completed_at - self.started_at).total_seconds(), 1)
        return None

    @computed_field
    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @computed_field
    @property
    def error_count(self) -> int:
        return len(self.errors)


class PaginatedIngestionRuns(BaseModel):
    data: list[IngestionRunItem]
    total: int
    page: int
    page_size: int
    has_next: bool
