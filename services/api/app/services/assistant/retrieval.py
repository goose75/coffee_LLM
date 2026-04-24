"""
Assistant retrieval layer.

Each function executes a typed DB query and returns plain-dict records
safe to serialise into the prompt context. No ORM objects leave this module.

Tools:
  search_coffees        — text + filter search, returns up to 8 beans with prices
  get_coffee_detail     — full single-bean record with all current listings
  compare_coffees       — two named beans side-by-side
  find_by_brew_method   — beans flagged for a specific brew method
  find_by_price_range   — beans with a 250g variant under a budget
  find_similar_taste    — beans sharing flavour families with a given bean

All prices come from listing_variants joined through bean_listings.
The assistant MUST NOT mention prices not present in these records.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.enums import ReviewStatus
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.pricing import ListingVariant
from app.models.store import Store


def _ev(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _fmt_variant(v: ListingVariant) -> dict:
    return {
        "weight_g": v.weight_g,
        "grind_type": _ev(v.grind_type),
        "price_gbp": float(v.price_gbp),
        "price_per_100g_gbp": float(v.price_per_100g_gbp) if v.price_per_100g_gbp else None,
        "availability": _ev(v.availability_status),
    }


def _serialise_bean(
    bean: CanonicalBean,
    listings: list[BeanListing],
    store_map: dict,
) -> dict:
    """Convert a bean + its listings into a prompt-safe dict."""
    active = [l for l in listings if l.active_flag]
    all_prices = [float(v.price_gbp) for l in active for v in l.variants]
    avail_prices = [
        float(v.price_gbp) for l in active for v in l.variants
        if _ev(v.availability_status) != "out_of_stock"
    ]

    listing_data = []
    for l in active:
        store = store_map.get(l.store_id)
        listing_data.append({
            "store_name": store.name if store else "Unknown",
            "store_domain": store.domain if store else "",
            "product_url": l.product_url,
            "variants": [_fmt_variant(v) for v in sorted(l.variants, key=lambda x: x.weight_g or 0)],
            "min_price_gbp": min([float(v.price_gbp) for v in l.variants]) if l.variants else None,
        })

    return {
        "id": str(bean.id),
        "name": bean.canonical_name,
        "origin_country": bean.origin_country,
        "origin_region": bean.origin_region,
        "farm_or_estate": bean.farm_or_estate,
        "producer": bean.producer,
        "varietal": bean.varietal,
        "process": _ev(bean.process) if bean.process else None,
        "roast_level": _ev(bean.roast_level) if bean.roast_level else None,
        "flavour_notes": bean.flavour_notes,
        "espresso_suitable": bean.espresso_suitable_flag,
        "filter_suitable": bean.filter_suitable_flag,
        "decaf": bean.decaf_flag,
        "altitude_masl": (
            f"{bean.altitude_masl_min}–{bean.altitude_masl_max} masl"
            if bean.altitude_masl_min else None
        ),
        "harvest_year": bean.harvest_year,
        "min_price_gbp": min(avail_prices) if avail_prices else None,
        "max_price_gbp": max(all_prices) if all_prices else None,
        "store_count": len({l.store_id for l in active}),
        "listings": listing_data,
    }


async def _load_beans_with_listings(
    session: AsyncSession,
    stmt,
    limit: int = 8,
) -> list[dict]:
    """Execute a bean query and join listings+variants+stores."""
    stmt = (
        stmt
        .options(
            selectinload(CanonicalBean.bean_listings)
            .selectinload(BeanListing.variants),
            selectinload(CanonicalBean.bean_listings)
            .selectinload(BeanListing.store),
        )
        .where(
            CanonicalBean.id.in_(
                select(BeanListing.canonical_bean_id)
                .where(BeanListing.active_flag.is_(True))
            )
        )
        .distinct()
        .limit(limit)
    )

    beans = (await session.execute(stmt)).scalars().unique().all()
    results = []
    for bean in beans:
        active = [l for l in bean.bean_listings if l.active_flag]
        store_map = {l.store_id: l.store for l in active if l.store}
        results.append(_serialise_bean(bean, bean.bean_listings, store_map))
    return results


# ── Tool implementations ───────────────────────────────────────────────────────

async def search_coffees(
    session: AsyncSession,
    *,
    query: str = "",
    origin_country: str | None = None,
    process: str | None = None,
    roast_level: str | None = None,
    espresso_suitable: bool | None = None,
    filter_suitable: bool | None = None,
    decaf: bool | None = None,
    limit: int = 6,
) -> list[dict]:
    """Full-text + filter search returning up to `limit` beans with current prices."""
    stmt = (
        select(CanonicalBean)
        .order_by(CanonicalBean.data_completeness_score.desc(), CanonicalBean.canonical_name)
    )
    if query:
        stmt = stmt.where(or_(
            CanonicalBean.canonical_name.ilike(f"%{query}%"),
            CanonicalBean.origin_country.ilike(f"%{query}%"),
            CanonicalBean.origin_region.ilike(f"%{query}%"),
            CanonicalBean.farm_or_estate.ilike(f"%{query}%"),
        ))
    if origin_country:
        stmt = stmt.where(CanonicalBean.origin_country.ilike(f"%{origin_country}%"))
    if process:
        stmt = stmt.where(CanonicalBean.process == process)
    if roast_level:
        stmt = stmt.where(CanonicalBean.roast_level == roast_level)
    if espresso_suitable is not None:
        stmt = stmt.where(CanonicalBean.espresso_suitable_flag.is_(espresso_suitable))
    if filter_suitable is not None:
        stmt = stmt.where(CanonicalBean.filter_suitable_flag.is_(filter_suitable))
    if decaf is not None:
        stmt = stmt.where(CanonicalBean.decaf_flag.is_(decaf))

    return await _load_beans_with_listings(session, stmt, limit=limit)


async def get_coffee_detail(
    session: AsyncSession,
    *,
    coffee_id: str | None = None,
    name_query: str | None = None,
) -> list[dict]:
    """Fetch one specific bean by ID or name fragment."""
    stmt = select(CanonicalBean)
    if coffee_id:
        try:
            stmt = stmt.where(CanonicalBean.id == uuid.UUID(coffee_id))
        except ValueError:
            return []
    elif name_query:
        stmt = stmt.where(CanonicalBean.canonical_name.ilike(f"%{name_query}%"))
    else:
        return []
    return await _load_beans_with_listings(session, stmt, limit=1)


async def compare_coffees(
    session: AsyncSession,
    *,
    name_a: str,
    name_b: str,
) -> list[dict]:
    """Retrieve two named coffees for side-by-side comparison."""
    results = []
    for name in [name_a, name_b]:
        r = await get_coffee_detail(session, name_query=name)
        if r:
            results.append(r[0])
    return results


async def find_by_brew_method(
    session: AsyncSession,
    *,
    method: str,  # "espresso" | "filter" | "both"
    limit: int = 6,
) -> list[dict]:
    """Return beans suited for a specific brew method."""
    stmt = select(CanonicalBean).order_by(CanonicalBean.data_completeness_score.desc())
    if method == "espresso":
        stmt = stmt.where(CanonicalBean.espresso_suitable_flag.is_(True))
    elif method == "filter":
        stmt = stmt.where(CanonicalBean.filter_suitable_flag.is_(True))
    else:  # both
        stmt = stmt.where(
            CanonicalBean.espresso_suitable_flag.is_(True),
            CanonicalBean.filter_suitable_flag.is_(True),
        )
    return await _load_beans_with_listings(session, stmt, limit=limit)


async def find_by_price_range(
    session: AsyncSession,
    *,
    max_price_gbp: float,
    weight_g: int = 250,
    espresso_suitable: bool | None = None,
    filter_suitable: bool | None = None,
    limit: int = 6,
) -> list[dict]:
    """Return beans with a variant at or under a price, for a given weight."""
    tolerance = 0.15  # allow ±15% weight tolerance
    wmin = int(weight_g * (1 - tolerance))
    wmax = int(weight_g * (1 + tolerance))

    # Find bean IDs that have a qualifying variant
    qualifying_stmt = (
        select(BeanListing.canonical_bean_id)
        .join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
        .where(
            BeanListing.active_flag.is_(True),
            BeanListing.canonical_bean_id.is_not(None),
            ListingVariant.weight_g >= wmin,
            ListingVariant.weight_g <= wmax,
            ListingVariant.price_gbp <= max_price_gbp,
        )
        .distinct()
    )

    stmt = select(CanonicalBean).where(
        CanonicalBean.id.in_(qualifying_stmt)
    ).order_by(CanonicalBean.data_completeness_score.desc())

    if espresso_suitable is not None:
        stmt = stmt.where(CanonicalBean.espresso_suitable_flag.is_(espresso_suitable))
    if filter_suitable is not None:
        stmt = stmt.where(CanonicalBean.filter_suitable_flag.is_(filter_suitable))

    # Override the inner where clause from _load_beans_with_listings to avoid double filter
    stmt = (
        stmt
        .options(
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants),
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.store),
        )
        .limit(limit)
    )
    beans = (await session.execute(stmt)).scalars().unique().all()
    results = []
    for bean in beans:
        active = [l for l in bean.bean_listings if l.active_flag]
        store_map = {l.store_id: l.store for l in active if l.store}
        results.append(_serialise_bean(bean, bean.bean_listings, store_map))
    return results


async def find_similar_taste(
    session: AsyncSession,
    *,
    coffee_id: str,
    limit: int = 4,
) -> list[dict]:
    """Return beans with overlapping flavour families, ranked by Jaccard similarity."""
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        return []

    # Get family slugs for the source bean
    src_tags = (await session.execute(
        select(FlavourTaxonomy.slug)
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id == bean_uuid,
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
    )).scalars().all()

    if not src_tags:
        # Fall back to flavour_notes text similarity search
        return await search_coffees(session, limit=limit)

    src_families = {slug.split(".")[0] for slug in src_tags}

    # Get all other beans' families
    all_tags = (await session.execute(
        select(BeanFlavourTag.bean_id, FlavourTaxonomy.slug)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id != bean_uuid,
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
    )).all()

    from collections import defaultdict
    bean_families: dict = defaultdict(set)
    for bid, slug in all_tags:
        bean_families[bid].add(slug.split(".")[0])

    scored = sorted(
        [(bid, len(src_families & fams) / len(src_families | fams))
         for bid, fams in bean_families.items() if fams],
        key=lambda x: -x[1],
    )

    top_ids = [str(bid) for bid, _ in scored[:limit]]
    if not top_ids:
        return []

    stmt = select(CanonicalBean).where(
        CanonicalBean.id.in_([uuid.UUID(i) for i in top_ids])
    )
    return await _load_beans_with_listings(session, stmt, limit=limit)
