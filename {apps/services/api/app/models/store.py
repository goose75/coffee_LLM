"""
Store model.

A store is any UK seller or roaster we track. One domain = one store.
Stores can be roasters, cafes, or pure ecommerce retailers.
The source_type and parser_strategy fields drive ingestion routing.
"""

from sqlalchemy import Boolean, Integer, String, Text
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
    last_successful_crawl_at: Mapped[str | None] = mapped_column(nullable=True)

    # Relationships
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
