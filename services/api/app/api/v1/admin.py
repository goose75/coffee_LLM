"""
Admin API v1 router — full implementation.
Sources, ingestion runs, triggering ingestion, extractions, review, mappings, beans.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi.responses import Response
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.enums import MappingType
from app.models.ingestion_run import IngestionRun
from app.models.resolution import NormalisationMapping
from app.models.store import Store
from app.schemas.ingestion import IngestionRunItem, PaginatedIngestionRuns
from app.schemas.normalisation import (
    MappingCreate,
    MappingItem,
    MappingUpdate,
    NormaliseRequest,
    NormaliseResponse,
    PaginatedMappings,
    VocabSummary,
    VALID_MAPPING_TYPES,
    VALID_NORMALISED_VALUES,
)
from app.services.normalisation import CoffeeNormaliser
from app.schemas.sources import (
    ImportReport,
    PaginatedStores,
    StoreDetail,
    StoreDetectionSummary,
    StoreListItem,
)
from app.services.source_inventory import SourceInventoryImporter

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sources", response_model=PaginatedStores)
async def list_sources(
    active_only: bool = Query(True),
    parser_strategy: str | None = Query(None),
    source_type: str | None = Query(None),
    roaster_only: bool = Query(False),
    uk_region: str | None = Query(None),
    health_status: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedStores:
    """List all tracked source domains with health status and filters."""
    stmt = select(Store)
    if active_only:
        stmt = stmt.where(Store.active_flag == True)  # noqa: E712
    if parser_strategy:
        stmt = stmt.where(Store.parser_strategy == parser_strategy)
    if source_type:
        stmt = stmt.where(Store.source_type == source_type)
    if roaster_only:
        stmt = stmt.where(Store.roaster_flag == True)  # noqa: E712
    if uk_region:
        stmt = stmt.where(Store.uk_region.ilike(f"%{uk_region}%"))
    if q:
        stmt = stmt.where(or_(Store.name.ilike(f"%{q}%"), Store.domain.ilike(f"%{q}%")))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Store.name).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    items = [StoreListItem.model_validate(s) for s in rows]

    if health_status:
        items = [i for i in items if i.health_status == health_status]
        total = len(items)

    return PaginatedStores(
        data=items, total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
        filters_applied={k: v for k, v in {
            "active_only": active_only, "parser_strategy": parser_strategy,
            "source_type": source_type, "roaster_only": roaster_only,
            "uk_region": uk_region, "health_status": health_status, "q": q,
        }.items() if v is not None and v is not False},
    )


@router.get("/sources/{source_id}", response_model=StoreDetail)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)) -> StoreDetail:
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    stmt = select(Store).where(Store.id == store_uuid).options(selectinload(Store.source_pages))
    store = (await db.execute(stmt)).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return StoreDetail.model_validate(store)


@router.post("/sources/{source_id}/rescan", response_model=StoreDetectionSummary)
async def rescan_source(source_id: str, db: AsyncSession = Depends(get_db)) -> StoreDetectionSummary:
    """Re-run domain detection and update parser_strategy for a store."""
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    importer = SourceInventoryImporter(session=db)
    result = await importer.rescan_store(store)
    return StoreDetectionSummary(**result)


@router.post("/sources/{source_id}/ingest")
async def trigger_ingestion(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger a Shopify ingestion run for a store.
    Only works for stores with parser_strategy=shopify.
    Runs synchronously in the request for now (Phase 2 moves this to a worker queue).
    """
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    if store.parser_strategy.value != "shopify":
        raise HTTPException(
            status_code=422,
            detail=f"Store parser_strategy is '{store.parser_strategy.value}', not 'shopify'",
        )

    from app.services.shopify import ShopifyIngestionPipeline
    pipeline = ShopifyIngestionPipeline(session=db, store=store)
    run = await pipeline.run()

    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "records_seen": run.records_seen,
        "records_created": run.records_created,
        "records_updated": run.records_updated,
        "records_unchanged": run.records_unchanged,
        "errors": len(run.errors),
        "warnings": len(run.warnings),
    }


@router.post("/sources/import/csv", response_model=ImportReport)
async def import_csv(
    file: Annotated[UploadFile, File()],
    db: AsyncSession = Depends(get_db),
) -> ImportReport:
    content = await file.read()
    text_content = content.decode("utf-8", errors="replace")
    importer = SourceInventoryImporter(session=db)
    report = await importer.import_csv_content(text_content)
    return ImportReport(**report)


@router.post("/sources/import/seed", response_model=ImportReport)
async def import_seed(db: AsyncSession = Depends(get_db)) -> ImportReport:
    seed_path = Path(__file__).parent.parent.parent.parent / "data" / "uk_roasters_seed.csv"
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail=f"Seed file not found at {seed_path}")
    importer = SourceInventoryImporter(session=db)
    report = await importer.import_csv_file(seed_path)
    return ImportReport(**report)


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion Runs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ingestion-runs", response_model=PaginatedIngestionRuns)
async def list_ingestion_runs(
    store_id: str | None = Query(None),
    status: str | None = Query(None),
    run_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedIngestionRuns:
    """List ingestion run history, newest first."""
    stmt = select(IngestionRun)
    if store_id:
        try:
            stmt = stmt.where(IngestionRun.store_id == uuid.UUID(store_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid store_id UUID")
    if status:
        stmt = stmt.where(IngestionRun.status == status)
    if run_type:
        stmt = stmt.where(IngestionRun.run_type == run_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(IngestionRun.started_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedIngestionRuns(
        data=[IngestionRunItem.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/ingestion-runs/{run_id}", response_model=IngestionRunItem)
async def get_ingestion_run(run_id: str, db: AsyncSession = Depends(get_db)) -> IngestionRunItem:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    run = (await db.execute(select(IngestionRun).where(IngestionRun.id == run_uuid))).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return IngestionRunItem.model_validate(run)


# ─────────────────────────────────────────────────────────────────────────────
# Extractions, Review, Mappings, Beans (stubs for future phases)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/extractions/failures")
async def list_extraction_failures(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    return {"data": [], "total": 0, "page": page, "page_size": page_size, "has_next": False}

@router.get("/extractions/{extraction_id}")
async def get_extraction(extraction_id: str, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=404, detail="Not found")

from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.resolution import CanonicalMatch
from app.schemas.matching import (
    CanonicalMatchItem,
    BeanListingSummary,
    CanonicalBeanSummary,
    PaginatedMatches,
    ReviewActionRequest,
    MatchActionResponse,
    MatchDecisionSchema,
)
from app.services.matching import CanonicalMatchingService

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Match Review
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/review/matches", response_model=PaginatedMatches)
async def list_review_matches(
    status: str = Query("pending", description="pending | accepted | rejected | skipped | all"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    max_confidence: float = Query(1.0, ge=0.0, le=1.0),
    match_method: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedMatches:
    """
    List canonical match decisions with filtering.
    Default: pending matches only (the review queue).
    """
    stmt = select(CanonicalMatch)

    if status != "all":
        stmt = stmt.where(CanonicalMatch.review_status == status)
    if min_confidence > 0:
        stmt = stmt.where(CanonicalMatch.confidence_score >= min_confidence)
    if max_confidence < 1.0:
        stmt = stmt.where(CanonicalMatch.confidence_score <= max_confidence)
    if match_method:
        stmt = stmt.where(CanonicalMatch.match_method == match_method)

    # Count pending for badge
    pending_count_row = await db.execute(
        select(func.count()).select_from(
            select(CanonicalMatch).where(CanonicalMatch.review_status == "pending").subquery()
        )
    )
    pending_count = pending_count_row.scalar_one()

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(CanonicalMatch.confidence_score.desc(), CanonicalMatch.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    # Hydrate listing and canonical for each match
    items: list[CanonicalMatchItem] = []
    for match in rows:
        item = CanonicalMatchItem.model_validate(match)

        listing = await db.get(BeanListing, match.bean_listing_id)
        if listing:
            item.bean_listing = BeanListingSummary.model_validate(listing)

        canonical = await db.get(CanonicalBean, match.proposed_canonical_bean_id)
        if canonical:
            item.proposed_canonical_bean = CanonicalBeanSummary.model_validate(canonical)

        items.append(item)

    return PaginatedMatches(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        pending_count=pending_count,
    )


@router.get("/review/matches/{match_id}", response_model=CanonicalMatchItem)
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)) -> CanonicalMatchItem:
    """Get a single match with full listing and canonical bean detail."""
    try:
        match_uuid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    match = (await db.execute(
        select(CanonicalMatch).where(CanonicalMatch.id == match_uuid)
    )).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")

    item = CanonicalMatchItem.model_validate(match)
    listing = await db.get(BeanListing, match.bean_listing_id)
    if listing:
        item.bean_listing = BeanListingSummary.model_validate(listing)
    canonical = await db.get(CanonicalBean, match.proposed_canonical_bean_id)
    if canonical:
        item.proposed_canonical_bean = CanonicalBeanSummary.model_validate(canonical)

    return item


@router.post("/review/matches/{match_id}/accept", response_model=MatchActionResponse)
async def accept_match(
    match_id: str,
    body: ReviewActionRequest = ReviewActionRequest(),
    db: AsyncSession = Depends(get_db),
) -> MatchActionResponse:
    """Accept a proposed canonical match. Links listing to the canonical bean."""
    try:
        match_uuid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    service = CanonicalMatchingService(db)
    try:
        match = await service.accept_match(
            match_id=match_uuid,
            user_id=body.user_id,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MatchActionResponse(
        match_id=match.id,
        outcome="accepted",
        canonical_bean_id=match.proposed_canonical_bean_id,
        review_status=match.review_status.value,
    )


@router.post("/review/matches/{match_id}/reject", response_model=MatchActionResponse)
async def reject_match(
    match_id: str,
    body: ReviewActionRequest = ReviewActionRequest(),
    db: AsyncSession = Depends(get_db),
) -> MatchActionResponse:
    """Reject a proposed match. Listing remains unlinked."""
    try:
        match_uuid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    service = CanonicalMatchingService(db)
    try:
        match = await service.reject_match(
            match_id=match_uuid,
            user_id=body.user_id,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MatchActionResponse(
        match_id=match.id,
        outcome="rejected",
        canonical_bean_id=match.proposed_canonical_bean_id,
        review_status=match.review_status.value,
    )


@router.post("/review/run-matching/{listing_id}", response_model=MatchDecisionSchema)
async def run_matching_for_listing(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
) -> MatchDecisionSchema:
    """Trigger the matching pipeline for a single listing (admin tool)."""
    try:
        listing_uuid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    listing = await db.get(BeanListing, listing_uuid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    service = CanonicalMatchingService(db)
    decision = await service.match_listing(listing)
    await db.commit()

    return MatchDecisionSchema(
        outcome=decision.outcome,
        listing_id=decision.listing_id,
        canonical_match_id=decision.canonical_match_id,
        canonical_bean_id=decision.canonical_bean_id,
        confidence=decision.confidence,
        signals=decision.signals.to_dict() if decision.signals else None,
        error=decision.error,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Normalisation Mappings
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/mappings", response_model=PaginatedMappings)
async def list_mappings(
    mapping_type: str | None = Query(None),
    q: str | None = Query(None, description="Search raw_value or normalised_value"),
    source: str | None = Query(None, description="Filter by source: manual, rule, db, llm"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> PaginatedMappings:
    """List all normalisation mappings with filtering and pagination."""
    stmt = select(NormalisationMapping)
    if mapping_type:
        if mapping_type not in VALID_MAPPING_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid mapping_type: {mapping_type}")
        stmt = stmt.where(NormalisationMapping.mapping_type == mapping_type)
    if q:
        stmt = stmt.where(
            or_(
                NormalisationMapping.raw_value.ilike(f"%{q}%"),
                NormalisationMapping.normalised_value.ilike(f"%{q}%"),
            )
        )
    if source:
        stmt = stmt.where(NormalisationMapping.source == source)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(NormalisationMapping.mapping_type, NormalisationMapping.raw_value)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return PaginatedMappings(
        data=[MappingItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.post("/mappings", response_model=MappingItem, status_code=201)
async def create_mapping(
    body: MappingCreate,
    db: AsyncSession = Depends(get_db),
) -> MappingItem:
    """Create a new normalisation mapping. Rejects duplicates on (type, raw_value)."""
    existing = (await db.execute(
        select(NormalisationMapping).where(
            NormalisationMapping.mapping_type == body.mapping_type,
            NormalisationMapping.raw_value.ilike(body.raw_value),
        )
    )).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Mapping already exists for type='{body.mapping_type}' raw='{body.raw_value}' → '{existing.normalised_value}'",
        )

    mapping = NormalisationMapping(
        mapping_type=MappingType(body.mapping_type),
        raw_value=body.raw_value,
        normalised_value=body.normalised_value,
        confidence_score=body.confidence_score,
        source=body.source,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return MappingItem.model_validate(mapping)


@router.get("/mappings/vocab", response_model=list[VocabSummary])
async def list_vocab_summary(db: AsyncSession = Depends(get_db)) -> list[VocabSummary]:
    """Summary counts per mapping type — used in the admin UI tab bar."""
    result = []
    for mt in sorted(VALID_MAPPING_TYPES):
        count_row = await db.execute(
            select(func.count()).where(NormalisationMapping.mapping_type == mt)
        )
        count = count_row.scalar_one()
        result.append(VocabSummary(
            mapping_type=mt,
            count=count,
            valid_values=sorted(VALID_NORMALISED_VALUES.get(mt, set())),
        ))
    return result


@router.get("/mappings/{mapping_id}", response_model=MappingItem)
async def get_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)) -> MappingItem:
    try:
        mid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    row = (await db.execute(
        select(NormalisationMapping).where(NormalisationMapping.id == mid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return MappingItem.model_validate(row)


@router.patch("/mappings/{mapping_id}", response_model=MappingItem)
async def update_mapping(
    mapping_id: str,
    body: MappingUpdate,
    db: AsyncSession = Depends(get_db),
) -> MappingItem:
    """Update normalised_value, confidence, or source of an existing mapping."""
    try:
        mid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    row = (await db.execute(
        select(NormalisationMapping).where(NormalisationMapping.id == mid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")

    if body.normalised_value is not None:
        row.normalised_value = body.normalised_value
    if body.confidence_score is not None:
        row.confidence_score = body.confidence_score
    if body.source is not None:
        row.source = body.source

    await db.commit()
    await db.refresh(row)
    return MappingItem.model_validate(row)


@router.delete("/mappings/{mapping_id}", status_code=204, response_class=Response)
async def delete_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a mapping entry."""
    try:
        mid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    row = (await db.execute(
        select(NormalisationMapping).where(NormalisationMapping.id == mid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.delete(row)
    await db.commit()


@router.post("/mappings/normalise", response_model=NormaliseResponse)
async def normalise_value(
    body: NormaliseRequest,
    db: AsyncSession = Depends(get_db),
) -> NormaliseResponse:
    """
    Normalise a single raw value — useful for testing mappings in the admin UI
    before committing new entries to the dictionary.
    """
    normaliser = CoffeeNormaliser(db)
    method_map = {
        "roast_level": normaliser.normalise_roast,
        "grind": normaliser.normalise_grind,
        "process": normaliser.normalise_process,
        "country": normaliser.normalise_country,
        "region": normaliser.normalise_region,
    }
    method = method_map.get(body.mapping_type)
    if method is None:
        raise HTTPException(status_code=422, detail=f"Normalise not supported for type '{body.mapping_type}'")

    result = await method(body.raw_value)
    return NormaliseResponse(
        raw_value=result.raw,
        mapping_type=body.mapping_type,
        normalised_value=result.normalised,
        confidence=result.confidence,
        source=result.source,
        is_unknown=result.is_unknown,
    )


from app.schemas.public import CanonicalBeanItem, CanonicalBeanUpdate, PaginatedBeans

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Beans — admin CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/beans", response_model=PaginatedBeans)
async def list_canonical_beans(
    q: str | None = Query(None),
    origin_country: str | None = Query(None),
    process: str | None = Query(None),
    roast_level: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedBeans:
    """List canonical beans with optional filters. Returns all beans (not just those with listings)."""
    stmt = select(CanonicalBean)
    if q:
        stmt = stmt.where(
            or_(
                CanonicalBean.canonical_name.ilike(f"%{q}%"),
                CanonicalBean.origin_country.ilike(f"%{q}%"),
                CanonicalBean.farm_or_estate.ilike(f"%{q}%"),
            )
        )
    if origin_country:
        stmt = stmt.where(CanonicalBean.origin_country.ilike(f"%{origin_country}%"))
    if process:
        stmt = stmt.where(CanonicalBean.process == process)
    if roast_level:
        stmt = stmt.where(CanonicalBean.roast_level == roast_level)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(CanonicalBean.data_completeness_score.desc(), CanonicalBean.canonical_name).offset((page - 1) * page_size).limit(page_size)
    beans = (await db.execute(stmt)).scalars().all()

    return PaginatedBeans(
        data=[CanonicalBeanItem.model_validate(b) for b in beans],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/beans/{bean_id}", response_model=CanonicalBeanItem)
async def get_canonical_bean(bean_id: str, db: AsyncSession = Depends(get_db)) -> CanonicalBeanItem:
    try:
        bean_uuid = uuid.UUID(bean_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    bean = (await db.execute(select(CanonicalBean).where(CanonicalBean.id == bean_uuid))).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Canonical bean not found")
    return CanonicalBeanItem.model_validate(bean)


@router.patch("/beans/{bean_id}", response_model=CanonicalBeanItem)
async def update_canonical_bean(
    bean_id: str,
    body: CanonicalBeanUpdate,
    db: AsyncSession = Depends(get_db),
) -> CanonicalBeanItem:
    """Update editable fields on a canonical bean. Recomputes completeness score."""
    try:
        bean_uuid = uuid.UUID(bean_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    bean = (await db.execute(select(CanonicalBean).where(CanonicalBean.id == bean_uuid))).scalar_one_or_none()
    if bean is None:
        raise HTTPException(status_code=404, detail="Canonical bean not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Handle enum coercion for process and roast_level
        if field == "process" and value is not None:
            from app.models.enums import Process
            try:
                value = Process(value)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid process: {value}")
        if field == "roast_level" and value is not None:
            from app.models.enums import RoastLevel
            try:
                value = RoastLevel(value)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid roast_level: {value}")
        setattr(bean, field, value)

    # Recompute completeness
    bean.data_completeness_score = bean.compute_completeness()

    await db.commit()
    await db.refresh(bean)
    return CanonicalBeanItem.model_validate(bean)
