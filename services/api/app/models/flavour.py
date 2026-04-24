"""
Flavour taxonomy and bean-level taste tag models.

FlavourTaxonomy: controlled vocabulary tree
  depth 0 → family  (e.g. "Fruity")
  depth 1 → category (e.g. "Citrus")
  depth 2 → tag      (e.g. "Lemon")

BeanFlavourTag: the M2M join with confidence + audit data
  - raw_note   : the exact string from the source (never modified)
  - confidence : 0–1 from the normalisation source
  - source     : 'rule' | 'llm' | 'manual'
  - review_status : mirrors canonical_matches workflow
  - llm_audit  : full LLM JSON stored for traceability
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy import ARRAY as SA_ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin
from app.models.enums import ReviewStatus


class FlavourTaxonomy(UUIDMixin, Base):
    """
    A node in the three-level flavour vocabulary tree.

    depth 0 = family   (Fruity, Floral, Sweet, Chocolate, Nutty, Spice, Earthy, Fermented)
    depth 1 = category (Citrus, Berry, Tropical, ...)
    depth 2 = tag      (Lemon, Raspberry, Mango, ...)
    """

    __tablename__ = "flavour_taxonomy"

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flavour_taxonomy.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Wheel visualisation colour (CSS hex e.g. "#c4763a")
    colour: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # Known raw-text synonyms for rule-based matching
    synonyms: Mapped[list[str]] = mapped_column(
        SA_ARRAY(String(100)), nullable=False, default=list
    )

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    parent: Mapped["FlavourTaxonomy | None"] = relationship(
        "FlavourTaxonomy",
        remote_side="FlavourTaxonomy.id",
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list["FlavourTaxonomy"]] = relationship(
        "FlavourTaxonomy",
        back_populates="parent",
        foreign_keys=[parent_id],
        cascade="all, delete-orphan",
    )
    bean_tags: Mapped[list["BeanFlavourTag"]] = relationship(
        back_populates="taxonomy_node",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FlavourTaxonomy depth={self.depth} '{self.slug}'>"

    @property
    def family_slug(self) -> str:
        """Return the top-level family slug (first segment of dot-separated slug)."""
        return self.slug.split(".")[0]


class BeanFlavourTag(UUIDMixin, Base):
    """
    A single normalised flavour tag linked to a canonical bean.

    One raw_note can produce at most one tag per taxonomy node
    (enforced by unique index on bean_id + taxonomy_id + raw_note).
    """

    __tablename__ = "bean_flavour_tags"

    bean_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_beans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flavour_taxonomy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Preserved verbatim — the original text that triggered this mapping
    raw_note: Mapped[str] = mapped_column(String(200), nullable=False)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # 'rule' | 'llm' | 'manual'
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="rule")

    review_status: Mapped[ReviewStatus] = mapped_column(
        nullable=False, default=ReviewStatus.accepted, index=True
    )

    # Full LLM response for audit / explainability; None for rule-based
    llm_audit: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    bean: Mapped["CanonicalBean"] = relationship(  # noqa: F821
        back_populates="flavour_tags",
        foreign_keys=[bean_id],
    )
    taxonomy_node: Mapped[FlavourTaxonomy] = relationship(
        back_populates="bean_tags",
        foreign_keys=[taxonomy_id],
    )

    def __repr__(self) -> str:
        return f"<BeanFlavourTag '{self.raw_note}' → {self.taxonomy_id} conf={self.confidence:.2f}>"
