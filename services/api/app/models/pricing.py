"""
ListingVariant and PriceHistory models.

ListingVariant represents one sellable SKU within a listing — a specific
combination of weight, grind type, and pack count with a current price.

PriceHistory is append-only. Every ingestion run appends the current price
for each variant, building a full time series. Rows are never updated or deleted.
The recorded_at timestamp is the ingestion time, not the seller's timestamp.

Design notes:
- price_gbp is stored as a Numeric to avoid float precision errors.
- price_per_100g_gbp is computed on insert and stored for fast sorting.
- seller_variant_id is the stable identifier from the source (Shopify variant ID).
  Used as the upsert key for idempotency.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin
from app.models.enums import GrindType, AvailabilityStatus


class ListingVariant(UUIDMixin, Base):
    """One priceable SKU within a bean listing."""

    __tablename__ = "listing_variants"

    bean_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bean_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Raw variant title from source (e.g. "250g / Espresso")
    variant_title_raw: Mapped[str] = mapped_column(String(300), nullable=False)

    # Parsed / normalised fields
    weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grind_type: Mapped[GrindType] = mapped_column(
        nullable=False, default=GrindType.unknown, index=True
    )
    pack_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Pricing — Numeric(10, 2) for exact decimal storage
    price_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_100g_gbp: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")

    # Availability
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        nullable=False, default=AvailabilityStatus.unknown, index=True
    )

    # Source identifiers for idempotent upserts
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_variant_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Snapshot timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    bean_listing: Mapped["BeanListing"] = relationship(back_populates="variants")  # noqa: F821
    price_history: Mapped[list["PriceHistory"]] = relationship(  # noqa: F821
        back_populates="listing_variant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ListingVariant {self.weight_g}g {self.grind_type} £{self.price_gbp}>"


class PriceHistory(UUIDMixin, Base):
    """
    Append-only price time series for a listing variant.

    Never updated. One row per ingestion run per variant.
    Enables price change alerts and trend analysis.
    """

    __tablename__ = "price_history"

    listing_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listing_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    price_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_100g_gbp: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        nullable=False, default=AvailabilityStatus.unknown
    )

    # When this price was recorded (ingestion time)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    listing_variant: Mapped["ListingVariant"] = relationship(  # noqa: F821
        back_populates="price_history"
    )

    def __repr__(self) -> str:
        return f"<PriceHistory £{self.price_gbp} @ {self.recorded_at}>"
