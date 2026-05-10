"""
roaster_fingerprint.py — Roaster fingerprint aggregate API.

GET /api/v1/roasters/{roaster_id}/fingerprint
  Returns a full style profile for a roaster derived from their coffee data:
  flavour families, origin mix, process mix, roast tendencies, price stats,
  newest coffees, and a short style summary.
"""
from __future__ import annotations
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid as _uuid

from app.core.database import get_db
from app.models.store import Store
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.pricing import ListingVariant
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.enums import ReviewStatus

router = APIRouter()

PROCESS_COLOURS = {
    "washed": "#6b9e8c", "natural": "#c4763a", "honey": "#d4a84b",
    "anaerobic": "#8b6bab", "wet_hulled": "#5a7fa8",
}
FAMILY_COLOURS = {
    "fruity": "#e05c3a", "floral": "#c084c0", "sweet": "#d4a84b",
    "chocolate": "#7c4b2a", "nutty": "#a07850", "spice": "#c47820",
    "earthy": "#6b7c4a", "fermented": "#8b6bab",
}


def _ev(val):
    if val is None: return None
    return val.value if hasattr(val, "value") else str(val)


def _style_summary(
    top_families: list[str],
    top_process: str | None,
    dominant_roast: str | None,
    top_origins: list[str],
    avg_price: float | None,
) -> str:
    """Generate a short grounded style description from aggregate data."""
    parts = []

    # Process tendency
    if top_process == "washed":
        parts.append("clean, washed-process coffees")
    elif top_process == "natural":
        parts.append("expressive natural-process coffees")
    elif top_process == "honey":
        parts.append("nuanced honey-process coffees")
    elif top_process == "anaerobic":
        parts.append("experimental anaerobic lots")

    # Roast tendency
    if dominant_roast in ("light", "medium_light"):
        parts.append("roasted light to preserve origin character")
    elif dominant_roast in ("medium",):
        parts.append("medium-roasted for balance")
    elif dominant_roast in ("dark", "medium_dark"):
        parts.append("roasted darker for body and intensity")

    # Flavour tendency
    flav_map = {
        "fruity": "fruit-forward character",
        "floral": "floral delicacy",
        "chocolate": "chocolate depth",
        "nutty": "nutty warmth",
        "sweet": "natural sweetness",
        "fermented": "complex fermented notes",
        "earthy": "earthy complexity",
    }
    fam_parts = [flav_map[f] for f in top_families[:2] if f in flav_map]
    if fam_parts:
        parts.append(f"with {' and '.join(fam_parts)}")

    # Origin tendency
    if top_origins:
        if len(top_origins) == 1:
            parts.append(f"sourced primarily from {top_origins[0]}")
        elif len(top_origins) == 2:
            parts.append(f"drawing from {top_origins[0]} and {top_origins[1]}")
        else:
            parts.append(f"spanning {len(top_origins)} origins")

    if not parts:
        return "A specialty roaster with a diverse range of coffees."

    summary = "This roaster tends toward " + ", ".join(parts[:3]) + "."
    return summary[0].upper() + summary[1:]


class FamilyStat(BaseModel):
    slug: str
    label: str
    colour: str
    count: int
    pct: int

class ProcessStat(BaseModel):
    process: str
    colour: str
    count: int
    pct: int

class OriginStat(BaseModel):
    country: str
    count: int
    pct: int

class RoastStat(BaseModel):
    roast_level: str
    count: int
    pct: int

class RecentCoffee(BaseModel):
    id: str
    canonical_name: str
    origin_country: str | None
    process: str | None
    roast_level: str | None
    flavour_notes: list[str]
    min_price_gbp: float | None

class RoasterFingerprint(BaseModel):
    store_id: str
    name: str
    domain: str
    homepage_url: str
    uk_region: str | None
    roaster_flag: bool
    cafe_flag: bool
    coffee_count: int
    listing_count: int
    style_summary: str
    flavour_families: list[FamilyStat]
    processes: list[ProcessStat]
    origins: list[OriginStat]
    roast_levels: list[RoastStat]
    avg_price_gbp: float | None
    price_min_gbp: float | None
    price_max_gbp: float | None
    recent_coffees: list[RecentCoffee]


@router.get("/roasters/{roaster_id}/fingerprint", response_model=RoasterFingerprint)
async def get_roaster_fingerprint(
    roaster_id: str,
    db: AsyncSession = Depends(get_db),
) -> RoasterFingerprint:
    try:
        store_uuid = _uuid.UUID(roaster_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(
        select(Store).where(Store.id == store_uuid)
    )).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Roaster not found")

    # Get all active listings for this store
    listings = (await db.execute(
        select(BeanListing)
        .where(BeanListing.store_id == store_uuid, BeanListing.active_flag.is_(True))
    )).scalars().all()

    listing_count = len(listings)
    bean_ids_raw = list({bl.canonical_bean_id for bl in listings if bl.canonical_bean_id})

    # Get canonical beans
    beans = []
    if bean_ids_raw:
        beans = (await db.execute(
            select(CanonicalBean).where(CanonicalBean.id.in_(bean_ids_raw))
        )).scalars().all()

    coffee_count = len(beans)

    # Prices
    price_rows = (await db.execute(
        select(func.min(ListingVariant.price_gbp),
               func.max(ListingVariant.price_gbp),
               func.avg(ListingVariant.price_gbp))
        .join(BeanListing, BeanListing.id == ListingVariant.bean_listing_id)
        .where(BeanListing.store_id == store_uuid, BeanListing.active_flag.is_(True))
    )).one()
    price_min, price_max, price_avg = price_rows

    # Flavour families
    if bean_ids_raw:
        raw_tag_rows = (await db.execute(
            select(FlavourTaxonomy.slug, BeanFlavourTag.bean_id)
            .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
            .where(
                BeanFlavourTag.bean_id.in_(bean_ids_raw),
                BeanFlavourTag.review_status == ReviewStatus.accepted,
            )
        )).all()
        family_nodes = {n.slug: n.label for n in (await db.execute(
            select(FlavourTaxonomy).where(FlavourTaxonomy.depth == 0)
        )).scalars().all()}
        from collections import defaultdict
        fam_bean_sets = defaultdict(set)
        for slug, bean_id in raw_tag_rows:
            family_slug = slug.split(".")[0]
            if family_slug in family_nodes:
                fam_bean_sets[family_slug].add(bean_id)
        fam_rows = [(slug, family_nodes[slug], len(beans)) for slug, beans in
                    sorted(fam_bean_sets.items(), key=lambda x: -len(x[1]))]
    else:
        fam_rows = []

    flavour_families = [
        FamilyStat(
            slug=s, label=l,
            colour=FAMILY_COLOURS.get(s, "#888"),
            count=c,
            pct=round(c / max(coffee_count, 1) * 100),
        )
        for s, l, c in fam_rows
    ]

    # Processes
    proc_counter = Counter(_ev(b.process) for b in beans if b.process)
    total_with_proc = sum(proc_counter.values())
    processes = [
        ProcessStat(
            process=p,
            colour=PROCESS_COLOURS.get(p, "#888"),
            count=c,
            pct=round(c / max(total_with_proc, 1) * 100),
        )
        for p, c in proc_counter.most_common()
    ]

    # Origins
    origin_counter = Counter(b.origin_country for b in beans if b.origin_country)
    total_with_origin = sum(origin_counter.values())
    origins = [
        OriginStat(
            country=country,
            count=c,
            pct=round(c / max(total_with_origin, 1) * 100),
        )
        for country, c in origin_counter.most_common(8)
    ]

    # Roast levels
    roast_counter = Counter(_ev(b.roast_level) for b in beans if b.roast_level)
    total_with_roast = sum(roast_counter.values())
    roast_order = ["light", "medium_light", "medium", "medium_dark", "dark"]
    roast_levels = [
        RoastStat(
            roast_level=r,
            count=roast_counter[r],
            pct=round(roast_counter[r] / max(total_with_roast, 1) * 100),
        )
        for r in roast_order if r in roast_counter
    ]

    # Recent coffees (last 6 linked beans)
    recent_listing_ids = sorted(
        [(bl.canonical_bean_id, bl.first_seen_at) for bl in listings if bl.canonical_bean_id],
        key=lambda x: x[1] or "", reverse=True
    )[:6]
    recent_bean_ids = [bid for bid, _ in recent_listing_ids]

    # Min prices for recent beans
    recent_prices = {}
    if recent_bean_ids:
        price_res = (await db.execute(
            select(BeanListing.canonical_bean_id, func.min(ListingVariant.price_gbp))
            .join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
            .where(BeanListing.canonical_bean_id.in_(recent_bean_ids),
                   BeanListing.store_id == store_uuid)
            .group_by(BeanListing.canonical_bean_id)
        )).all()
        recent_prices = {str(bid): float(p) for bid, p in price_res if p}

    bean_map = {b.id: b for b in beans}
    recent_coffees = []
    seen = set()
    for bid, _ in recent_listing_ids:
        if bid in seen or bid not in bean_map:
            continue
        seen.add(bid)
        b = bean_map[bid]
        recent_coffees.append(RecentCoffee(
            id=str(b.id),
            canonical_name=b.canonical_name,
            origin_country=b.origin_country,
            process=_ev(b.process),
            roast_level=_ev(b.roast_level),
            flavour_notes=(b.flavour_notes or [])[:3],
            min_price_gbp=recent_prices.get(str(b.id)),
        ))

    # Style summary
    top_families = [f.slug for f in flavour_families[:3]]
    top_process = processes[0].process if processes else None
    dominant_roast = roast_levels[0].roast_level if roast_levels else None
    top_origins = [o.country for o in origins[:3]]

    summary = _style_summary(top_families, top_process, dominant_roast, top_origins,
                             float(price_avg) if price_avg else None)

    return RoasterFingerprint(
        store_id=str(store.id),
        name=store.name,
        domain=store.domain,
        homepage_url=store.homepage_url,
        uk_region=store.uk_region,
        roaster_flag=store.roaster_flag,
        cafe_flag=store.cafe_flag,
        coffee_count=coffee_count,
        listing_count=listing_count,
        style_summary=summary,
        flavour_families=flavour_families,
        processes=processes,
        origins=origins,
        roast_levels=roast_levels,
        avg_price_gbp=round(float(price_avg), 2) if price_avg else None,
        price_min_gbp=round(float(price_min), 2) if price_min else None,
        price_max_gbp=round(float(price_max), 2) if price_max else None,
        recent_coffees=recent_coffees,
    )
