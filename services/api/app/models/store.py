"""
Store model — fixed version.

Fixes:
  1. last_successful_crawl_at: VARCHAR → DateTime(timezone=True)
  2. Added ingestion_runs relationship to match IngestionRun.back_populates="ingestion_runs"
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin, TimestampMixin
from app.models.enums import SourceType, ParserStrategy


class Store(UUIDMixin, TimestampMixin, Base):
    """A coffee seller or roaster."""

    __tablename__ = "stores"

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    homepage_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    source_type: Mapped[SourceType] = mapped_column(nullable=False, default=SourceType.html)
    parser_strategy: Mapped[ParserStrategy] = mapped_column(
        nullable=False, default=ParserStrategy.unknown
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="GB")
    uk_region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Flags
    roaster_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cafe_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ecommerce_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Crawl metadata
    crawl_frequency_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)

    # FIXED: was Mapped[str | None] with no column type → stored as VARCHAR
    # Scheduler does timestamp arithmetic against this column; must be DateTime
    last_successful_crawl_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships — all three must match back_populates in the related models
    source_pages: Mapped[list["SourcePage"]] = relationship(  # noqa: F821
        back_populates="store", cascade="all, delete-orphan"
    )
    bean_listings: Mapped[list["BeanListing"]] = relationship(  # noqa: F821
        back_populates="store"
    )
    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(  # noqa: F821
        back_populates="store"
    )

    def __repr__(self) -> str:
        return f"<Store {self.domain}>"
