"""
RawExtraction model.

Stores the direct output of any extraction pass (Shopify JSON, schema.org,
HTML rules, or LLM) before normalisation. Preserves full lineage.

Every extraction carries:
- which method produced it
- the raw structured payload as JSONB
- a confidence score (0–1)
- a validation status

The payload must conform to ExtractionPayload from shared-types.
LLM extractions additionally record model_name and prompt_version.
"""

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin, CreatedAtMixin
from app.models.enums import ExtractionMethod, ValidationStatus


class RawExtraction(UUIDMixin, CreatedAtMixin, Base):
    """Structured output from a single extraction pass."""

    __tablename__ = "raw_extractions"

    source_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provenance
    extraction_method: Mapped[ExtractionMethod] = mapped_column(nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Output
    extracted_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        nullable=False, default=ValidationStatus.valid, index=True
    )
    validation_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    source_page: Mapped["SourcePage"] = relationship(  # noqa: F821
        back_populates="raw_extractions"
    )

    def __repr__(self) -> str:
        return f"<RawExtraction {self.extraction_method} confidence={self.confidence_score:.2f}>"
