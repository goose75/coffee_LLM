"""
compare.py — Coffee comparison API.

GET /api/v1/coffees/compare?ids=id1,id2,id3
  Returns a structured comparison payload for 2-3 coffees including:
  - normalised sensory dimensions (roast, body, acidity, sweetness)
  - flavour family weights
  - price per 100g
  - brew suitability
  - a short auto-generated contrast explanation
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.canonical_bean import CanonicalBean
from app.models.bean_listing import BeanListing
from app.models.pricing import ListingVariant
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.enums import ReviewStatus

router = APIRouter()

# ── Sensory dimension mappings ─────────────────────────────────────────────────
# Each returns a 0–100 score for visual bars.

ROAST_SCORES = {"light": 20, "medium_light": 38, "medium": 55, "medium_dark": 72, "dark": 90}
PROCESS_BODY_BOOST = {"natural": 15, "honey": 8, "anaerobic": 12, "washed": 0, "wet_hulled": 5}
PROCESS_ACIDITY_BOOST = {"washed": 15, "honey": 5, "natural": -5, "anaerobic": 8, "wet_hulled": -8}

# Origin acidity tendencies
ORIGIN_ACIDITY = {
    "Ethiopia": 20, "Kenya": 22, "Colombia": 12, "Guatemala": 10,
    "Rwanda": 18, "Burundi": 16, "Panama": 14, "Costa Rica": 10,
    "Honduras": 8, "Peru": 6, "Brazil": -10, "Indonesia": -15,
    "India": -8, "Yemen": 5, "Nicaragua": 5, "Tanzania": 12,
}

# Flavour families in display order with colours
FAMILY_META = [
    ("fruity",    "Fruity",     "#e05c3a"),
    ("floral",    "Floral",     "#c084c0"),
    ("sweet",     "Sweet",      "#d4a84b"),
    ("chocolate", "Chocolate",  "#7c4b2a"),
    ("nutty",     "Nutty",      "#a07850"),
    ("spice",     "Spice",      "#c47820"),
    ("earthy",    "Earthy",     "#6b7c4a"),
    ("fermented", "Fermented",  "#8b6bab"),
]


def _ev(val) -> str | None:
    if val is None:
        return None
    return val.value if hasattr(val, "value") else str(val)


def compute_sensory(bean: CanonicalBean, family_weights: dict[str, int]) -> dict[str, float]:
    """Compute 0–100 sensory scores for a single bean."""
    roast = _ev(bean.roast_level) or "medium"
    process = _ev(bean.process) or "washed"
    origin = bean.origin_country or ""

    roast_score = ROAST_SCORES.get(roast, 55)

    # Body: base from roast + process boost
    body = 30 + (roast_score * 0.4) + PROCESS_BODY_BOOST.get(process, 0)
    body = max(5, min(95, body))

    # Acidity: inverse of roast + process/origin signals
    acidity = 80 - (roast_score * 0.6) + PROCESS_ACIDITY_BOOST.get(process, 0)
    acidity += ORIGIN_ACIDITY.get(origin, 0)
    acidity = max(5, min(95, acidity))

    # Sweetness: natural/honey high, dark roast reduces
    sweetness = 50 + PROCESS_BODY_BOOST.get(process, 0) * 1.5 - (roast_score - 55) * 0.3
    sweetness = max(5, min(95, sweetness))

    # Complexity: driven by flavour family diversity + anaerobic/natural
    family_count = len([v for v in family_weights.values() if v > 0])
    complexity = 20 + family_count * 10 + (15 if process == "anaerobic" else 0)
    complexity = max(5, min(95, complexity))

    return {
        "roast":      round(roast_score),
        "body":       round(body),
        "acidity":    round(acidity),
        "sweetness":  round(sweetness),
        "complexity": round(complexity),
    }


def generate_contrast(coffees: list[dict]) -> str:
    """
    Generate a short, grounded contrast sentence for 2-3 coffees.
    Purely data-driven — no LLM.
    """
    if len(coffees) < 2:
        return ""

    a, b = coffees[0], coffees[1]
    a_name = a["canonical_name"].split(",")[0].strip()
    b_name = b["canonical_name"].split(",")[0].strip()

    parts: list[str] = []

    # Roast contrast
    ra, rb = a["sensory"]["roast"], b["sensory"]["roast"]
    if abs(ra - rb) >= 20:
        lighter = a_name if ra < rb else b_name
        darker = b_name if ra < rb else a_name
        parts.append(f"{lighter} is lighter roasted, {darker} is darker and more intense")

    # Acidity contrast
    aa, ab = a["sensory"]["acidity"], b["sensory"]["acidity"]
    if abs(aa - ab) >= 15:
        brighter = a_name if aa > ab else b_name
        softer = b_name if aa > ab else a_name
        parts.append(f"{brighter} has brighter acidity while {softer} is smoother")

    # Flavour family contrast
    a_families = sorted(a["family_weights"].items(), key=lambda x: -x[1])
    b_families = sorted(b["family_weights"].items(), key=lambda x: -x[1])
    a_top = a_families[0][0] if a_families and a_families[0][1] > 0 else None
    b_top = b_families[0][0] if b_families and b_families[0][1] > 0 else None

    if a_top and b_top and a_top != b_top:
        parts.append(f"{a_name} leans {a_top} while {b_name} is more {b_top}-led")
    elif a_top and b_top and a_top == b_top:
        parts.append(f"both share {a_top} character")

    # Process contrast
    pa, pb = a.get("process"), b.get("process")
    if pa and pb and pa != pb:
        parts.append(f"{a_name} is {pa}-processed giving it different structure to the {pb} {b_name}")

    if not parts:
        return f"{a_name} and {b_name} share a similar profile."

    return ". ".join(parts[:3]) + "."


# ── Response models ───────────────────────────────────────────────────────────

class CoffeeCompareItem(BaseModel):
    id: str
    canonical_name: str
    origin_country: str | None
    origin_region: str | None
    farm_or_estate: str | None
    process: str | None
    roast_level: str | None
    varietal: list[str]
    harvest_year: int | None
    altitude_masl_min: int | None
    altitude_masl_max: int | None
    decaf_flag: bool
    espresso_suitable_flag: bool
    filter_suitable_flag: bool
    flavour_notes: list[str]
    data_completeness_score: float
    # Pricing
    min_price_gbp: float | None
    price_per_100g_gbp: float | None
    listing_count: int
    # Sensory dimensions (0-100)
    sensory: dict[str, float]
    # Flavour families (slug → bean count/weight)
    family_weights: dict[str, int]
    # Family metadata for display
    family_meta: list[dict]


class CompareResponse(BaseModel):
    coffees: list[CoffeeCompareItem]
    contrast: str
    shared_notes: list[str]
    family_slugs: list[str]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/coffees/compare-multi", response_model=CompareResponse)
async def compare_coffees(
    ids: str = Query(..., description="Comma-separated coffee IDs (2-3)"),
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """
    Return a structured comparison payload for 2-3 coffees.
    """
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=422, detail="At least 2 coffee IDs required")
    if len(id_list) > 3:
        raise HTTPException(status_code=422, detail="Maximum 3 coffees can be compared")

    import uuid as uuid_mod
    uuids = []
    for id_str in id_list:
        try:
            uuids.append(uuid_mod.UUID(id_str))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid UUID: {id_str}")

    # Load beans with listings
    beans = (await db.execute(
        select(CanonicalBean)
        .where(CanonicalBean.id.in_(uuids))
        .options(
            selectinload(CanonicalBean.bean_listings).selectinload(BeanListing.variants)
        )
    )).scalars().all()

    if len(beans) != len(uuids):
        found_ids = {str(b.id) for b in beans}
        missing = [i for i in id_list if i not in found_ids]
        raise HTTPException(status_code=404, detail=f"Coffee(s) not found: {missing}")

    # Order beans to match input order
    bean_map = {str(b.id): b for b in beans}
    beans = [bean_map[i] for i in id_list]

    # Load flavour family weights per bean
    family_rows = (await db.execute(
        select(FlavourTaxonomy.slug, BeanFlavourTag.bean_id, func.count(BeanFlavourTag.id))
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id.in_(uuids),
            BeanFlavourTag.review_status == ReviewStatus.accepted,
            FlavourTaxonomy.depth == 0,
        )
        .group_by(FlavourTaxonomy.slug, BeanFlavourTag.bean_id)
    )).all()

    # {bean_id: {family_slug: count}}
    bean_families: dict[str, dict[str, int]] = {str(b.id): {} for b in beans}
    for slug, bean_id, count in family_rows:
        bean_families[str(bean_id)][slug] = count

    items: list[dict] = []
    for bean in beans:
        active = [l for l in bean.bean_listings if l.active_flag]
        all_prices = [float(v.price_gbp) for l in active for v in l.variants]
        avail_prices = [float(v.price_gbp) for l in active for v in l.variants
                        if v.availability_status != "out_of_stock"]

        # Best price per 100g from 250g variants
        p100g = None
        for l in active:
            for v in l.variants:
                if v.weight_g and v.weight_g > 0:
                    candidate = float(v.price_gbp) / v.weight_g * 100
                    if p100g is None or candidate < p100g:
                        p100g = candidate

        family_weights = {slug: 0 for slug, _, _ in FAMILY_META}
        family_weights.update(bean_families.get(str(bean.id), {}))

        sensory = compute_sensory(bean, family_weights)

        items.append({
            "id": str(bean.id),
            "canonical_name": bean.canonical_name,
            "origin_country": bean.origin_country,
            "origin_region": bean.origin_region,
            "farm_or_estate": bean.farm_or_estate,
            "process": _ev(bean.process),
            "roast_level": _ev(bean.roast_level),
            "varietal": bean.varietal or [],
            "harvest_year": bean.harvest_year,
            "altitude_masl_min": bean.altitude_masl_min,
            "altitude_masl_max": bean.altitude_masl_max,
            "decaf_flag": bean.decaf_flag,
            "espresso_suitable_flag": bean.espresso_suitable_flag,
            "filter_suitable_flag": bean.filter_suitable_flag,
            "flavour_notes": bean.flavour_notes or [],
            "data_completeness_score": bean.data_completeness_score,
            "min_price_gbp": min(avail_prices) if avail_prices else None,
            "price_per_100g_gbp": round(p100g, 2) if p100g else None,
            "listing_count": len(active),
            "sensory": sensory,
            "family_weights": family_weights,
            "family_meta": [
                {"slug": s, "label": l, "colour": c}
                for s, l, c in FAMILY_META
            ],
        })

    # Shared flavour notes
    if items:
        note_sets = [set(i["flavour_notes"]) for i in items]
        shared = list(note_sets[0].intersection(*note_sets[1:]))
    else:
        shared = []

    contrast = generate_contrast(items)

    return CompareResponse(
        coffees=[CoffeeCompareItem(**item) for item in items],
        contrast=contrast,
        shared_notes=shared[:6],
        family_slugs=[s for s, _, _ in FAMILY_META],
    )
