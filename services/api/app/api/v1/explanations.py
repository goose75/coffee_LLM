"""
explanations.py — Explanation API endpoints.

GET /api/v1/explain/coffee/{coffee_id}
GET /api/v1/explain/compare?ids=id1,id2
GET /api/v1/explain/origin/{country}
GET /api/v1/explain/roaster/{roaster_id}
GET /api/v1/explain/search?q=query&coffee_id=id

All endpoints:
  - Return {"explanation": "...", "source": "llm"|"rules"|"cache"}
  - Never raise on LLM failure — always return something
  - Cache at the application layer (1 hour TTL)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid as _uuid

from app.core.database import get_db
from app.core.config import settings
from app.models.canonical_bean import CanonicalBean
from app.models.store import Store
from app.models.bean_listing import BeanListing
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.enums import ReviewStatus
from app.services.explain import (
    explain,
    build_coffee_profile_data,
    build_compare_data,
    build_origin_data,
    build_roaster_data,
    build_search_match_data,
    _cache_key,
    _cache_get,
)

router = APIRouter()


class ExplanationResponse(BaseModel):
    explanation: str
    source: str   # "llm" | "rules" | "cache"


def _ev(val):
    if val is None: return None
    return val.value if hasattr(val, "value") else str(val)


@router.get("/explain/coffee/{coffee_id}", response_model=ExplanationResponse)
async def explain_coffee(
    coffee_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    try:
        bean_uuid = _uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if not bean:
        raise HTTPException(status_code=404, detail="Coffee not found")

    data = build_coffee_profile_data({
        "canonical_name": bean.canonical_name,
        "origin_country": bean.origin_country,
        "origin_region": bean.origin_region,
        "process": _ev(bean.process),
        "roast_level": _ev(bean.roast_level),
        "flavour_notes": bean.flavour_notes or [],
        "altitude_masl_min": bean.altitude_masl_min,
        "espresso_suitable_flag": bean.espresso_suitable_flag,
        "filter_suitable_flag": bean.filter_suitable_flag,
        "varietal": bean.varietal or [],
    })

    key = _cache_key("coffee_profile", data)
    cached = _cache_get(key)
    source = "cache" if cached else ("llm" if settings.ANTHROPIC_API_KEY else "rules")

    text = await explain("coffee_profile", data, api_key=settings.ANTHROPIC_API_KEY)
    return ExplanationResponse(explanation=text, source=source)


@router.get("/explain/compare", response_model=ExplanationResponse)
async def explain_compare(
    ids: str = Query(..., description="Comma-separated coffee IDs"),
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    id_list = [i.strip() for i in ids.split(",") if i.strip()][:3]
    if len(id_list) < 2:
        raise HTTPException(status_code=422, detail="At least 2 IDs required")

    uuids = [_uuid.UUID(i) for i in id_list]
    beans = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id.in_(uuids))
    )).scalars().all()

    bean_map = {str(b.id): b for b in beans}
    ordered = [bean_map[i] for i in id_list if i in bean_map]

    coffees = [
        {
            "canonical_name": b.canonical_name,
            "origin_country": b.origin_country,
            "process": _ev(b.process),
            "roast_level": _ev(b.roast_level),
            "flavour_notes": b.flavour_notes or [],
        }
        for b in ordered
    ]

    data = build_compare_data(coffees)
    key = _cache_key("coffee_compare", data)
    cached = _cache_get(key)
    source = "cache" if cached else ("llm" if settings.ANTHROPIC_API_KEY else "rules")

    text = await explain("coffee_compare", data, api_key=settings.ANTHROPIC_API_KEY)
    return ExplanationResponse(explanation=text, source=source)


@router.get("/explain/origin/{country}", response_model=ExplanationResponse)
async def explain_origin(
    country: str,
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    from urllib.parse import unquote
    country = unquote(country)

    beans = (await db.execute(
        select(CanonicalBean)
        .where(func.lower(CanonicalBean.origin_country) == country.lower())
    )).scalars().all()

    if not beans:
        return ExplanationResponse(
            explanation="No coffees from this origin yet.",
            source="rules"
        )

    bean_ids = [b.id for b in beans]

    # Get flavour families
    fam_rows = (await db.execute(
        select(FlavourTaxonomy.label, func.count(func.distinct(BeanFlavourTag.bean_id)))
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id.in_(bean_ids),
            BeanFlavourTag.review_status == ReviewStatus.accepted,
            FlavourTaxonomy.depth == 0,
        )
        .group_by(FlavourTaxonomy.label)
        .order_by(func.count(func.distinct(BeanFlavourTag.bean_id)).desc())
    )).all()

    from collections import Counter
    proc_counter = Counter(_ev(b.process) for b in beans if b.process)
    dominant_process = proc_counter.most_common(1)[0][0] if proc_counter else None

    alts = [b.altitude_masl_min for b in beans if b.altitude_masl_min]
    alt_max = [b.altitude_masl_max for b in beans if b.altitude_masl_max]

    origin_data = {
        "country": country,
        "coffee_count": len(beans),
        "processes": [{"process": dominant_process, "pct": 100}] if dominant_process else [],
        "flavour_families": [{"label": l, "count": c} for l, c in fam_rows],
        "altitude_min": min(alts) if alts else None,
        "altitude_max": max(alt_max) if alt_max else None,
    }

    data = build_origin_data(origin_data)
    key = _cache_key("origin_character", data)
    cached = _cache_get(key)
    source = "cache" if cached else ("llm" if settings.ANTHROPIC_API_KEY else "rules")

    text = await explain("origin_character", data, api_key=settings.ANTHROPIC_API_KEY)
    return ExplanationResponse(explanation=text, source=source)


@router.get("/explain/roaster/{roaster_id}", response_model=ExplanationResponse)
async def explain_roaster(
    roaster_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    try:
        store_uuid = _uuid.UUID(roaster_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(
        select(Store).where(Store.id == store_uuid)
    )).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Roaster not found")

    # Reuse the fingerprint data builder
    from app.api.v1.roaster_fingerprint import get_roaster_fingerprint
    fp = await get_roaster_fingerprint(roaster_id, db)

    fp_dict = {
        "name": fp.name,
        "coffee_count": fp.coffee_count,
        "processes": [{"process": p.process, "pct": p.pct} for p in fp.processes],
        "roast_levels": [{"roast_level": r.roast_level, "pct": r.pct} for r in fp.roast_levels],
        "flavour_families": [{"label": f.label, "count": f.count} for f in fp.flavour_families],
        "origins": [{"country": o.country, "count": o.count} for o in fp.origins],
    }

    data = build_roaster_data(fp_dict)
    key = _cache_key("roaster_style", data)
    cached = _cache_get(key)
    source = "cache" if cached else ("llm" if settings.ANTHROPIC_API_KEY else "rules")

    text = await explain("roaster_style", data, api_key=settings.ANTHROPIC_API_KEY)
    return ExplanationResponse(explanation=text, source=source)


@router.get("/explain/search", response_model=ExplanationResponse)
async def explain_search_match(
    q: str = Query(...),
    coffee_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    try:
        bean_uuid = _uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if not bean:
        raise HTTPException(status_code=404, detail="Coffee not found")

    data = build_search_match_data(q, {
        "canonical_name": bean.canonical_name,
        "origin_country": bean.origin_country,
        "process": _ev(bean.process),
        "roast_level": _ev(bean.roast_level),
        "flavour_notes": bean.flavour_notes or [],
    })

    key = _cache_key("search_match", data)
    cached = _cache_get(key)
    source = "cache" if cached else ("llm" if settings.ANTHROPIC_API_KEY else "rules")

    text = await explain("search_match", data, api_key=settings.ANTHROPIC_API_KEY)
    return ExplanationResponse(explanation=text, source=source)
