"""
Admin API v1 router — full implementation.
Sources, ingestion runs, triggering ingestion, extractions, review, mappings, beans.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

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
    LastRunSummary,
    PaginatedStores,
    StoreDetail,
    StoreDetectionSummary,
    StoreListItem,
)
from app.services.source_inventory import SourceInventoryImporter
from app.services.error_recovery import ErrorRecoveryService
from app.api.v1 import admin_feedback

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

    # Fetch latest run per store in one query — Postgres DISTINCT ON.
    store_ids = [s.id for s in rows]
    last_runs_by_store: dict = {}
    if store_ids:
        last_run_stmt = (
            select(IngestionRun)
            .where(IngestionRun.store_id.in_(store_ids))
            .order_by(IngestionRun.store_id, desc(IngestionRun.started_at))
            .distinct(IngestionRun.store_id)
        )
        for run in (await db.execute(last_run_stmt)).scalars().all():
            last_runs_by_store[run.store_id] = run

    items: list[StoreListItem] = []
    for s in rows:
        item = StoreListItem.model_validate(s)
        run = last_runs_by_store.get(s.id)
        if run is not None:
            errors_list = list(run.errors or [])
            buckets: dict[str, int] = {}
            for e in errors_list:
                msg = (e or {}).get("message") or "unknown error"
                buckets[msg] = buckets.get(msg, 0) + 1
            item.last_run = LastRunSummary(
                id=run.id,
                status=run.status.value if hasattr(run.status, "value") else str(run.status),
                started_at=run.started_at,
                completed_at=run.completed_at,
                records_seen=run.records_seen or 0,
                records_created=run.records_created or 0,
                records_updated=run.records_updated or 0,
                error_count=len(errors_list),
                warning_count=len(run.warnings or []),
                top_errors=[(e or {}).get("message", "") for e in errors_list[:3]],
                top_error_buckets=dict(sorted(buckets.items(), key=lambda kv: -kv[1])[:5]),
            )
        items.append(item)

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


@router.patch("/sources/{source_id}", response_model=StoreListItem)
async def update_source(
    source_id: str,
    parser_strategy: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StoreListItem:
    """Update a source's parser strategy."""
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    if parser_strategy:
        # Validate parser_strategy is a valid enum value
        valid_strategies = ["shopify", "html", "schema_org", "llm", "unknown"]
        if parser_strategy not in valid_strategies:
            raise HTTPException(status_code=422, detail=f"Invalid parser_strategy. Must be one of: {', '.join(valid_strategies)}")
        store.parser_strategy = parser_strategy

    await db.commit()
    await db.refresh(store)
    return StoreListItem.model_validate(store)


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


@router.post("/sources/reingest-all")
async def reingest_all(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> dict:
    """Trigger re-ingestion of all active Shopify sources."""
    # Count active Shopify stores
    count_stmt = select(func.count()).select_from(
        select(Store).where(
            (Store.active_flag == True) & (Store.parser_strategy == "shopify")  # noqa: E712
        ).subquery()
    )
    count = (await db.execute(count_stmt)).scalar_one() or 0

    # Schedule the bulk reingest in the background
    async def run_reingest():
        stmt = select(Store).where(
            (Store.active_flag == True) & (Store.parser_strategy == "shopify")  # noqa: E712
        ).order_by(Store.name)
        stores = (await db.execute(stmt)).scalars().all()

        from app.services.shopify import ShopifyIngestionPipeline

        for store in stores:
            try:
                pipeline = ShopifyIngestionPipeline(session=db, store=store)
                await pipeline.run()
            except Exception as e:
                # Log but continue with next store
                print(f"Error ingesting {store.domain}: {e}")

    background_tasks.add_task(run_reingest)

    return {
        "status": "queued",
        "message": f"Re-ingestion queued for {count} active Shopify sources",
        "started_count": count,
    }


@router.post("/sources/{store_id}/reingest")
async def reingest_store(
    store_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger re-ingestion of a single store (supports all parser strategies)."""
    # Fetch store
    try:
        sid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid store_id UUID")

    stmt = select(Store).where(Store.id == sid)
    store = (await db.execute(stmt)).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    # Route to appropriate pipeline based on parser_strategy
    async def run_reingest():
        try:
            if store.parser_strategy == "shopify":
                from app.services.shopify import ShopifyIngestionPipeline

                pipeline = ShopifyIngestionPipeline(session=db, store=store)
                await pipeline.run()
            elif store.parser_strategy == "html":
                from app.services.html.pipeline import HtmlIngestionPipeline

                pipeline = HtmlIngestionPipeline(session=db, store=store)
                await pipeline.run()
            else:
                # For schema_org, llm, unknown: use ExtractionService via dispatcher
                # For now, just log a message
                print(
                    f"Reingest for {store.parser_strategy} not yet implemented in admin endpoint"
                )
        except Exception as e:
            print(f"Error ingesting {store.domain}: {e}")

    background_tasks.add_task(run_reingest)

    return {
        "status": "queued",
        "message": f"Re-ingestion queued for {store.domain} ({store.parser_strategy})",
        "store_id": store_id,
        "parser_strategy": store.parser_strategy,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Error Recovery & Learning (Auto-correction)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/error-recovery/analysis")
async def analyze_errors(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Analyze recent ingestion failures and identify misclassifications.

    Returns suggested corrections for stores marked with wrong parser_strategy,
    identified by error patterns in failed runs (last 24 hours).
    """
    service = ErrorRecoveryService(session=db)
    return await service.analyze_failures(hours=24)


@router.post("/error-recovery/auto-correct")
async def auto_correct_errors(
    min_confidence: float = Query(0.90, ge=0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Automatically correct misclassified sources based on error patterns.

    Only applies corrections with confidence >= min_confidence (default 0.90).

    Returns list of applied corrections.
    """
    service = ErrorRecoveryService(session=db)
    return await service.auto_correct(min_confidence=min_confidence)


@router.get("/error-recovery/summary")
async def error_recovery_summary(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Get a summary of recent errors and affected stores.

    Shows:
    - Total failures in last 24h
    - Top error patterns
    - Parser strategies of affected stores
    """
    service = ErrorRecoveryService(session=db)
    return await service.get_correction_summary()


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
    BulkEnhancementSummary,
    BulkReviewRequest,
    BulkReviewResponse,
    CanonicalMatchItem,
    BeanListingSummary,
    CanonicalBeanSummary,
    DataQualityIssue,
    DataQualityReport,
    EnhancementApplyRequest,
    EnhancementApplyResponse,
    EnhancementProposal,
    FieldCoverage,
    FieldDisagreement,
    HistogramBin,
    MergeRequest,
    MergeResult,
    PaginatedMatches,
    ReviewActionRequest,
    ReviewAnalytics,
    MatchActionResponse,
    MatchDecisionSchema,
    TopBlocker,
)
from app.services.matching import CanonicalMatchingService
from app.services.matching.enhancement import (
    apply_enhancement,
    bulk_enhance,
    propose_enhancement,
)
from app.services.matching.merge import merge_canonical_beans

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Match Review
# ─────────────────────────────────────────────────────────────────────────────


def _bin(value: float) -> tuple[float, float, str]:
    """Return (low, high, label) for the 0.1-wide bin containing value."""
    bins = [(i / 10, (i + 1) / 10) for i in range(10)]
    for lo, hi in bins:
        # last bin is inclusive on both ends
        if (lo <= value < hi) or (hi == 1.0 and value <= 1.0 and value >= lo):
            return lo, hi, f"{lo:.1f}-{hi:.1f}"
    return 0.0, 0.1, "0.0-0.1"


def _empty_histogram() -> list[dict]:
    bins = [(i / 10, (i + 1) / 10) for i in range(10)]
    return [{"bin_min": lo, "bin_max": hi, "bin_label": f"{lo:.1f}-{hi:.1f}", "count": 0}
            for lo, hi in bins]


def _add_to_histogram(hist: list[dict], value: float | None) -> None:
    if value is None:
        return
    v = max(0.0, min(1.0, float(value)))
    idx = min(int(v * 10), 9)
    hist[idx]["count"] += 1


@router.get("/review/analytics", response_model=ReviewAnalytics)
async def review_analytics(db: AsyncSession = Depends(get_db)) -> ReviewAnalytics:
    """
    Aggregate analytics over the canonical-match queue and canonical bean
    catalogue. Read-only; safe to call frequently.
    """
    # Status counts
    status_rows = await db.execute(
        select(CanonicalMatch.review_status, func.count())
        .group_by(CanonicalMatch.review_status)
    )
    counts = {str(row[0]): int(row[1]) for row in status_rows.all()}
    pending_count = counts.get("pending", 0)
    accepted_count = counts.get("accepted", 0)
    rejected_count = counts.get("rejected", 0)

    # Pull all pending matches (we need signal JSON anyway; small enough)
    pending_stmt = select(CanonicalMatch).where(CanonicalMatch.review_status == "pending")
    pending = (await db.execute(pending_stmt)).scalars().all()

    pending_hist = _empty_histogram()
    exact_hist = _empty_histogram()
    fuzzy_hist = _empty_histogram()
    embedding_hist = _empty_histogram()

    field_stats: dict[str, dict[str, int]] = {
        f: {"matched": 0, "mismatched": 0, "skipped": 0}
        for f in ("origin_country", "process", "varietal", "farm_or_estate")
    }
    method_breakdown: dict[str, int] = {}

    # Top-blocker counters
    near_miss_threshold = 0.92
    near_miss_count = 0           # combined ≥ 0.85 but < 0.92
    sparse_canonical_count = 0    # field_matches has 3+ skipped fields
    fuzzy_only_count = 0          # exact == 0 but fuzzy ≥ 0.9
    no_embedding_count = 0        # embedding_score == 0 (would have lifted combined)

    for m in pending:
        _add_to_histogram(pending_hist, m.confidence_score)
        method = str(m.match_method.value if hasattr(m.match_method, "value") else m.match_method)
        method_breakdown[method] = method_breakdown.get(method, 0) + 1

        sigs = m.match_signals_json or {}
        exact = sigs.get("exact_score")
        fuzzy = sigs.get("fuzzy_score")
        embedding = sigs.get("embedding_score")
        _add_to_histogram(exact_hist, exact)
        _add_to_histogram(fuzzy_hist, fuzzy)
        _add_to_histogram(embedding_hist, embedding)

        field_matches = sigs.get("field_matches", {}) or {}
        for fname, stats in field_stats.items():
            v = field_matches.get(fname)
            if v is True:
                stats["matched"] += 1
            elif v is False:
                stats["mismatched"] += 1
            else:
                stats["skipped"] += 1

        # Top blockers
        if m.confidence_score is not None and 0.85 <= m.confidence_score < near_miss_threshold:
            near_miss_count += 1
        skipped_fields = sum(1 for v in field_matches.values() if v is None)
        if skipped_fields >= 3:
            sparse_canonical_count += 1
        if (exact or 0) < 0.05 and (fuzzy or 0) >= 0.9:
            fuzzy_only_count += 1
        if (embedding or 0) < 0.05:
            no_embedding_count += 1

    blockers: list[TopBlocker] = []
    if near_miss_count:
        blockers.append(TopBlocker(
            label="near_miss",
            count=near_miss_count,
            description=f"{near_miss_count} matches with confidence 0.85–0.91 — one nudge away from auto-accept.",
        ))
    if no_embedding_count:
        blockers.append(TopBlocker(
            label="no_embedding",
            count=no_embedding_count,
            description=f"{no_embedding_count} matches have no embedding contribution — backfilling embeddings would lift their score.",
        ))
    if sparse_canonical_count:
        blockers.append(TopBlocker(
            label="sparse_canonical",
            count=sparse_canonical_count,
            description=f"{sparse_canonical_count} matches couldn't compare 3+ fields because the canonical bean is too sparse — Pass 4 enrichment is the fix.",
        ))
    if fuzzy_only_count:
        blockers.append(TopBlocker(
            label="fuzzy_only",
            count=fuzzy_only_count,
            description=f"{fuzzy_only_count} matches lean entirely on fuzzy title similarity with no structured-field agreement.",
        ))
    blockers.sort(key=lambda b: -b.count)

    field_coverage = [
        FieldCoverage(field=fname, **stats) for fname, stats in field_stats.items()
    ]

    # Canonical bean catalogue completeness
    bean_rows = (await db.execute(select(CanonicalBean.data_completeness_score))).all()
    catalogue_hist = _empty_histogram()
    total_score = 0.0
    for row in bean_rows:
        score = row[0] or 0.0
        _add_to_histogram(catalogue_hist, score)
        total_score += score
    canonical_bean_count = len(bean_rows)
    avg_completeness = round(total_score / canonical_bean_count, 3) if canonical_bean_count else 0.0

    return ReviewAnalytics(
        pending_count=pending_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        pending_confidence_histogram=[HistogramBin(**b) for b in pending_hist],
        exact_score_histogram=[HistogramBin(**b) for b in exact_hist],
        fuzzy_score_histogram=[HistogramBin(**b) for b in fuzzy_hist],
        embedding_score_histogram=[HistogramBin(**b) for b in embedding_hist],
        field_coverage=field_coverage,
        method_breakdown=method_breakdown,
        top_blockers=blockers,
        catalogue_completeness_histogram=[HistogramBin(**b) for b in catalogue_hist],
        canonical_bean_count=canonical_bean_count,
        avg_canonical_completeness=avg_completeness,
    )


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
        stmt
        .options(
            selectinload(CanonicalMatch.bean_listing),
            selectinload(CanonicalMatch.proposed_canonical_bean),
        )
        .order_by(CanonicalMatch.confidence_score.desc(), CanonicalMatch.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    items: list[CanonicalMatchItem] = []
    for match in rows:
        item = CanonicalMatchItem(
            id=match.id,
            bean_listing_id=match.bean_listing_id,
            proposed_canonical_bean_id=match.proposed_canonical_bean_id,
            match_method=str(match.match_method.value if hasattr(match.match_method, "value") else match.match_method),
            confidence_score=match.confidence_score,
            reviewed_by=match.reviewed_by,
            review_status=str(match.review_status.value if hasattr(match.review_status, "value") else match.review_status),
            review_notes=match.review_notes,
            reviewed_at=match.reviewed_at,
            created_at=match.created_at,
            match_signals_json=match.match_signals_json,
            bean_listing=BeanListingSummary.model_validate(match.bean_listing) if match.bean_listing else None,
            proposed_canonical_bean=CanonicalBeanSummary.model_validate(match.proposed_canonical_bean) if match.proposed_canonical_bean else None,
        )
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

    item = CanonicalMatchItem(
        id=match.id,
        bean_listing_id=match.bean_listing_id,
        proposed_canonical_bean_id=match.proposed_canonical_bean_id,
        match_method=str(match.match_method.value if hasattr(match.match_method, "value") else match.match_method),
        confidence_score=match.confidence_score,
        reviewed_by=match.reviewed_by,
        review_status=str(match.review_status.value if hasattr(match.review_status, "value") else match.review_status),
        review_notes=match.review_notes,
        reviewed_at=match.reviewed_at,
        created_at=match.created_at,
        match_signals_json=match.match_signals_json,
        bean_listing=BeanListingSummary.model_validate(match.bean_listing) if match.bean_listing else None,
        proposed_canonical_bean=CanonicalBeanSummary.model_validate(match.proposed_canonical_bean) if match.proposed_canonical_bean else None,
    )
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


@router.post("/review/matches/bulk-accept", response_model=BulkReviewResponse)
async def bulk_accept_matches(
    body: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkReviewResponse:
    """
    Bulk-accept matches. Provide either an explicit `match_ids` list OR
    filter parameters (min_confidence, max_confidence, match_method). Only
    matches currently in `pending` are affected — already-decided matches
    are returned in `skipped`.
    """
    service = CanonicalMatchingService(db)
    if body.match_ids:
        affected, skipped = await service.bulk_accept(
            match_ids=body.match_ids,
            user_id=body.user_id,
            notes=body.notes,
        )
    else:
        affected, skipped = await service.bulk_accept_by_filter(
            min_confidence=body.min_confidence,
            max_confidence=body.max_confidence,
            match_method=body.match_method,
            user_id=body.user_id,
            notes=body.notes,
            limit=body.limit,
        )
    return BulkReviewResponse(outcome="accepted", affected=affected, skipped=skipped)


@router.post("/review/matches/bulk-reject", response_model=BulkReviewResponse)
async def bulk_reject_matches(
    body: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkReviewResponse:
    """Bulk-reject matches. See bulk_accept_matches for filter semantics."""
    service = CanonicalMatchingService(db)
    if body.match_ids:
        affected, skipped = await service.bulk_reject(
            match_ids=body.match_ids,
            user_id=body.user_id,
            notes=body.notes,
        )
    else:
        affected, skipped = await service.bulk_reject_by_filter(
            min_confidence=body.min_confidence,
            max_confidence=body.max_confidence,
            match_method=body.match_method,
            user_id=body.user_id,
            notes=body.notes,
            limit=body.limit,
        )
    return BulkReviewResponse(outcome="rejected", affected=affected, skipped=skipped)


@router.get("/review/data-quality", response_model=DataQualityReport)
async def data_quality_report(
    min_listings: int = Query(2, ge=1, description="ignore canonical beans with fewer linked listings"),
    disagreement_threshold: float = Query(0.30, ge=0.0, le=1.0, description="fraction of disagreeing listings that triggers a flag"),
    duplicate_fuzzy_threshold: float = Query(0.92, ge=0.0, le=1.0),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> DataQualityReport:
    """
    Return a list of canonical-bean issues that operator review should resolve.

    Detects:
      • field_disagreement — canonical's value contradicts what most linked
        listings claim. Either the canonical is wrong or the bean should split.
      • duplicate_suspect — two canonical beans with the same origin_country
        and very similar names. Likely a matcher misfire that produced two
        identities for one bean.
      • very_sparse — canonical with completeness < 0.2; nothing for the
        matcher to grip.
      • stale_auto_accept — accepted match whose stored confidence is below
        today's review threshold (0.75). May warrant re-review.
    """
    issues: list[DataQualityIssue] = []

    # 1. Field-disagreement and very_sparse
    bean_stmt = (
        select(CanonicalBean)
        .options(selectinload(CanonicalBean.bean_listings))
        .order_by(CanonicalBean.canonical_name)
    )
    beans = (await db.execute(bean_stmt)).scalars().all()

    for bean in beans:
        listings = list(bean.bean_listings or [])
        if bean.data_completeness_score < 0.2:
            issues.append(DataQualityIssue(
                issue_type="very_sparse",
                bean_id=bean.id,
                canonical_name=bean.canonical_name,
                severity="medium",
                summary=(
                    f"Completeness {bean.data_completeness_score:.0%} — only "
                    f"{int(bean.data_completeness_score * 10)} of 10 key fields populated."
                ),
            ))

        if len(listings) < min_listings:
            continue

        # Each field maps to (canonical_value_normalised, getter_for_listing)
        comparisons = [
            ("origin_country",
             (bean.origin_country or "").strip().lower() or None,
             lambda l: (l.origin_label_raw or "").strip().lower() or None),
            ("process",
             (str(bean.process.value) if bean.process and hasattr(bean.process, "value") else (bean.process or "")).strip().lower() or None,
             lambda l: (l.process_label_raw or "").strip().lower() or None),
        ]
        disagreements: list[FieldDisagreement] = []
        for field, canonical_val, listing_getter in comparisons:
            if canonical_val is None:
                continue
            counter: dict[str, int] = {}
            considered = 0
            for l in listings:
                v = listing_getter(l)
                if v is None or v == "":
                    continue
                considered += 1
                counter[v] = counter.get(v, 0) + 1
            if considered < min_listings:
                continue
            disagreeing = considered - counter.get(canonical_val, 0)
            if disagreeing / considered >= disagreement_threshold:
                majority_value = max(counter.items(), key=lambda kv: kv[1])[0] if counter else None
                disagreements.append(FieldDisagreement(
                    field=field,
                    canonical_value=canonical_val,
                    listing_majority_value=majority_value,
                    listings_disagreeing=disagreeing,
                    total_listings=considered,
                ))
        if disagreements:
            severity = "high" if any(d.listings_disagreeing / max(d.total_listings, 1) >= 0.5 for d in disagreements) else "medium"
            summary = (
                f"{len(disagreements)} field(s) disagree with linked listings: "
                + ", ".join(
                    f"{d.field} '{d.canonical_value}' vs majority '{d.listing_majority_value}' "
                    f"({d.listings_disagreeing}/{d.total_listings})"
                    for d in disagreements
                )
            )
            issues.append(DataQualityIssue(
                issue_type="field_disagreement",
                bean_id=bean.id,
                canonical_name=bean.canonical_name,
                severity=severity,
                summary=summary,
                field_disagreements=disagreements,
            ))

    # 2. Duplicate-suspects: same origin_country + close fuzzy name
    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None  # type: ignore

    if fuzz is not None:
        seen_pairs: set[tuple] = set()
        # Bucket by origin_country to keep N-squared bounded.
        by_origin: dict[str, list[CanonicalBean]] = {}
        for b in beans:
            key = (b.origin_country or "_unknown").strip().lower()
            by_origin.setdefault(key, []).append(b)
        for bucket in by_origin.values():
            if len(bucket) < 2:
                continue
            for i, a in enumerate(bucket):
                for b in bucket[i + 1:]:
                    score = fuzz.token_set_ratio(a.canonical_name.lower(), b.canonical_name.lower()) / 100.0
                    if score >= duplicate_fuzzy_threshold:
                        pair = tuple(sorted((str(a.id), str(b.id))))
                        if pair in seen_pairs:
                            continue
                        seen_pairs.add(pair)
                        issues.append(DataQualityIssue(
                            issue_type="duplicate_suspect",
                            bean_id=a.id,
                            canonical_name=a.canonical_name,
                            severity="high",
                            summary=(
                                f"Likely duplicate of '{b.canonical_name}' "
                                f"(fuzzy similarity {score:.0%}, same origin)."
                            ),
                            duplicate_of_bean_id=b.id,
                            duplicate_of_name=b.canonical_name,
                        ))

    # 3. Stale auto-accepts — accepted with confidence below today's review band
    stale_stmt = (
        select(CanonicalMatch, CanonicalBean.canonical_name)
        .join(CanonicalBean, CanonicalMatch.proposed_canonical_bean_id == CanonicalBean.id)
        .where(CanonicalMatch.review_status == "accepted")
        .where(CanonicalMatch.confidence_score < 0.75)
        .order_by(CanonicalMatch.confidence_score)
        .limit(50)
    )
    stale_rows = (await db.execute(stale_stmt)).all()
    for match, canonical_name in stale_rows:
        issues.append(DataQualityIssue(
            issue_type="stale_auto_accept",
            bean_id=match.proposed_canonical_bean_id,
            canonical_name=canonical_name,
            severity="low",
            summary=(
                f"Match accepted at confidence {match.confidence_score:.0%}, "
                f"below today's 75% review threshold. Worth a second look."
            ),
            stale_match_id=match.id,
        ))

    # Sort by severity (high → low), then by type, then by name
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (severity_order.get(i.severity, 9), i.issue_type, i.canonical_name))
    issues = issues[:limit]

    counts: dict[str, int] = {}
    for i in issues:
        counts[i.issue_type] = counts.get(i.issue_type, 0) + 1

    return DataQualityReport(issues=issues, counts_by_type=counts, total=len(issues))


@router.get("/beans/{bean_id}/enhance/preview", response_model=EnhancementProposal)
async def preview_enhancement(
    bean_id: str,
    db: AsyncSession = Depends(get_db),
) -> EnhancementProposal:
    """
    Preview what enhancement would propose for one canonical bean. No writes.
    Returns the suggestions plus completeness score so the caller can decide.
    """
    try:
        bid = uuid.UUID(bean_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    proposal = await propose_enhancement(db, bid)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Canonical bean not found")
    return proposal


@router.post("/beans/{bean_id}/enhance/apply", response_model=EnhancementApplyResponse)
async def apply_bean_enhancement(
    bean_id: str,
    body: EnhancementApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> EnhancementApplyResponse:
    """Apply selected enhancement suggestions to a canonical bean."""
    try:
        bid = uuid.UUID(bean_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    proposal = await propose_enhancement(db, bid)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Canonical bean not found")
    bean, updated = await apply_enhancement(db, bid, proposal, body.accepted_fields)
    return EnhancementApplyResponse(
        bean_id=bean.id,
        fields_updated=updated,
        new_completeness=bean.data_completeness_score or 0.0,
    )


@router.post("/beans/enhance/bulk", response_model=BulkEnhancementSummary)
async def bulk_enhance_beans(
    max_completeness: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    auto_apply_threshold: float = Query(0.9, ge=0.5, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> BulkEnhancementSummary:
    """
    Auto-enhance canonical beans whose completeness is below `max_completeness`.
    Suggestions whose confidence is ≥`auto_apply_threshold` are applied
    immediately. Lower-confidence suggestions are NOT applied — they remain
    available via the per-bean preview endpoint.
    """
    summary = await bulk_enhance(
        db,
        max_completeness=max_completeness,
        limit=limit,
        auto_apply_threshold=auto_apply_threshold,
    )
    return BulkEnhancementSummary(**summary)


@router.post("/beans/merge", response_model=MergeResult)
async def merge_beans(
    body: MergeRequest,
    db: AsyncSession = Depends(get_db),
) -> MergeResult:
    """
    Merge two canonical beans into one. All BeanListings and CanonicalMatches
    that pointed at `source` are re-pointed at `target`. Fields populated on
    source but blank on target are copied. Source is deleted by default.

    Refuses the merge if origin_country differs between the two beans —
    that's almost certainly a mistake.
    """
    try:
        result = await merge_canonical_beans(
            db,
            source_bean_id=body.source_bean_id,
            target_bean_id=body.target_bean_id,
            delete_source=body.delete_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MergeResult(**result)


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


@router.delete("/mappings/{mapping_id}", status_code=200)
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


# ─────────────────────────────────────────────────────────────────────────────
# Feedback loops (Phase 4)

# Include feedback router endpoints
router.include_router(admin_feedback.router)
