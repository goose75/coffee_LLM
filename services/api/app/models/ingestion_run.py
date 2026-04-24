"""
IngestionRun model.

One row per ingestion job execution. Provides a full audit trail of what
was fetched, what changed, and what failed. Used by the admin app's
ingestion monitoring dashboard.

warnings and errors are stored as JSONB arrays. Each entry is a structured
object with a message, optional url, and optional exception detail.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin
from app.models.enums import RunType, RunStatus


class IngestionRun(UUIDMixin, Base):
    """Audit record for a single ingestion job execution."""

    __tablename__ = "ingestion_runs"

    # ── Job classification ─────────────────────────────────────────────────
    run_type: Mapped[RunType] = mapped_column(nullable=False, index=True)

    # Nullable — None means a platform-wide run, not a single-store run.
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Timing ────────────────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Status ────────────────────────────────────────────────────────────
    status: Mapped[RunStatus] = mapped_column(
        nullable=False, default=RunStatus.running, index=True
    )

    # ── Counters ──────────────────────────────────────────────────────────
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Structured logs ───────────────────────────────────────────────────
    # Each entry: {"message": str, "url": str|null, "detail": str|null}
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Relationships
    store: Mapped["Store | None"] = relationship(back_populates="ingestion_runs")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<IngestionRun {self.run_type} "
            f"status={self.status} "
            f"started={self.started_at}>"
        )

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
