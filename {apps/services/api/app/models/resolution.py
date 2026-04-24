"""
CanonicalMatch model — entity resolution decisions.
NormalisationMapping model — raw-to-controlled-vocab dictionary.

CanonicalMatch records every attempt to link a bean_listing to a canonical_bean.
The match may be system-generated (auto-accepted above threshold) or pending
human review. Every decision is stored — including rejections — for auditability.

NormalisationMapping is the editable dictionary that maps raw source strings
to controlled vocabulary values. Entries here are applied during the
normalisation pass and can be extended by operators via the admin app.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin, TimestampMixin
from app.models.enums import MatchMethod, ReviewStatus, MappingType


class CanonicalMatch(UUIDMixin, Base):
    """
    A match decision linking a bean_listing to a canonical_bean.

    Lifecycle:
    1. Entity resolution proposes a match with a confidence_score.
    2. If score >= AUTO_ACCEPT threshold → accepted_by_system_flag = True.
    3. If score is in review band → review_status = pending, queued for human.
    4. Human accepts or rejects via admin app.
    5. On accept: bean_listing.canonical_bean_id is updated.
    """

    __tablename__ = "canonical_matches"

    # ── References ─────────────────────────────────────────────────────────
    bean_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bean_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposed_canonical_bean_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_beans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Match decision ─────────────────────────────────────────────────────
    match_method: Mapped[MatchMethod] = mapped_column(nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # System auto-accepted when confidence >= threshold
    accepted_by_system_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── Human review ───────────────────────────────────────────────────────
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        nullable=False, default=ReviewStatus.pending, index=True
    )
    review_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Debug signals (stored for reviewer context) ────────────────────────
    # Stores the per-signal breakdown: exact_score, fuzzy_score, embedding_score
    match_signals: Mapped[dict | None] = mapped_column(
        "match_signals_json",
        type_=None,  # overridden in migration with JSONB
        nullable=True,
    )

    # Relationships
    bean_listing: Mapped["BeanListing"] = relationship(  # noqa: F821
        back_populates="canonical_matches",
        foreign_keys=[bean_listing_id],
    )
    proposed_canonical_bean: Mapped["CanonicalBean"] = relationship(  # noqa: F821
        back_populates="canonical_matches",
        foreign_keys=[proposed_canonical_bean_id],
    )

    def __repr__(self) -> str:
        return (
            f"<CanonicalMatch {self.match_method} "
            f"confidence={self.confidence_score:.2f} "
            f"status={self.review_status}>"
        )


class NormalisationMapping(UUIDMixin, TimestampMixin, Base):
    """
    Raw source string → controlled vocabulary mapping.

    e.g. "Full City" → roast_level: "medium_dark"
         "French Press" → grind_type: "cafetiere"
         "Natural Process" → process: "natural"

    These mappings are applied during the normalisation pass and are
    editable by operators through the admin app's mapping dictionary manager.
    confidence_score represents how certain we are this mapping is correct —
    lower-confidence mappings can be flagged for review.
    """

    __tablename__ = "normalisation_mappings"

    mapping_type: Mapped[MappingType] = mapped_column(nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalised_value: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Source: "manual" (operator-entered) | "llm" (LLM-suggested) | "rule" (pattern-matched)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")

    def __repr__(self) -> str:
        return (
            f"<NormalisationMapping {self.mapping_type}: "
            f"'{self.raw_value}' → '{self.normalised_value}'>"
        )
