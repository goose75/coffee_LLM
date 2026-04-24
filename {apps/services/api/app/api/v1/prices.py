"""
Price intelligence API router.

Public endpoints (mounted under /api/v1):
  GET /coffees/{id}/price-history   — time series per variant
  GET /coffees/{id}/price-compare   — cross-store comparison at current prices
  GET /coffees/{id}/price-stats     — min/max/median summary cards
  GET /market/averages              — aggregated market pricing by dimension

Admin endpoints (mounted under /api/v1/admin):
  GET /prices/recent-changes        — variants with price changes in N days
  GET /prices/anomalies             — suspected price anomalies
  GET /prices/weight-coverage       — variants missing weight_g or price_per_100g

All monetary values are GBP stored as Numeric(10,2) in the DB; returned as float.
Price-per-100g is always recomputed from the stored weight and price to keep it
consistent — never blindly trusted from the stored column alone.
"""
from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.pricing import ListingVariant, PriceHistory
from app.models.store import Store
from app.schemas.prices import (
    BeanPriceHistory,
    MarketAverageRow,
    MarketAverages,
    PriceAnomaly,
    PriceChangeEvent,
    PriceSummaryStats,
    SellerComparison,
    SellerListing,
    VariantOffer,
    VariantPriceHistory,
    WeightCoverageRow,
    PricePoint,
)

public_router = APIRouter()
admin_router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _p100(price_gbp: float, weight_g: int | None) -> float | None:
    if weight_g and weight_g > 0:
        return round(price_gbp / weight_g * 100, 4)
    return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 2)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 2)


# ── Public: price history ──────────────────────────────────────────────────────

@public_router.get("/coffees/{coffee_id}/price-history", response_model=BeanPriceHistory)
async def get_price_history(
    coffee_id: str,
    days: int = Query(90, ge=7, le=730, description="Look-back window in days"),
    weight_g: int | None = Query(None, description="Filter to a specific weight (grams)"),
    db: AsyncSession = Depends(get_db),
) -> BeanPriceHistory:
    """
    Price history for all variants of a canonical bean.

    Returns one VariantPriceHistory per listing_variant, each containing a
    chronological list of PricePoints. The client can use this to draw a
    per-store, per-weight time series chart.
    """
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Coffee not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Fetch all variants for this bean (through bean_listings)
    variants_stmt = (
        select(ListingVariant, BeanListing, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(
            BeanListing.canonical_bean_id == bean_uuid,
            BeanListing.active_flag.is_(True),
        )
    )
    if weight_g is not None:
        variants_stmt = variants_stmt.where(ListingVariant.weight_g == weight_g)

    variant_rows = (await db.execute(variants_stmt)).all()

    # Fetch price history for all these variants in one query
    if not variant_rows:
        return BeanPriceHistory(bean_id=bean.id, canonical_name=bean.canonical_name)

    variant_ids = [row.ListingVariant.id for row in variant_rows]
    history_rows = (await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.listing_variant_id.in_(variant_ids),
            PriceHistory.recorded_at >= cutoff,
        )
        .order_by(PriceHistory.listing_variant_id, PriceHistory.recorded_at)
    )).scalars().all()

    # Group history by variant_id
    history_map: dict[uuid.UUID, list[PricePoint]] = {}
    for ph in history_rows:
        vid = ph.listing_variant_id
        if vid not in history_map:
            history_map[vid] = []
        history_map[vid].append(PricePoint(
            recorded_at=ph.recorded_at,
            price_gbp=float(ph.price_gbp),
            price_per_100g_gbp=float(ph.price_per_100g_gbp) if ph.price_per_100g_gbp else None,
            availability_status=_enum_val(ph.availability_status),
        ))

    variants_out: list[VariantPriceHistory] = []
    for row in variant_rows:
        v = row.ListingVariant
        bl = row.BeanListing
        st = row.Store
        history = history_map.get(v.id, [])
        # If no history entries, synthesise one from current listing_variant price
        if not history:
            history = [PricePoint(
                recorded_at=v.recorded_at,
                price_gbp=float(v.price_gbp),
                price_per_100g_gbp=_p100(float(v.price_gbp), v.weight_g),
                availability_status=_enum_val(v.availability_status),
            )]
        variants_out.append(VariantPriceHistory(
            variant_id=v.id,
            variant_title=v.variant_title_raw,
            weight_g=v.weight_g,
            grind_type=_enum_val(v.grind_type),
            store_name=st.name,
            store_id=st.id,
            history=history,
        ))

    return BeanPriceHistory(
        bean_id=bean.id,
        canonical_name=bean.canonical_name,
        variants=variants_out,
    )


# ── Public: cross-store comparison ────────────────────────────────────────────

@public_router.get("/coffees/{coffee_id}/price-compare", response_model=SellerComparison)
async def get_price_compare(
    coffee_id: str,
    weight_g: int | None = Query(None, description="Normalise comparison to a specific weight"),
    db: AsyncSession = Depends(get_db),
) -> SellerComparison:
    """
    Current prices for a canonical bean across all stores.

    When weight_g is specified, only variants of that weight are returned so
    the comparison is apples-to-apples. Without it, all variants are shown
    grouped by store.
    """
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Coffee not found")

    variants_stmt = (
        select(ListingVariant, BeanListing, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(
            BeanListing.canonical_bean_id == bean_uuid,
            BeanListing.active_flag.is_(True),
        )
        .order_by(Store.name, ListingVariant.weight_g.nullslast(), ListingVariant.grind_type)
    )
    if weight_g is not None:
        variants_stmt = variants_stmt.where(ListingVariant.weight_g == weight_g)

    rows = (await db.execute(variants_stmt)).all()

    # Group by store
    store_map: dict[uuid.UUID, SellerListing] = {}
    for row in rows:
        v = row.ListingVariant
        bl = row.BeanListing
        st = row.Store
        if st.id not in store_map:
            store_map[st.id] = SellerListing(
                store_id=st.id,
                store_name=st.name,
                store_domain=st.domain,
                store_homepage_url=st.homepage_url,
            )
        price = float(v.price_gbp)
        p100 = _p100(price, v.weight_g)
        store_map[st.id].offers.append(VariantOffer(
            variant_id=v.id,
            variant_title=v.variant_title_raw,
            weight_g=v.weight_g,
            grind_type=_enum_val(v.grind_type),
            price_gbp=price,
            price_per_100g_gbp=p100,
            availability_status=_enum_val(v.availability_status),
            product_url=bl.product_url,
        ))

    # Sort stores cheapest first
    stores = sorted(store_map.values(), key=lambda s: (s.min_price_gbp or 9999, s.store_name))

    return SellerComparison(
        bean_id=bean.id,
        canonical_name=bean.canonical_name,
        stores=stores,
    )


# ── Public: price stats ────────────────────────────────────────────────────────

@public_router.get("/coffees/{coffee_id}/price-stats", response_model=list[PriceSummaryStats])
async def get_price_stats(
    coffee_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[PriceSummaryStats]:
    """
    Min/max/median pricing stats broken down by weight for a canonical bean.

    Returns one PriceSummaryStats row per distinct weight available.
    The client renders these as summary cards (cheapest, median, premium).
    """
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Coffee not found")

    rows = (await db.execute(
        select(ListingVariant)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .where(
            BeanListing.canonical_bean_id == bean_uuid,
            BeanListing.active_flag.is_(True),
        )
    )).scalars().all()

    if not rows:
        return []

    # Group by weight_g
    by_weight: dict[int | None, list[ListingVariant]] = {}
    for v in rows:
        key = v.weight_g
        by_weight.setdefault(key, []).append(v)

    stats: list[PriceSummaryStats] = []
    # Sort by weight ascending; None last
    for wg in sorted(by_weight.keys(), key=lambda x: (x is None, x or 0)):
        variants = by_weight[wg]
        prices = [float(v.price_gbp) for v in variants]
        avail_prices = [float(v.price_gbp) for v in variants if _enum_val(v.availability_status) != "out_of_stock"]
        p100_list = [_p100(float(v.price_gbp), v.weight_g) for v in variants]
        p100_list = [p for p in p100_list if p is not None]
        avail_p100 = [_p100(float(v.price_gbp), v.weight_g) for v in variants
                      if _enum_val(v.availability_status) != "out_of_stock" and v.weight_g]
        avail_p100 = [p for p in avail_p100 if p is not None]

        stats.append(PriceSummaryStats(
            weight_g=wg,
            sample_count=len(variants),
            min_price_gbp=min(avail_prices) if avail_prices else None,
            max_price_gbp=max(prices) if prices else None,
            median_price_gbp=_median(avail_prices),
            mean_price_gbp=_mean(avail_prices),
            min_per_100g=min(avail_p100) if avail_p100 else None,
            max_per_100g=max(p100_list) if p100_list else None,
            median_per_100g=_median(avail_p100),
        ))

    return stats


# ── Public: market averages ───────────────────────────────────────────────────

@public_router.get("/market/averages", response_model=MarketAverages)
async def get_market_averages(
    dimension: str = Query("origin_country", description="origin_country | process | roast_level | store"),
    weight_g: int = Query(250, ge=50, le=5000, description="Normalise to this weight"),
    db: AsyncSession = Depends(get_db),
) -> MarketAverages:
    """
    Average pricing across the market, segmented by dimension.

    Only considers variants at (or very near) the specified weight.
    Useful for showing 'Ethiopia 250g averages £12.80/100g'.
    """
    VALID_DIMS = {"origin_country", "process", "roast_level", "store"}
    if dimension not in VALID_DIMS:
        raise HTTPException(status_code=422, detail=f"dimension must be one of {sorted(VALID_DIMS)}")

    # Weight tolerance: ±10%
    wmin = int(weight_g * 0.90)
    wmax = int(weight_g * 1.10)

    rows = (await db.execute(
        select(ListingVariant, BeanListing, CanonicalBean, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .join(CanonicalBean, BeanListing.canonical_bean_id == CanonicalBean.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(
            BeanListing.active_flag.is_(True),
            ListingVariant.weight_g >= wmin,
            ListingVariant.weight_g <= wmax,
        )
    )).all()

    if not rows:
        return MarketAverages(dimension_type=dimension, weight_g_filter=weight_g)

    # Group by dimension value
    groups: dict[str, list[tuple[float, float | None, uuid.UUID]]] = {}
    for row in rows:
        v = row.ListingVariant
        bl = row.BeanListing
        cb = row.CanonicalBean
        st = row.Store

        if dimension == "origin_country":
            key = cb.origin_country or "Unknown"
        elif dimension == "process":
            key = _enum_val(cb.process) if cb.process else "unknown"
        elif dimension == "roast_level":
            key = _enum_val(cb.roast_level) if cb.roast_level else "unknown"
        else:  # store
            key = st.name

        price = float(v.price_gbp)
        p100 = _p100(price, v.weight_g)
        groups.setdefault(key, []).append((price, p100, cb.id))

    result_rows: list[MarketAverageRow] = []
    for dim_val, entries in sorted(groups.items()):
        prices = [e[0] for e in entries]
        p100_vals = [e[1] for e in entries if e[1] is not None]
        bean_ids = {e[2] for e in entries}

        result_rows.append(MarketAverageRow(
            dimension=dim_val,
            dimension_type=dimension,
            bean_count=len(bean_ids),
            sample_count=len(entries),
            mean_price_gbp=_mean(prices),
            mean_per_100g=_mean(p100_vals),
            median_per_100g=_median(p100_vals),
        ))

    # Sort by mean_per_100g ascending (cheapest dimension first)
    result_rows.sort(key=lambda r: (r.median_per_100g or 9999))

    return MarketAverages(
        dimension_type=dimension,
        weight_g_filter=weight_g,
        rows=result_rows,
    )


# ── Admin: recent price changes ───────────────────────────────────────────────

@admin_router.get("/prices/recent-changes", response_model=list[PriceChangeEvent])
async def get_recent_changes(
    days: int = Query(7, ge=1, le=90),
    min_change_pct: float = Query(2.0, ge=0.1, description="Only return changes above this % threshold"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[PriceChangeEvent]:
    """
    Variants whose price changed within the last N days.

    Compares the most recent price_history entry against the one immediately
    before it. Returns changes above the min_change_pct threshold.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all variants that have recent history
    recent_history = (await db.execute(
        select(PriceHistory)
        .where(PriceHistory.recorded_at >= cutoff)
        .order_by(PriceHistory.listing_variant_id, PriceHistory.recorded_at.desc())
    )).scalars().all()

    # Group by variant
    by_variant: dict[uuid.UUID, list[PriceHistory]] = {}
    for ph in recent_history:
        by_variant.setdefault(ph.listing_variant_id, []).append(ph)

    if not by_variant:
        return []

    # For each variant with recent history, fetch one earlier point
    variant_ids = list(by_variant.keys())
    all_history = (await db.execute(
        select(PriceHistory)
        .where(PriceHistory.listing_variant_id.in_(variant_ids))
        .order_by(PriceHistory.listing_variant_id, PriceHistory.recorded_at)
    )).scalars().all()

    all_by_variant: dict[uuid.UUID, list[PriceHistory]] = {}
    for ph in all_history:
        all_by_variant.setdefault(ph.listing_variant_id, []).append(ph)

    # Fetch variant metadata
    variants_meta = (await db.execute(
        select(ListingVariant, BeanListing, CanonicalBean, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .outerjoin(CanonicalBean, BeanListing.canonical_bean_id == CanonicalBean.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(ListingVariant.id.in_(variant_ids))
    )).all()
    meta_map = {row.ListingVariant.id: row for row in variants_meta}

    events: list[PriceChangeEvent] = []
    for vid, history in all_by_variant.items():
        if len(history) < 2:
            continue
        new_entry = history[-1]
        old_entry = history[-2]
        new_price = float(new_entry.price_gbp)
        old_price = float(old_entry.price_gbp)
        if old_price == 0:
            continue
        change = new_price - old_price
        change_pct = abs(change / old_price) * 100
        if change_pct < min_change_pct:
            continue

        meta = meta_map.get(vid)
        if meta is None:
            continue
        v = meta.ListingVariant
        bl = meta.BeanListing
        cb = meta.CanonicalBean
        st = meta.Store

        events.append(PriceChangeEvent(
            variant_id=v.id,
            bean_id=cb.id if cb else None,
            bean_name=cb.canonical_name if cb else bl.raw_title,
            store_name=st.name,
            weight_g=v.weight_g,
            grind_type=_enum_val(v.grind_type),
            old_price_gbp=old_price,
            new_price_gbp=new_price,
            change_gbp=round(change, 2),
            change_pct=round(change_pct, 1),
            old_per_100g=_p100(old_price, v.weight_g),
            new_per_100g=_p100(new_price, v.weight_g),
            recorded_at=new_entry.recorded_at,
        ))

    # Sort by largest % change first
    events.sort(key=lambda e: abs(e.change_pct), reverse=True)
    return events[:limit]


# ── Admin: anomaly detection ───────────────────────────────────────────────────

@admin_router.get("/prices/anomalies", response_model=list[PriceAnomaly])
async def get_price_anomalies(
    db: AsyncSession = Depends(get_db),
) -> list[PriceAnomaly]:
    """
    Variants with potentially anomalous prices.

    Rules applied:
    1. Price per 100g > £20 (very expensive for specialty coffee)
    2. Price per 100g < £0.50 (implausibly cheap)
    3. Price > £200 (likely data error)
    4. Same canonical bean with price > 3× the median across stores
    5. Price per 100g increases with weight (normally should decrease)
    """
    rows = (await db.execute(
        select(ListingVariant, BeanListing, CanonicalBean, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .outerjoin(CanonicalBean, BeanListing.canonical_bean_id == CanonicalBean.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(BeanListing.active_flag.is_(True))
        .order_by(CanonicalBean.id, ListingVariant.weight_g.nullslast())
    )).all()

    anomalies: list[PriceAnomaly] = []

    # Collect prices per canonical bean to detect outliers
    bean_prices: dict[uuid.UUID, list[float]] = {}
    for row in rows:
        cb = row.CanonicalBean
        v = row.ListingVariant
        if cb:
            bean_prices.setdefault(cb.id, []).append(float(v.price_gbp))

    bean_medians: dict[uuid.UUID, float] = {
        bid: statistics.median(prices) for bid, prices in bean_prices.items() if prices
    }

    seen: set[uuid.UUID] = set()
    for row in rows:
        v = row.ListingVariant
        bl = row.BeanListing
        cb = row.CanonicalBean
        st = row.Store
        if v.id in seen:
            continue

        price = float(v.price_gbp)
        p100 = _p100(price, v.weight_g)
        bean_name = cb.canonical_name if cb else bl.raw_title
        bean_id = cb.id if cb else None

        reason = None
        severity = "low"

        if price > 200:
            reason = f"Price £{price:.2f} exceeds £200 — likely a data error"
            severity = "high"
        elif p100 is not None and p100 > 20:
            reason = f"Price per 100g £{p100:.2f} exceeds £20 — unusually expensive"
            severity = "medium"
        elif p100 is not None and p100 < 0.50:
            reason = f"Price per 100g £{p100:.4f} is suspiciously cheap"
            severity = "medium"
        elif cb and bean_id in bean_medians:
            median = bean_medians[bean_id]
            if median > 0 and price > median * 3:
                reason = f"Price £{price:.2f} is {price/median:.1f}× the median £{median:.2f} for this bean"
                severity = "medium"

        if reason:
            anomalies.append(PriceAnomaly(
                variant_id=v.id,
                bean_id=bean_id,
                bean_name=bean_name,
                store_name=st.name,
                weight_g=v.weight_g,
                grind_type=_enum_val(v.grind_type),
                price_gbp=price,
                price_per_100g_gbp=p100,
                reason=reason,
                severity=severity,
                recorded_at=v.recorded_at,
            ))
            seen.add(v.id)

    anomalies.sort(key=lambda a: {"high": 0, "medium": 1, "low": 2}[a.severity])
    return anomalies[:100]


# ── Admin: weight coverage ─────────────────────────────────────────────────────

@admin_router.get("/prices/weight-coverage", response_model=list[WeightCoverageRow])
async def get_weight_coverage(
    db: AsyncSession = Depends(get_db),
) -> list[WeightCoverageRow]:
    """
    Variants with missing or suspicious weight data.

    This is key for data quality: without weight_g we cannot compute
    price_per_100g and cannot do fair cross-store comparison.
    """
    rows = (await db.execute(
        select(ListingVariant, BeanListing, CanonicalBean, Store)
        .join(BeanListing, ListingVariant.bean_listing_id == BeanListing.id)
        .outerjoin(CanonicalBean, BeanListing.canonical_bean_id == CanonicalBean.id)
        .join(Store, BeanListing.store_id == Store.id)
        .where(
            BeanListing.active_flag.is_(True),
            or_(
                ListingVariant.weight_g.is_(None),
                ListingVariant.price_per_100g_gbp.is_(None),
                ListingVariant.weight_g < 10,    # suspiciously small
                ListingVariant.weight_g > 10000,  # suspiciously large
            )
        )
        .order_by(Store.name, BeanListing.raw_title)
    )).all()

    result: list[WeightCoverageRow] = []
    for row in rows:
        v = row.ListingVariant
        bl = row.BeanListing
        cb = row.CanonicalBean
        st = row.Store

        if v.weight_g is None:
            issue = "missing_weight"
        elif v.weight_g < 10 or v.weight_g > 10000:
            issue = "suspicious_weight"
        else:
            issue = "no_per_100g"

        result.append(WeightCoverageRow(
            variant_id=v.id,
            bean_id=cb.id if cb else None,
            bean_name=cb.canonical_name if cb else bl.raw_title,
            store_name=st.name,
            variant_title=v.variant_title_raw,
            weight_g=v.weight_g,
            price_gbp=float(v.price_gbp),
            price_per_100g_gbp=float(v.price_per_100g_gbp) if v.price_per_100g_gbp else None,
            issue=issue,
        ))

    return result
