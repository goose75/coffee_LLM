"""
Taste intelligence API router.

Public endpoints (prefix /api/v1):
  GET /coffees/{id}/taste-profile   — structured flavour tags + family breakdown
  GET /coffees/{id}/similar         — similar coffees by taste overlap
  GET /taste/distribution           — family distribution aggregated by origin/process

Admin endpoints (prefix /api/v1/admin):
  GET  /taste/review                — low-confidence tags pending human review
  POST /taste/review/{tag_id}/accept
  POST /taste/review/{tag_id}/reject
  POST /taste/tag-bean/{bean_id}    — trigger normalisation for one bean
  POST /taste/tag-all               — bulk trigger for all beans
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.canonical_bean import CanonicalBean
from app.models.enums import ReviewStatus
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from pydantic import BaseModel
from app.schemas.taste import (
    FamilyDistribution,
    FamilyDistributionRow,
    FlavorFamilySummary,
    SimilarCoffee,
    TasteProfile,
    TagReviewItem,
    TaggedNote,
)
from app.services.taste.service import TasteTaggingService

public_router = APIRouter()
admin_router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ev(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


async def _load_taxonomy_tree(session: AsyncSession) -> dict[str, FlavourTaxonomy]:
    rows = (await session.execute(select(FlavourTaxonomy))).scalars().all()
    return {str(n.id): n for n in rows}


# ── Public: taste profile ──────────────────────────────────────────────────────

@public_router.get("/coffees/{coffee_id}/taste-profile", response_model=TasteProfile)
async def get_taste_profile(
    coffee_id: str,
    db: AsyncSession = Depends(get_db),
) -> TasteProfile:
    """
    Structured flavour profile for a canonical bean.
    Returns accepted tags grouped by family, plus raw notes preserved.
    If no tags exist yet, falls back to raw flavour_notes with no structure.
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

    # Fetch accepted tags with taxonomy nodes
    tag_rows = (await db.execute(
        select(BeanFlavourTag, FlavourTaxonomy)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id == bean_uuid,
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
        .order_by(FlavourTaxonomy.depth.desc(), BeanFlavourTag.confidence.desc())
    )).all()

    taxonomy_map = await _load_taxonomy_tree(db)

    # Group by family
    families: dict[str, dict] = {}
    for tag, tax_node in tag_rows:
        slug = tax_node.slug
        family_slug = slug.split(".")[0]
        family_node = next(
            (n for n in taxonomy_map.values() if n.slug == family_slug and n.depth == 0),
            None,
        )
        if family_slug not in families:
            families[family_slug] = {
                "family_slug": family_slug,
                "family_label": family_node.label if family_node else family_slug.title(),
                "colour": family_node.colour if family_node else "#9a9080",
                "tags": [],
            }
        families[family_slug]["tags"].append(TaggedNote(
            raw_note=tag.raw_note,
            slug=tax_node.slug,
            label=tax_node.label,
            confidence=tag.confidence,
            source=tag.source,
        ))

    family_summaries = [
        FlavorFamilySummary(
            family_slug=v["family_slug"],
            family_label=v["family_label"],
            colour=v["colour"],
            tags=v["tags"],
            weight=len(v["tags"]),
        )
        for v in sorted(families.values(), key=lambda x: -len(x["tags"]))
    ]

    has_tags = len(tag_rows) > 0
    return TasteProfile(
        bean_id=bean.id,
        canonical_name=bean.canonical_name,
        raw_notes=list(bean.flavour_notes or []),
        families=family_summaries,
        has_structured_tags=has_tags,
        tag_count=len(tag_rows),
    )


# ── Public: similar coffees by taste ──────────────────────────────────────────

@public_router.get("/coffees/{coffee_id}/similar", response_model=list[SimilarCoffee])
async def get_similar_coffees(
    coffee_id: str,
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[SimilarCoffee]:
    """
    Return coffees with the most overlapping accepted flavour tags.
    Scored by Jaccard similarity on family slugs.
    """
    try:
        bean_uuid = uuid.UUID(coffee_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    # Fetch this bean's accepted tag slugs (family level)
    this_tags = (await db.execute(
        select(FlavourTaxonomy.slug)
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id == bean_uuid,
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
    )).scalars().all()

    if not this_tags:
        return []

    # Get family slugs for this bean
    this_families = {slug.split(".")[0] for slug in this_tags}

    # Fetch all other beans with tags
    all_tags = (await db.execute(
        select(BeanFlavourTag.bean_id, FlavourTaxonomy.slug)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id != bean_uuid,
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
    )).all()

    if not all_tags:
        return []

    # Compute Jaccard per bean
    bean_families: dict[uuid.UUID, set[str]] = defaultdict(set)
    for tag_bean_id, slug in all_tags:
        bean_families[tag_bean_id].add(slug.split(".")[0])

    scores: list[tuple[uuid.UUID, float]] = []
    for other_id, other_families in bean_families.items():
        intersection = len(this_families & other_families)
        union = len(this_families | other_families)
        if union > 0:
            scores.append((other_id, intersection / union))

    scores.sort(key=lambda x: -x[1])
    top_ids = [bid for bid, _ in scores[:limit]]

    if not top_ids:
        return []

    # Fetch bean metadata
    beans = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id.in_(top_ids))
    )).scalars().all()

    bean_map = {b.id: b for b in beans}
    score_map = {bid: sc for bid, sc in scores}

    result = []
    for bid in top_ids:
        b = bean_map.get(bid)
        if b is None:
            continue
        shared = this_families & bean_families.get(bid, set())
        result.append(SimilarCoffee(
            bean_id=b.id,
            canonical_name=b.canonical_name,
            origin_country=b.origin_country,
            process=_ev(b.process) if b.process else None,
            roast_level=_ev(b.roast_level) if b.roast_level else None,
            flavour_notes=list(b.flavour_notes or []),
            similarity_score=round(score_map[bid], 3),
            shared_families=sorted(shared),
        ))

    return result


# ── Public: family distribution ────────────────────────────────────────────────

@public_router.get("/taste/distribution", response_model=FamilyDistribution)
async def get_taste_distribution(
    dimension: str = Query("origin_country", description="origin_country | process | roast_level"),
    db: AsyncSession = Depends(get_db),
) -> FamilyDistribution:
    """
    Aggregate flavour family counts segmented by a dimension.
    Useful for showing 'Ethiopian coffees are predominantly floral + fruity'.
    """
    VALID = {"origin_country", "process", "roast_level"}
    if dimension not in VALID:
        raise HTTPException(status_code=422, detail=f"dimension must be one of {sorted(VALID)}")

    rows = (await db.execute(
        select(BeanFlavourTag, FlavourTaxonomy, CanonicalBean)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .join(CanonicalBean, BeanFlavourTag.bean_id == CanonicalBean.id)
        .where(BeanFlavourTag.review_status == ReviewStatus.accepted)
    )).all()

    # group: dimension_value → family_slug → count
    dist: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for tag, tax, bean in rows:
        if dimension == "origin_country":
            dim_val = bean.origin_country or "Unknown"
        elif dimension == "process":
            dim_val = _ev(bean.process) if bean.process else "unknown"
        else:
            dim_val = _ev(bean.roast_level) if bean.roast_level else "unknown"

        family = tax.slug.split(".")[0]
        dist[dim_val][family] += 1

    result_rows = []
    for dim_val, family_counts in sorted(dist.items()):
        total = sum(family_counts.values())
        result_rows.append(FamilyDistributionRow(
            dimension_value=dim_val,
            family_counts=dict(family_counts),
            total_tags=total,
        ))

    return FamilyDistribution(dimension_type=dimension, rows=result_rows)


# ── Admin: review queue ────────────────────────────────────────────────────────

@admin_router.get("/taste/review", response_model=list[TagReviewItem])
async def list_taste_review(
    min_confidence: float = Query(0.0),
    max_confidence: float = Query(0.70),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[TagReviewItem]:
    """Low-confidence LLM-generated tags awaiting human review."""
    tags = (await db.execute(
        select(BeanFlavourTag, FlavourTaxonomy, CanonicalBean)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .join(CanonicalBean, BeanFlavourTag.bean_id == CanonicalBean.id)
        .where(
            BeanFlavourTag.review_status == ReviewStatus.pending,
            BeanFlavourTag.confidence >= min_confidence,
            BeanFlavourTag.confidence <= max_confidence,
        )
        .order_by(BeanFlavourTag.confidence.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all()

    return [
        TagReviewItem(
            tag_id=tag.id,
            bean_id=tag.bean_id,
            bean_name=bean.canonical_name,
            raw_note=tag.raw_note,
            slug=tax.slug,
            label=tax.label,
            confidence=tag.confidence,
            source=tag.source,
            review_status=_ev(tag.review_status),
            llm_audit=tag.llm_audit,
            created_at=tag.created_at,
        )
        for tag, tax, bean in tags
    ]


@admin_router.post("/taste/review/{tag_id}/accept")
async def accept_taste_tag(tag_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        tag_uuid = uuid.UUID(tag_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    tag = (await db.execute(
        select(BeanFlavourTag).where(BeanFlavourTag.id == tag_uuid)
    )).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.review_status = ReviewStatus.accepted
    await db.commit()
    return {"accepted": True, "tag_id": str(tag_uuid)}


@admin_router.post("/taste/review/{tag_id}/reject")
async def reject_taste_tag(tag_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        tag_uuid = uuid.UUID(tag_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    tag = (await db.execute(
        select(BeanFlavourTag).where(BeanFlavourTag.id == tag_uuid)
    )).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.review_status = ReviewStatus.rejected
    await db.commit()
    return {"rejected": True, "tag_id": str(tag_uuid)}


@admin_router.post("/taste/tag-bean/{bean_id}")
async def trigger_tag_bean(
    bean_id: str,
    use_llm: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger taste normalisation for a single bean."""
    try:
        bean_uuid = uuid.UUID(bean_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    bean = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id == bean_uuid)
    )).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Bean not found")
    svc = TasteTaggingService(db)
    result = await svc.tag_bean(bean, use_llm=use_llm)
    await db.commit()
    return {
        "bean_id": str(bean_uuid),
        "total_notes": result.total_notes,
        "rule_matched": result.rule_matched,
        "llm_matched": result.llm_matched,
        "unmatched": result.unmatched,
        "tags_upserted": result.tags_upserted,
    }


@admin_router.post("/taste/tag-all")
async def trigger_tag_all(
    background_tasks: BackgroundTasks,
    use_llm: bool = Query(False, description="Set True to enable LLM for unmatched notes"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger rule-based taste normalisation for all beans (LLM opt-in)."""
    svc = TasteTaggingService(db)
    results = await svc.tag_all_beans(use_llm=use_llm)
    total_upserted = sum(r.tags_upserted for r in results)
    return {
        "beans_processed": len(results),
        "total_tags_upserted": total_upserted,
        "use_llm": use_llm,
    }


# ── Flavour Atlas ─────────────────────────────────────────────────────────────

class AtlasNode(BaseModel):
    slug: str
    label: str
    depth: int
    colour: str
    coffee_count: int
    children: list["AtlasNode"] = []

class AtlasResponse(BaseModel):
    families: list[AtlasNode]
    total_coffees: int

@public_router.get("/taste/atlas", response_model=AtlasResponse)
async def get_flavour_atlas(db: AsyncSession = Depends(get_db)) -> AtlasResponse:
    """
    Return the full flavour taxonomy tree annotated with coffee counts.
    Used by the Flavour Atlas page to build the interactive graph.
    Each node includes how many canonical beans have at least one tag in that subtree.
    """
    # Load full taxonomy
    tax_rows = (await db.execute(
        select(FlavourTaxonomy).order_by(FlavourTaxonomy.depth, FlavourTaxonomy.sort_order)
    )).scalars().all()

    tax_by_slug: dict[str, FlavourTaxonomy] = {t.slug: t for t in tax_rows}

    # Count distinct beans per taxonomy node (accepted tags only)
    count_rows = (await db.execute(
        select(FlavourTaxonomy.slug, func.count(func.distinct(BeanFlavourTag.bean_id)))
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(BeanFlavourTag.review_status == ReviewStatus.accepted)
        .group_by(FlavourTaxonomy.slug)
    )).all()

    # Direct counts per slug
    direct_counts: dict[str, int] = {slug: count for slug, count in count_rows}

    # Bubble counts up to parents — a family's count = union of beans tagged anywhere in subtree
    # We need distinct bean_ids per family subtree
    family_bean_sets: dict[str, set] = defaultdict(set)
    cat_bean_sets: dict[str, set] = defaultdict(set)

    tag_bean_rows = (await db.execute(
        select(FlavourTaxonomy.slug, BeanFlavourTag.bean_id)
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(BeanFlavourTag.review_status == ReviewStatus.accepted)
    )).all()

    for slug, bean_id in tag_bean_rows:
        parts = slug.split(".")
        family_bean_sets[parts[0]].add(bean_id)
        if len(parts) >= 2:
            cat_bean_sets[f"{parts[0]}.{parts[1]}"].add(bean_id)

    # Build node tree
    families = [t for t in tax_rows if t.depth == 0]
    categories = [t for t in tax_rows if t.depth == 1]
    tags = [t for t in tax_rows if t.depth == 2]

    result_families: list[AtlasNode] = []
    for fam in families:
        fam_node = AtlasNode(
            slug=fam.slug,
            label=fam.label,
            depth=0,
            colour=fam.colour or "#888",
            coffee_count=len(family_bean_sets.get(fam.slug, set())),
        )
        for cat in [c for c in categories if c.slug.startswith(fam.slug + ".")]:
            cat_node = AtlasNode(
                slug=cat.slug,
                label=cat.label,
                depth=1,
                colour=cat.colour or fam.colour or "#888",
                coffee_count=len(cat_bean_sets.get(cat.slug, set())),
            )
            for tag in [t for t in tags if t.slug.startswith(cat.slug + ".")]:
                cat_node.children.append(AtlasNode(
                    slug=tag.slug,
                    label=tag.label,
                    depth=2,
                    colour=tag.colour or fam.colour or "#888",
                    coffee_count=direct_counts.get(tag.slug, 0),
                ))
            fam_node.children.append(cat_node)
        # Family with no categories — tags hang directly
        if not fam_node.children:
            for tag in [t for t in tags if t.slug.startswith(fam.slug + ".")]:
                fam_node.children.append(AtlasNode(
                    slug=tag.slug,
                    label=tag.label,
                    depth=2,
                    colour=tag.colour or fam.colour or "#888",
                    coffee_count=direct_counts.get(tag.slug, 0),
                ))
        result_families.append(fam_node)

    total = len(set().union(*family_bean_sets.values())) if family_bean_sets else 0
    return AtlasResponse(families=result_families, total_coffees=total)


@public_router.get("/taste/atlas/coffees")
async def get_atlas_coffees(
    slugs: str = Query(..., description="Comma-separated flavour slugs to filter by"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=48),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return coffees matching any of the given flavour slugs.
    Slug can be a family (fruity), category (fruity.citrus), or tag (fruity.citrus.lemon).
    A family slug matches all coffees with any tag in that family.
    """
    slug_list = [s.strip() for s in slugs.split(",") if s.strip()]

    # Find all taxonomy node IDs whose slug starts with any of the requested slugs
    all_tax = (await db.execute(select(FlavourTaxonomy))).scalars().all()
    matching_tax_ids = [
        t.id for t in all_tax
        if any(t.slug == s or t.slug.startswith(s + ".") for s in slug_list)
    ]

    if not matching_tax_ids:
        return {"data": [], "total": 0, "page": page, "page_size": page_size, "has_next": False}

    # Find beans with accepted tags in any of these taxonomy nodes
    bean_id_rows = (await db.execute(
        select(func.distinct(BeanFlavourTag.bean_id))
        .where(
            BeanFlavourTag.taxonomy_id.in_(matching_tax_ids),
            BeanFlavourTag.review_status == ReviewStatus.accepted,
        )
    )).scalars().all()

    total = len(bean_id_rows)
    paged_ids = bean_id_rows[(page - 1) * page_size: page * page_size]

    if not paged_ids:
        return {"data": [], "total": total, "page": page, "page_size": page_size, "has_next": False}

    beans = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.id.in_(paged_ids))
    )).scalars().all()

    # Gather matched flavour slugs per bean for display
    bean_tag_rows = (await db.execute(
        select(BeanFlavourTag.bean_id, FlavourTaxonomy.slug, FlavourTaxonomy.label)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(BeanFlavourTag.bean_id.in_(paged_ids), BeanFlavourTag.review_status == ReviewStatus.accepted)
    )).all()

    bean_tags: dict = defaultdict(list)
    for bid, slug, label in bean_tag_rows:
        bean_tags[bid].append({"slug": slug, "label": label})

    data = [
        {
            "id": str(b.id),
            "canonical_name": b.canonical_name,
            "origin_country": b.origin_country,
            "origin_region": b.origin_region,
            "process": b.process.value if b.process else None,
            "roast_level": b.roast_level.value if b.roast_level else None,
            "flavour_notes": b.flavour_notes,
            "data_completeness_score": b.data_completeness_score,
            "matched_tags": bean_tags.get(b.id, []),
        }
        for b in beans
    ]

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }
