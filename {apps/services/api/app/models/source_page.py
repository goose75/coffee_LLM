"""
SourcePage model.

One row per URL or feed endpoint fetched during ingestion.
content_hash drives change detection — if hash is unchanged, we skip reprocessing.
raw_storage_path points to the object in S3 or local storage.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDMixin
from app.models.enums import PageType, ParserStrategy
from sqlalchemy import DateTime


class SourcePage(UUIDMixin, Base):
    """A fetched URL belonging to a store."""

    __tablename__ = "source_pages"

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[PageType] = mapped_column(nullable=False, default=PageType.product)
    parser_strategy: Mapped[ParserStrategy] = mapped_column(
        nullable=False, default=ParserStrategy.unknown
    )

    # Fetch metadata
    discovered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_fetched_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Change detection
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Object storage
    raw_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    store: Mapped["Store"] = relationship(back_populates="source_pages")  # noqa: F821
    raw_extractions: Mapped[list["RawExtraction"]] = relationship(  # noqa: F821
        back_populates="source_page", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SourcePage {self.url[:60]}>"
