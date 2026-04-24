"""
BeanListing model.

A listing is how a specific store presents and sells a coffee. One canonical
bean can be represented by many listings across different stores.

The link to canonical_bean_id is nullable — new listings start unlinked and
are resolved by the entity resolution service (Phase 4).

Raw label fields preserve the exact text from the source, alongside any
normalised values derived from them. Never overwrite raw values.

content_hash is computed over the listing's key descriptive fields, enabling
change detection without refetching the full page.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin
from app.models.enums import ListingStatus


class BeanListing(UUIDMixin, Base):
    """A seller's specific product page for a coffee."""

    __tablename__ = "bean_listings"

    # ── Foreign keys ──────────────────────────────────────────────────────
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_bean_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_beans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Raw source fields (never modified after ingestion) ────────────────
    raw_title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw label text preserved alongside normalised values
    roast_label_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    process_label_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origin_label_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)
    varietal_label_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Seller's own product handle / slug (used as stable identifier for Shopify)
    seller_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Status ────────────────────────────────────────────────────────────
    listing_status: Mapped[ListingStatus] = mapped_column(
        nullable=False, default=ListingStatus.active, index=True
    )
    active_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # ── Temporal tracking ─────────────────────────────────────────────────
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Change detection ──────────────────────────────────────────────────
    # SHA-256 over (title + description + all variant prices).
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    store: Mapped["Store"] = relationship(back_populates="bean_listings")  # noqa: F821
    canonical_bean: Mapped["CanonicalBean | None"] = relationship(  # noqa: F821
        back_populates="bean_listings"
    )
    variants: Mapped[list["ListingVariant"]] = relationship(  # noqa: F821
        back_populates="bean_listing", cascade="all, delete-orphan"
    )
    canonical_matches: Mapped[list["CanonicalMatch"]] = relationship(  # noqa: F821
        back_populates="bean_listing",
        foreign_keys="CanonicalMatch.bean_listing_id",
    )

    def __repr__(self) -> str:
        return f"<BeanListing '{self.raw_title[:50]}'>"
