"""
search.py — Natural language search API endpoint.

POST /api/v1/search/interpret
  Accepts a natural language query, returns ParsedQuery + ranked coffees.

GET  /api/v1/search/suggest
  Returns quick suggestions for the search box autocomplete.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.canonical_bean import CanonicalBean
from app.models.bean_listing import BeanListing
from app.models.pricing import ListingVariant
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.enums import ReviewStatus
from app.services.search.query_parser import ParsedQuery, parse_async, parse_rules

logger = logging.getLogger("app.api.search")

router = APIRouter(prefix="/search", tags=["search"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 12
    use_llm: bool = True


class CoffeeMatch(BaseModel):
    id: str
    canonical_name: str
    origin_country: str | None
    origin_region: str | None
    process: str | None
    roast_level: str | None
    flavour_notes: list[str]
    min_price_gbp: float | None
    listing_count: int
    data_completeness_score: float
    match_score: float
    match_reasons: list[str]


class SearchResponse(BaseModel):
    query: str
    parsed: dict
    summary: str
    source: str
    results: list[CoffeeMatch]
    total: int
    page: int
    page_size: int
    has_next: bool


# ── Ranking logic ─────────────────────────────────────────────────────────────

def score_coffee(bean: CanonicalBean, pq: ParsedQuery,
                 min_price: float | None, listing_count: int) -> tuple[float, list[str]]:
    """
    Score a coffee against a parsed query. Returns (score, reasons).

    Scoring is purely data-driven — no LLM involvement.
    """
    score = 0.0
    reasons: list[str] = []

    # ── Flavour note matches ──────────────────────────────────────────────────
    if pq.flavour_notes and bean.flavour_notes:
        bean_notes_lower = [n.lower() for n in bean.flavour_notes]
        for note in pq.flavour_notes:
            note_lower = note.lower()
            for bn in bean_notes_lower:
                if note_lower in bn or bn in note_lower:
                    score += 2.0
                    reasons.append(f"{note} notes")
                    break

    # ── Roast level match ─────────────────────────────────────────────────────
    if pq.roast_level and bean.roast_level:
        bean_roast = bean.roast_level.value if hasattr(bean.roast_level, "value") else str(bean.roast_level)
        if bean_roast == pq.roast_level:
            score += 3.0
            reasons.append(f"{pq.roast_level} roast")
        elif abs(["light","medium","dark"].index(pq.roast_level) -
                 ["light","medium","dark"].index(bean_roast)) == 1:
            score += 0.5  # adjacent roast level

    # ── Process match ─────────────────────────────────────────────────────────
    if pq.process and bean.process:
        bean_process = bean.process.value if hasattr(bean.process, "value") else str(bean.process)
        if bean_process == pq.process:
            score += 2.5
            reasons.append(f"{pq.process} process")

    # ── Origin match ──────────────────────────────────────────────────────────
    if pq.origin_country and bean.origin_country:
        if pq.origin_country.lower() in bean.origin_country.lower():
            score += 4.0
            reasons.append(f"from {bean.origin_country}")
    if pq.origin_region and bean.origin_region:
        if pq.origin_region.lower() in bean.origin_region.lower():
            score += 2.0
            reasons.append(f"{bean.origin_region} region")

    # ── Brew method ───────────────────────────────────────────────────────────
    if pq.espresso_suitable is True and bean.espresso_suitable_flag:
        score += 2.0
        reasons.append("espresso suitable")
    if pq.filter_suitable is True and bean.filter_suitable_flag:
        score += 2.0
        reasons.append("filter suitable")

    # ── Body signal boosts ────────────────────────────────────────────────────
    if pq.body_signal in ("full", "syrupy"):
        # Natural and honey processes tend to be fuller-bodied
        bean_process = (bean.process.value if hasattr(bean.process, "value") else str(bean.process or ""))
        if bean_process in ("natural", "honey"):
            score += 1.0
    elif pq.body_signal in ("light", "clean"):
        bean_process = (bean.process.value if hasattr(bean.process, "value") else str(bean.process or ""))
        if bean_process == "washed":
            score += 1.0

    # ── Acidity signal boosts ─────────────────────────────────────────────────
    if pq.acidity_signal in ("bright", "juicy", "clean"):
        if bean.origin_country in ("Ethiopia", "Kenya"):
            score += 1.0
    elif pq.acidity_signal == "low":
        if bean.origin_country in ("Brazil", "Indonesia"):
            score += 1.0

    # ── Data completeness bonus ───────────────────────────────────────────────
    score += bean.data_completeness_score * 0.5

    # ── Availability bonus ────────────────────────────────────────────────────
    if listing_count > 0:
        score += min(listing_count * 0.1, 0.5)

    return score, list(dict.fromkeys(reasons))  # deduplicate while preserving order


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/interpret", response_model=SearchResponse)
async def interpret_search(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Parse a natural language query and return ranked coffees.
    """
    query = req.query.strip()

    # Parse query
    if req.use_llm and query:
        pq = await parse_async(query)
    else:
        pq = parse_rules(query) if query else ParsedQuery(summary="Showing all coffees")

    logger.info(
        "search query=%r source=%s roast=%s process=%s origin=%s price=(%s-%s) flavours=%s",
        query, pq.source, pq.roast_level, pq.process,
        pq.origin_country, pq.min_price, pq.max_price, pq.flavour_notes
    )

    # Build DB query
    stmt = (
        select(CanonicalBean)
        .join(BeanListing, BeanListing.canonical_bean_id == CanonicalBean.id)
        .where(BeanListing.active_flag.is_(True))
        .distinct()
    )

    # Apply hard filters
    if pq.origin_country:
        stmt = stmt.where(CanonicalBean.origin_country.ilike(f"%{pq.origin_country}%"))
    if pq.origin_region:
        stmt = stmt.where(CanonicalBean.origin_region.ilike(f"%{pq.origin_region}%"))
    if pq.roast_level:
        stmt = stmt.where(CanonicalBean.roast_level == pq.roast_level)
    if pq.process:
        stmt = stmt.where(CanonicalBean.process == pq.process)
    if pq.espresso_suitable is True:
        stmt = stmt.where(CanonicalBean.espresso_suitable_flag.is_(True))
    if pq.filter_suitable is True:
        stmt = stmt.where(CanonicalBean.filter_suitable_flag.is_(True))
    if pq.decaf is True:
        stmt = stmt.where(CanonicalBean.decaf_flag.is_(True))

    # Price filter — only apply if explicitly requested
    if pq.min_price is not None or pq.max_price is not None:
        stmt = stmt.join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
        if pq.min_price is not None:
            stmt = stmt.where(ListingVariant.price_gbp >= pq.min_price)
        if pq.max_price is not None:
            stmt = stmt.where(ListingVariant.price_gbp <= pq.max_price)

    beans = (await db.execute(stmt)).scalars().all()

    # Get listing counts and min prices
    listing_counts: dict = {}
    min_prices: dict = {}

    if beans:
        bean_ids = [b.id for b in beans]

        count_rows = (await db.execute(
            select(BeanListing.canonical_bean_id, func.count(BeanListing.id))
            .where(BeanListing.canonical_bean_id.in_(bean_ids), BeanListing.active_flag.is_(True))
            .group_by(BeanListing.canonical_bean_id)
        )).all()
        listing_counts = {bid: cnt for bid, cnt in count_rows}

        price_rows = (await db.execute(
            select(BeanListing.canonical_bean_id, func.min(ListingVariant.price_gbp))
            .join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
            .where(BeanListing.canonical_bean_id.in_(bean_ids))
            .group_by(BeanListing.canonical_bean_id)
        )).all()
        min_prices = {bid: price for bid, price in price_rows}

    # Score and rank
    scored: list[tuple[float, list[str], CanonicalBean]] = []
    for bean in beans:
        score, reasons = score_coffee(
            bean, pq,
            min_prices.get(bean.id),
            listing_counts.get(bean.id, 0)
        )
        scored.append((score, reasons, bean))

    scored.sort(key=lambda x: x[0], reverse=True)
    total = len(scored)

    # Paginate
    start = (req.page - 1) * req.page_size
    page_items = scored[start: start + req.page_size]

    results = []
    for score, reasons, bean in page_items:
        process_str = bean.process.value if hasattr(bean.process, "value") else (bean.process or None)
        roast_str = bean.roast_level.value if hasattr(bean.roast_level, "value") else (bean.roast_level or None)
        results.append(CoffeeMatch(
            id=str(bean.id),
            canonical_name=bean.canonical_name,
            origin_country=bean.origin_country,
            origin_region=bean.origin_region,
            process=process_str,
            roast_level=roast_str,
            flavour_notes=bean.flavour_notes or [],
            min_price_gbp=min_prices.get(bean.id),
            listing_count=listing_counts.get(bean.id, 0),
            data_completeness_score=bean.data_completeness_score,
            match_score=round(score, 2),
            match_reasons=reasons[:4],
        ))

    from dataclasses import asdict
    return SearchResponse(
        query=query,
        parsed=asdict(pq),
        summary=pq.summary,
        source=pq.source,
        results=results,
        total=total,
        page=req.page,
        page_size=req.page_size,
        has_next=(start + req.page_size) < total,
    )


@router.get("/suggest")
async def get_suggestions(
    q: str = Query("", description="Partial query for autocomplete"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Quick suggestions for the search box."""
    STATIC_SUGGESTIONS = [
        "something fruity and bright for V60",
        "syrupy espresso under £12",
        "chocolatey and nutty, not too dark",
        "floral Ethiopian natural",
        "clean washed Kenya",
        "juicy anaerobic with berry notes",
        "smooth Brazilian decaf",
        "light roast with citrus and floral notes",
    ]
    if not q:
        return {"suggestions": STATIC_SUGGESTIONS}
    filtered = [s for s in STATIC_SUGGESTIONS if q.lower() in s.lower()]
    return {"suggestions": filtered[:5]}
