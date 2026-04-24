"""
ORM models for entity resolution and normalisation mappings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class CanonicalMatch(UUIDMixin, Base):
    """
    Records a proposed or confirmed match between a bean_listing and a canonical_bean.
    Confidence-band routing:
      >= 0.92  → auto-accepted
      0.75-0.91 → review queue
      < 0.75   → new canonical candidate
    """

    __tablename__ = "canonical_matches"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bean_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_bean_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_beans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_method: Mapped[str] = mapped_column(String(50), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # Signal breakdown stored as JSON — fix: use JSON not dict
    match_signals_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    listing = relationship("BeanListing", back_populates="canonical_matches")
    canonical_bean = relationship("CanonicalBean", back_populates="canonical_matches")

    __table_args__ = (
        Index("ix_canonical_matches_review_status", "review_status"),
        Index("ix_canonical_matches_confidence", "confidence_score"),
    )


class NormalisationMapping(UUIDMixin, Base):
    """
    Operator-curated mapping from raw source text to controlled vocabulary values.
    DB lookups take priority over rule-based matching in CoffeeNormaliser.
    """

    __tablename__ = "normalisation_mappings"

    mapping_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalised_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_normalisation_mappings_type_raw",
            "mapping_type",
            "raw_value",
            unique=True,
        ),
    )
