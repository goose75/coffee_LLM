"""
CanonicalBean model.

The canonical bean is the underlying coffee identity — what the coffee IS,
independent of who sells it or what they call it. A single canonical bean
can have many listings across different stores.

The embedding_vector column stores a dense vector for semantic similarity
matching via pgvector. It's generated from a concatenation of key descriptive
fields: origin, process, varietal, flavour notes, and canonical_name.

Design notes:
- Normalised fields use controlled vocab enums.
- Arrays (varietal, flavour_notes) use PostgreSQL native ARRAY type.
- All text fields are nullable — we may know origin but not varietal.
- harvest_year is stored as an integer (e.g. 2024).
- Altitude stored as a range (min/max) since most sources give a range.
"""

from sqlalchemy import Boolean, Float, Integer, String, Text, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.mixins import UUIDMixin, TimestampMixin
from app.models.enums import RoastLevel, Process


class CanonicalBean(UUIDMixin, TimestampMixin, Base):
    """The deduplicated, normalised identity of a coffee."""

    __tablename__ = "canonical_beans"

    # ── Core identity ──────────────────────────────────────────────────────
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # ── Origin ────────────────────────────────────────────────────────────
    origin_country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    origin_region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    farm_or_estate: Mapped[str | None] = mapped_column(String(300), nullable=True)
    washing_station: Mapped[str | None] = mapped_column(String(300), nullable=True)
    producer: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ── Cultivar & Processing ─────────────────────────────────────────────
    varietal: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=list)
    process: Mapped[Process | None] = mapped_column(nullable=True, index=True)
    process_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Altitude ──────────────────────────────────────────────────────────
    altitude_masl_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altitude_masl_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Harvest & Roast ───────────────────────────────────────────────────
    harvest_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    roast_level: Mapped[RoastLevel | None] = mapped_column(nullable=True, index=True)

    # ── Sensory ───────────────────────────────────────────────────────────
    flavour_notes: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list
    )

    # ── Brew suitability ──────────────────────────────────────────────────
    decaf_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    espresso_suitable_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_suitable_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Semantic embedding (pgvector) ─────────────────────────────────────
    # Dimensionality matches EMBEDDING_DIMENSIONS in settings (default 1536).
    # Index created separately in migration as IVFFlat for approximate search.
    embedding_vector: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )

    # ── Quality score ─────────────────────────────────────────────────────
    # Completeness proxy: 0.0–1.0, computed on write.
    data_completeness_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Relationships
    bean_listings: Mapped[list["BeanListing"]] = relationship(  # noqa: F821
        back_populates="canonical_bean"
    )
    canonical_matches: Mapped[list["CanonicalMatch"]] = relationship(  # noqa: F821
        back_populates="proposed_canonical_bean",
        foreign_keys="CanonicalMatch.proposed_canonical_bean_id",
    )
    flavour_tags: Mapped[list["BeanFlavourTag"]] = relationship(  # noqa: F821
        back_populates="bean",
        foreign_keys="BeanFlavourTag.bean_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CanonicalBean '{self.canonical_name}'>"

    def compute_completeness(self) -> float:
        """Return a 0–1 score based on how many key fields are populated."""
        fields = [
            self.origin_country,
            self.origin_region,
            self.farm_or_estate,
            self.producer,
            bool(self.varietal),
            self.process,
            self.harvest_year,
            self.roast_level,
            bool(self.flavour_notes),
            self.altitude_masl_min,
        ]
        filled = sum(1 for f in fields if f is not None and f is not False)
        return round(filled / len(fields), 2)
