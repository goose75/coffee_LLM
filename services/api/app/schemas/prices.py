"""
Pydantic v2 schemas for price intelligence endpoints.

Covers:
  - PricePoint: single recorded price datum for charting
  - VariantHistory: full price history for one listing variant
  - BeanPriceHistory: aggregated history across all variants of a canonical bean
  - SellerComparison: side-by-side current prices across stores
  - MarketStats: min/max/median/average for a bean or market segment
  - MarketAverages: aggregated pricing by origin/process/roast
  - PriceAnomaly: admin-facing anomaly detection result
  - WeightCoverage: admin view of missing/suspicious weights
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ── Atomic price point ─────────────────────────────────────────────────────────

class PricePoint(BaseModel):
    """One observation in a price time series."""
    recorded_at: datetime
    price_gbp: float
    price_per_100g_gbp: float | None
    availability_status: str


# ── Variant-level history ─────────────────────────────────────────────────────

class VariantPriceHistory(BaseModel):
    variant_id: UUID
    variant_title: str
    weight_g: int | None
    grind_type: str
    store_name: str
    store_id: UUID
    history: list[PricePoint] = Field(default_factory=list)

    @computed_field
    @property
    def latest_price_gbp(self) -> float | None:
        return self.history[-1].price_gbp if self.history else None

    @computed_field
    @property
    def price_change_7d(self) -> float | None:
        """Absolute GBP change over the last 7 days, or None if insufficient data."""
        if len(self.history) < 2:
            return None
        from datetime import timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        # Find the most recent point before the cutoff
        older = [p for p in self.history if p.recorded_at <= cutoff]
        if not older:
            return None
        delta = self.history[-1].price_gbp - older[-1].price_gbp
        return round(delta, 2)


# ── Bean-level aggregated history ─────────────────────────────────────────────

class BeanPriceHistory(BaseModel):
    """Price history for a canonical bean, grouped by variant."""
    bean_id: UUID
    canonical_name: str
    variants: list[VariantPriceHistory] = Field(default_factory=list)

    @computed_field
    @property
    def min_current_price_gbp(self) -> float | None:
        prices = [v.latest_price_gbp for v in self.variants if v.latest_price_gbp is not None]
        return min(prices) if prices else None


# ── Cross-store comparison ─────────────────────────────────────────────────────

class VariantOffer(BaseModel):
    """A specific weight/grind offer at a specific price."""
    variant_id: UUID
    variant_title: str
    weight_g: int | None
    grind_type: str
    price_gbp: float
    price_per_100g_gbp: float | None
    availability_status: str
    product_url: str | None


class SellerListing(BaseModel):
    """One store's current offering of a canonical bean."""
    store_id: UUID
    store_name: str
    store_domain: str
    store_homepage_url: str
    offers: list[VariantOffer] = Field(default_factory=list)

    @computed_field
    @property
    def min_price_gbp(self) -> float | None:
        prices = [o.price_gbp for o in self.offers if o.availability_status != "out_of_stock"]
        return min(prices) if prices else None

    @computed_field
    @property
    def cheapest_per_100g(self) -> float | None:
        p100 = [o.price_per_100g_gbp for o in self.offers
                if o.price_per_100g_gbp is not None and o.availability_status != "out_of_stock"]
        return min(p100) if p100 else None


class SellerComparison(BaseModel):
    """Cross-store price comparison for a canonical bean."""
    bean_id: UUID
    canonical_name: str
    stores: list[SellerListing] = Field(default_factory=list)

    @computed_field
    @property
    def best_price_gbp(self) -> float | None:
        prices = [s.min_price_gbp for s in self.stores if s.min_price_gbp is not None]
        return min(prices) if prices else None

    @computed_field
    @property
    def best_price_per_100g(self) -> float | None:
        p100 = [s.cheapest_per_100g for s in self.stores if s.cheapest_per_100g is not None]
        return min(p100) if p100 else None


# ── Market statistics ─────────────────────────────────────────────────────────

class PriceSummaryStats(BaseModel):
    """Min/max/median/mean across a set of prices."""
    weight_g: int | None = None      # None = aggregated across all weights
    sample_count: int = 0
    min_price_gbp: float | None = None
    max_price_gbp: float | None = None
    median_price_gbp: float | None = None
    mean_price_gbp: float | None = None
    min_per_100g: float | None = None
    max_per_100g: float | None = None
    median_per_100g: float | None = None


class MarketAverageRow(BaseModel):
    """Average pricing for a market segment."""
    dimension: str          # e.g. "Ethiopia", "washed", "light"
    dimension_type: str     # "origin_country" | "process" | "roast_level" | "store"
    bean_count: int
    sample_count: int
    mean_price_gbp: float | None
    mean_per_100g: float | None
    median_per_100g: float | None


class MarketAverages(BaseModel):
    """Market-wide pricing summary by dimension."""
    dimension_type: str
    weight_g_filter: int | None   # e.g. 250 — only 250g variants considered
    rows: list[MarketAverageRow] = Field(default_factory=list)


# ── Admin anomaly and coverage views ─────────────────────────────────────────

class PriceChangeEvent(BaseModel):
    """A detected price change on a single variant."""
    variant_id: UUID
    bean_id: UUID | None
    bean_name: str
    store_name: str
    weight_g: int | None
    grind_type: str
    old_price_gbp: float
    new_price_gbp: float
    change_gbp: float
    change_pct: float
    old_per_100g: float | None
    new_per_100g: float | None
    recorded_at: datetime

    @computed_field
    @property
    def direction(self) -> str:
        return "up" if self.change_gbp > 0 else "down"


class PriceAnomaly(BaseModel):
    """A variant whose price looks suspicious."""
    variant_id: UUID
    bean_id: UUID | None
    bean_name: str
    store_name: str
    weight_g: int | None
    grind_type: str
    price_gbp: float
    price_per_100g_gbp: float | None
    reason: str             # human-readable explanation
    severity: str           # "low" | "medium" | "high"
    recorded_at: datetime


class WeightCoverageRow(BaseModel):
    """Admin view of a variant's weight status."""
    variant_id: UUID
    bean_id: UUID | None
    bean_name: str
    store_name: str
    variant_title: str
    weight_g: int | None
    price_gbp: float
    price_per_100g_gbp: float | None
    issue: str              # "missing_weight" | "suspicious_weight" | "no_per_100g"
