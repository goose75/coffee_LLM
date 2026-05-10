"""
Public API v1 router — implemented.
All endpoints are read-only and consumer-facing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.pricing import ListingVariant
from app.models.store import Store
from app.schemas.public import (
    CoffeeDetailPublic,
    CoffeePublic,
    PaginatedCoffees,
    PaginatedRoasters,
    RoasterPublic,
    StoreListingPublic,
    PriceVariantPublic,
)

router = APIRouter()


def _coffee_aggregates(bean: CanonicalBean) -> dict:
    active = [l for l in bean.bean_listings if l.active_flag]
    all_prices = [float(v.price_gbp) for l in active for v in l.variants]
    avail_prices = [float(v.price_gbp) for l in active for v in l.variants if v.availability_status != "out_of_stock"]
    store_ids = {l.store_id for l in active}
    # Price per 100g — use best available across all variants
    per_100g_prices = [
        float(v.price_per_100g_gbp)
        for l in active for v in l.variants
        if v.price_per_100g_gbp is not None and v.availability_status != "out_of_stock"
    ]
    return {
        "listing_count": len(active),
        "store_count": len(store_ids),
        "min_price_gbp": min(avail_prices) if avail_prices else None,
        "max_price_gbp": max(all_prices) if all_prices else None,
        "min_price_per_100g_gbp": min(per_100g_prices) if per_100g_prices else None,
    }


def _variant_val(v, field):
    val = getattr(v, field, None)
    if hasattr(val, "value"):
        return val.value
    return val


def _hydrate_listings(listings, store_map) -> list[StoreListingPublic]:
    result = []
    for listing in listings:
        if not listing.active_flag:
            continue
        store = store_map.get(listing.store_id)
        listing_status = listing.listing_status
        if hasattr(listing_status, "value"):
            listing_status = listing_status.value
        item = StoreListingPublic(
            id=listing.id,
            store_id=listing.store_id,
            store_name=store.name if store else "",
            store_domain=store.domain if store else "",
            store_homepage_url=store.homepage_url if store else "",
            raw_title=listing.raw_title,
            product_url=listing.product_url,
            listing_status=str(listing_status),
            active_flag=listing.active_flag,
            variants=[
                PriceVariantPublic(
                    id=v.id,
                    weight_g=v.weight_g,
                    grind_type=_variant_val(v, "grind_type") or "unknown",
                    price_gbp=float(v.price_gbp),
                    price_per_100g_gbp=float(v.price_per_100g_gbp) if v.price_per_100g_gbp else None,
                    availability_status=_variant_val(v, "availability_status") or "unknown",
                    sku=v.sku,
                )
                for v in sorted(listing.variants, key=lambda x: (x.weight_g or 0))
            ],
        )
        result.append(item)
    return result


@router.get("/coffees", response_model=PaginatedCoffees)
async def list_coffees(
    q: str | None = Query(None),
    origin_country: str | None = None,
    origin_region: str | None = None,
    process: str | None = None,
    roast_level: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    decaf: bool | None = None,
    espresso_suitable: bool | None = None,
    filter_suitable: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedCoffees:
    stmt = (
        select(CanonicalBean)
        .join(BeanListing, BeanListing.canonical_bean_id == CanonicalBean.id)
        .where(BeanListing.active_flag.is_(True))
        .distinct()
    )
    if q:
        stmt = stmt.where(or_(
            CanonicalBean.canonical_name.ilike(f"%{q}%"),
            CanonicalBean.origin_country.ilike(f"%{q}%"),
            CanonicalBean.origin_region.ilike(f"%{q}%"),
            CanonicalBean.farm_or_estate.ilike(f"%{q}%"),
        ))
    if origin_country:
        stmt = stmt.where(CanonicalBean.origin_country.ilike(f"%{origin_country}%"))
    if origin_region:
        stmt = stmt.where(CanonicalBean.origin_region.ilike(f"%{origin_region}%"))
    if process:
        stmt = stmt.where(CanonicalBean.process == process)
    if roast_level:
        stmt = stmt.where(CanonicalBean.roast_level == roast_level)
    if decaf is not None:
        stmt = stmt.where(CanonicalBean.decaf_flag.is_(decaf))
    if espresso_suitable is not None:
        stmt = stmt.where(CanonicalBean.espresso_suitable_flag.is_(espresso_suitable))
    if filter_suitable is not None:
        stmt = stmt.where(CanonicalBean.filter_suitable_flag.is_(filter_suitable))
    if min_price is not None or max_price is not None:
        stmt = stmt.join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
        if min_price is not None:
            stmt = stmt.where(ListingVariant.price_gbp >= min_price)
        if max_price is not None:
            stmt = stmt.where(ListingVariant.price_gbp <= max_price)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = (
        stmt
        .options(
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants),
        )
        .order_by(CanonicalBean.data_completeness_score.desc(), CanonicalBean.canonical_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    beans = (await db.execute(stmt)).scalars().unique().all()

    items = []
    for bean in beans:
        agg = _coffee_aggregates(bean)
        item = CoffeePublic.model_validate(bean)
        item.listing_count = agg["listing_count"]
        item.store_count = agg["store_count"]
        item.min_price_gbp = agg["min_price_gbp"]
        item.min_price_per_100g_gbp = agg.get("min_price_per_100g_gbp")
        item.max_price_gbp = agg["max_price_gbp"]
        items.append(item)

    return PaginatedCoffees(data=items, total=total, page=page, page_size=page_size, has_next=(page * page_size) < total)


@router.get("/coffees/{coffee_id}", response_model=CoffeeDetailPublic)
async def get_coffee(coffee_id: str, db: AsyncSession = Depends(get_db)) -> CoffeeDetailPublic:
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    stmt = (
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
        .options(
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants),
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.store),
        )
    )
    bean = (await db.execute(stmt)).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Coffee not found")

    active = [l for l in bean.bean_listings if l.active_flag]
    store_map = {l.store_id: l.store for l in active if l.store}
    agg = _coffee_aggregates(bean)

    item = CoffeeDetailPublic.model_validate(bean)
    item.listing_count = agg["listing_count"]
    item.store_count = agg["store_count"]
    item.min_price_gbp = agg["min_price_gbp"]
    item.min_price_per_100g_gbp = agg.get("min_price_per_100g_gbp")
    item.max_price_gbp = agg["max_price_gbp"]
    item.listings = _hydrate_listings(active, store_map)
    return item


@router.get("/coffees/{coffee_id}/compare", response_model=CoffeeDetailPublic)
async def compare_coffee(coffee_id: str, db: AsyncSession = Depends(get_db)) -> CoffeeDetailPublic:
    return await get_coffee(coffee_id, db)


@router.get("/roasters", response_model=PaginatedRoasters)
async def list_roasters(
    q: str | None = None,
    uk_region: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedRoasters:
    stmt = select(Store).where(Store.roaster_flag.is_(True), Store.active_flag.is_(True))
    if q:
        stmt = stmt.where(or_(Store.name.ilike(f"%{q}%"), Store.domain.ilike(f"%{q}%")))
    if uk_region:
        stmt = stmt.where(Store.uk_region.ilike(f"%{uk_region}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stores = (await db.execute(stmt.order_by(Store.name).offset((page - 1) * page_size).limit(page_size))).scalars().all()

    if stores:
        store_ids = [s.id for s in stores]
        counts_rows = (await db.execute(
            select(BeanListing.store_id, func.count(BeanListing.id).label("cnt"))
            .where(BeanListing.store_id.in_(store_ids), BeanListing.active_flag.is_(True))
            .group_by(BeanListing.store_id)
        )).all()
        count_map = {str(r.store_id): r.cnt for r in counts_rows}
    else:
        count_map = {}

    items = []
    for store in stores:
        item = RoasterPublic.model_validate(store)
        item.listing_count = count_map.get(str(store.id), 0)
        items.append(item)

    return PaginatedRoasters(data=items, total=total, page=page, page_size=page_size, has_next=(page * page_size) < total)


@router.get("/roasters/{roaster_id}", response_model=RoasterPublic)
async def get_roaster(roaster_id: str, db: AsyncSession = Depends(get_db)) -> RoasterPublic:
    try:
        store_uuid = uuid.UUID(roaster_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Roaster not found")
    count = (await db.execute(
        select(func.count(BeanListing.id))
        .where(BeanListing.store_id == store.id, BeanListing.active_flag.is_(True))
    )).scalar_one()
    item = RoasterPublic.model_validate(store)
    item.listing_count = count
    return item


@router.get("/new-releases", response_model=PaginatedCoffees)
async def new_releases(
    days: int = Query(14, ge=1, le=90),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedCoffees:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(CanonicalBean)
        .join(BeanListing, BeanListing.canonical_bean_id == CanonicalBean.id)
        .where(BeanListing.active_flag.is_(True), BeanListing.first_seen_at >= cutoff)
        .distinct()
    )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    newest_seen = (
        select(func.max(BeanListing.first_seen_at))
        .where(
            BeanListing.canonical_bean_id == CanonicalBean.id,
            BeanListing.active_flag.is_(True),
        )
        .correlate(CanonicalBean)
        .scalar_subquery()
    )

    stmt = (
        stmt
        .options(selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants))
        .order_by(newest_seen.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    beans = (await db.execute(stmt)).scalars().unique().all()

    items = []
    for bean in beans:
        agg = _coffee_aggregates(bean)
        item = CoffeePublic.model_validate(bean)
        item.listing_count = agg["listing_count"]
        item.store_count = agg["store_count"]
        item.min_price_gbp = agg["min_price_gbp"]
        item.min_price_per_100g_gbp = agg.get("min_price_per_100g_gbp")
        item.max_price_gbp = agg["max_price_gbp"]
        # Surface the most-recent listing timestamp for the new-releases feed
        newest = max(
            (l.first_seen_at for l in bean.bean_listings if l.active_flag),
            default=None,
        )
        if newest:
            item.newest_listing_at = newest.isoformat()
        items.append(item)

    return PaginatedCoffees(data=items, total=total, page=page, page_size=page_size, has_next=(page * page_size) < total)


@router.get("/stores/{store_id}/listings", response_model=PaginatedCoffees)
async def store_listings(
    store_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedCoffees:
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    stmt = (
        select(CanonicalBean)
        .join(BeanListing, BeanListing.canonical_bean_id == CanonicalBean.id)
        .where(BeanListing.store_id == store_uuid, BeanListing.active_flag.is_(True))
        .distinct()
    )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = (
        stmt
        .options(selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants))
        .order_by(CanonicalBean.canonical_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    beans = (await db.execute(stmt)).scalars().unique().all()

    items = []
    for bean in beans:
        agg = _coffee_aggregates(bean)
        item = CoffeePublic.model_validate(bean)
        item.listing_count = agg["listing_count"]
        item.store_count = agg["store_count"]
        item.min_price_gbp = agg["min_price_gbp"]
        item.min_price_per_100g_gbp = agg.get("min_price_per_100g_gbp")
        item.max_price_gbp = agg["max_price_gbp"]
        items.append(item)

    return PaginatedCoffees(data=items, total=total, page=page, page_size=page_size, has_next=(page * page_size) < total)

@router.get("/market/averages")
async def get_market_averages(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Return market-wide price statistics for value comparison.
    Used by browse cards to show ValueBadge (good value / premium).
    """
    from sqlalchemy import text as sql_text
    result = await db.execute(sql_text("""
        SELECT
            percentile_cont(0.5) WITHIN GROUP (ORDER BY lv.price_per_100g_gbp) as median_per_100g,
            AVG(lv.price_per_100g_gbp) as mean_per_100g,
            MIN(lv.price_per_100g_gbp) as min_per_100g,
            MAX(lv.price_per_100g_gbp) as max_per_100g,
            COUNT(DISTINCT bl.canonical_bean_id) as sample_size
        FROM listing_variants lv
        JOIN bean_listings bl ON bl.id = lv.bean_listing_id
        WHERE bl.active_flag = true
        AND lv.price_per_100g_gbp IS NOT NULL
        AND lv.price_per_100g_gbp > 0
        AND lv.price_per_100g_gbp < 50
        AND lv.availability_status != 'out_of_stock'
    """))
    row = result.one()
    return {
        "median_per_100g_gbp": round(float(row.median_per_100g), 2) if row.median_per_100g else None,
        "mean_per_100g_gbp": round(float(row.mean_per_100g), 2) if row.mean_per_100g else None,
        "min_per_100g_gbp": round(float(row.min_per_100g), 2) if row.min_per_100g else None,
        "max_per_100g_gbp": round(float(row.max_per_100g), 2) if row.max_per_100g else None,
        "sample_size": row.sample_size,
    }
