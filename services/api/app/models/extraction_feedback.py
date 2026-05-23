"""
Extraction feedback model — stores quality signals for continuous LLM improvement.

This table collects feedback on extractions from multiple sources:
1. Manual spot-checks (admin UI: rate extraction as correct/partial/wrong)
2. Price validation (flag suspicious price changes over time)
3. Duplicate detection (flag similar products with mismatched extractions)
4. A/B testing (compare prompt versions on same page)

Used to:
- Calibrate confidence scores (does claimed confidence match actual accuracy?)
- Identify systematic failures (which domains/patterns cause low quality?)
- Drive prompt iteration (which improvements actually help?)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Text, DateTime, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExtractionFeedback(Base):
    """
    Feedback signal on an extraction quality.

    One row per feedback event: manual rating, price anomaly, or duplicate detection.
    """

    __tablename__ = "extraction_feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=lambda: __import__("uuid").uuid4())

    # ── Link to extraction ────────────────────────────────────────────────
    raw_extraction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_extractions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Feedback type ────────────────────────────────────────────────────
    feedback_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        # "manual_review" | "price_anomaly" | "duplicate_mismatch" | "ab_test"
    )

    # ── Manual review (if feedback_type == 'manual_review') ──────────────
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        # "correct" | "partial" | "wrong" | null for non-manual feedback
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Price validation (if feedback_type == 'price_anomaly') ──────────
    price_previous_gbp: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_current_gbp: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_jump_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    # jump_factor = current / previous; >1.5 or <0.67 is anomalous

    # ── Duplicate detection (if feedback_type == 'duplicate_mismatch') ───
    matching_listing_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bean_listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Other domain that has seemingly same coffee with different extraction

    # ── A/B testing (if feedback_type == 'ab_test') ─────────────────────
    prompt_version_a: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prompt_version_b: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    winner: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "a" | "b" | "tie"

    # ── Metadata ──────────────────────────────────────────────────────────
    signal_strength: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        # 0.0–1.0: confidence in this feedback signal (1.0 = very reliable)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_feedback_type_created", "feedback_type", "created_at"),
        Index("idx_feedback_extraction_rating", "raw_extraction_id", "rating"),
    )

    def __repr__(self) -> str:
        return f"<ExtractionFeedback {self.id} type={self.feedback_type} rating={self.rating}>"
