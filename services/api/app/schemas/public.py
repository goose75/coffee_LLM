"""
Pydantic v2 response schemas for the public-facing API.

These are intentionally more compact than the admin schemas — they expose
only what a consumer-facing site needs, with no internal IDs or audit fields.
"""
from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, ConfigDict, computed_field, Field


# ── Nested objects ─────────────────────────────────────────────────────────────

class PriceVariantPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    weight_g: int | None
    grind_type: str
    price_gbp: float
    price_per_100g_gbp: float | None
    availability_status: str
    sku: str | None


class StoreListingPublic(BaseModel):
    """One store's listing for a given canonical coffee."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    store_name: str = ""      # populated from joined store
    store_domain: str = ""
    store_homepage_url: str = ""
    raw_title: str
    product_url: str | None
    listing_status: str
    active_flag: bool
    variants: list[PriceVariantPublic] = Field(default_factory=list)

    @computed_field
    @property
    def min_price_gbp(self) -> float | None:
        prices = [v.price_gbp for v in self.variants if v.availability_status != "out_of_stock"]
        return min(prices) if prices else None

    @computed_field
    @property
    def max_price_gbp(self) -> float | None:
        prices = [v.price_gbp for v in self.variants]
        return max(prices) if prices else None


# ── Canonical coffee (public-facing) ──────────────────────────────────────────

class CoffeePublic(BaseModel):
    """Canonical coffee for list views (no listings detail)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    origin_country: str | None
    origin_region: str | None
    farm_or_estate: str | None
    washing_station: str | None
    producer: str | None
    varietal: list[str]
    process: str | None
    process_detail: str | None
    altitude_masl_min: int | None
    altitude_masl_max: int | None
    harvest_year: int | None
    roast_level: str | None
    flavour_notes: list[str]
    decaf_flag: bool
    espresso_suitable_flag: bool
    filter_suitable_flag: bool
    data_completeness_score: float

    # Aggregated from listings — set by endpoint logic
    listing_count: int = 0
    store_count: int = 0
    min_price_gbp: float | None = None
    max_price_gbp: float | None = None
    # ISO-8601 timestamp of the most recent listing (used by new-releases feed)
    newest_listing_at: str | None = None


class CoffeeDetailPublic(CoffeePublic):
    """Full coffee with all store listings attached."""
    listings: list[StoreListingPublic] = Field(default_factory=list)


# ── Roaster (public-facing) ───────────────────────────────────────────────────

class RoasterPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str
    homepage_url: str
    uk_region: str | None
    roaster_flag: bool
    cafe_flag: bool
    active_flag: bool
    listing_count: int = 0


# ── Paginated wrappers ────────────────────────────────────────────────────────

class PaginatedCoffees(BaseModel):
    data: list[CoffeePublic]
    total: int
    page: int
    page_size: int
    has_next: bool


class PaginatedRoasters(BaseModel):
    data: list[RoasterPublic]
    total: int
    page: int
    page_size: int
    has_next: bool


# ── Admin canonical bean schemas ──────────────────────────────────────────────

class CanonicalBeanItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    origin_country: str | None
    origin_region: str | None
    farm_or_estate: str | None
    washing_station: str | None
    producer: str | None
    varietal: list[str]
    process: str | None
    process_detail: str | None
    altitude_masl_min: int | None
    altitude_masl_max: int | None
    harvest_year: int | None
    roast_level: str | None
    flavour_notes: list[str]
    decaf_flag: bool
    espresso_suitable_flag: bool
    filter_suitable_flag: bool
    data_completeness_score: float
    created_at: str
    updated_at: str


class CanonicalBeanUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    canonical_name: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    farm_or_estate: str | None = None
    washing_station: str | None = None
    producer: str | None = None
    varietal: list[str] | None = None
    process: str | None = None
    process_detail: str | None = None
    altitude_masl_min: int | None = None
    altitude_masl_max: int | None = None
    harvest_year: int | None = None
    roast_level: str | None = None
    flavour_notes: list[str] | None = None
    decaf_flag: bool | None = None
    espresso_suitable_flag: bool | None = None
    filter_suitable_flag: bool | None = None


class PaginatedBeans(BaseModel):
    data: list[CanonicalBeanItem]
    total: int
    page: int
    page_size: int
    has_next: bool
