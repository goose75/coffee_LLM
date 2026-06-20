"""
Admin API v1 router — full implementation.
Sources, ingestion runs, triggering ingestion, extractions, review, mappings, beans.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.enums import MappingType, Process, RoastLevel, PageType, ParserStrategy
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
log = logging.getLogger(__name__)


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
    if health_status:
        stmt = stmt.where(Store.health_status == health_status)
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


@router.delete("/sources/{source_id}", status_code=200)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Permanently delete a source and all its related data (pages, runs, extractions)."""
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    # Delete in order of dependencies
    from app.models.source_page import SourcePage
    from app.models.ingestion_run import IngestionRun

    # Delete all ingestion runs for this store
    await db.execute(delete(IngestionRun).where(IngestionRun.store_id == store_uuid))

    # Delete all source pages for this store
    await db.execute(delete(SourcePage).where(SourcePage.store_id == store_uuid))

    # Delete the store itself
    await db.delete(store)

    await db.commit()
    return {"deleted": True, "id": str(store_uuid)}


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
    Trigger ingestion run for a store (Shopify or HTML).
    Runs synchronously in the request for now (Phase 2 moves this to a worker queue).
    """
    try:
        store_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    if store.parser_strategy.value == "shopify":
        from app.services.shopify import ShopifyIngestionPipeline
        pipeline = ShopifyIngestionPipeline(session=db, store=store)
    elif store.parser_strategy.value == "html":
        from app.services.html import HtmlIngestionPipeline
        pipeline = HtmlIngestionPipeline(session=db, store=store)
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Store parser_strategy '{store.parser_strategy.value}' not supported yet",
        )

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


@router.post("/sources/{source_id}/discover-pages")
async def discover_pages(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Discover product pages on a store and add them to source_pages."""
    # Fetch store
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid store_id UUID")

    stmt = select(Store).where(Store.id == sid)
    store = (await db.execute(stmt)).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {source_id} not found")

    async def run_discovery():
        try:
            from app.models.source_page import SourcePage
            from app.services.extraction.source_discovery import discover_source_pages
            from datetime import datetime

            log.info(f"Discovering pages for {store.domain}...")

            # Run discovery
            discovered_urls = await discover_source_pages(
                domain=store.domain,
                homepage_url=store.homepage_url,
                max_pages=100
            )

            # Store discovered pages
            now = datetime.utcnow()

            for url in discovered_urls:
                # Check if page already exists
                existing = (
                    await db.execute(
                        select(SourcePage).where(
                            (SourcePage.store_id == store.id) & (SourcePage.url == url)
                        )
                    )
                ).scalar_one_or_none()

                if not existing:
                    source_page = SourcePage(
                        store_id=store.id,
                        url=url,
                        page_type=PageType.product,
                        parser_strategy=store.parser_strategy,
                        discovered_at=now,
                    )
                    db.add(source_page)

            await db.commit()
            log.info(f"Discovered {len(discovered_urls)} pages for {store.domain}")

        except Exception as e:
            log.error(f"Discovery error for {store.domain}: {e}")
            await db.rollback()

    background_tasks.add_task(run_discovery)

    return {
        "status": "queued",
        "message": f"Page discovery queued for {store.domain}",
        "store_id": source_id,
    }


@router.post("/sources/{source_id}/multi-stage-fallback")
async def multi_stage_fallback(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run multi-stage fallback chain: try parsers in ranked order until one works.

    For stores with pages but 0 extraction, tries each parser (ranked by quality)
    and keeps the first one that produces extraction results.
    """
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid store_id UUID")

    stmt = select(Store).where(Store.id == sid)
    store = (await db.execute(stmt)).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {source_id} not found")

    # Fetch a sample source page for testing
    from app.models.source_page import SourcePage
    page_stmt = select(SourcePage).where(SourcePage.store_id == store.id).limit(1)
    sample_page = (await db.execute(page_stmt)).scalar_one_or_none()

    if not sample_page:
        raise HTTPException(
            status_code=422,
            detail="No source pages found. Run discovery first.",
        )

    # Test all parsers to get ranking
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                sample_page.url,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=422, detail=f"Failed to fetch sample page")
            html_bytes = response.content
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch sample page: {e}")

    # Get parser rankings
    try:
        from app.services.extraction.parser_testing import test_all_parsers

        scores = await test_all_parsers(html_bytes, sample_page.url)
        parser_scores = [
            {"parser": s.parser_name, "score": s.total_score}
            for s in scores
        ]
    except Exception as e:
        log.error(f"Parser testing error: {e}")
        raise HTTPException(status_code=500, detail=f"Parser testing failed: {e}")

    # Run fallback in background
    async def run_fallback():
        try:
            from app.services.extraction.multi_stage_fallback import run_multi_stage_fallback

            # Helper to switch parser and re-ingest
            async def re_ingest_with_parser(store_id_arg: str, parser_name: str):
                # Switch parser
                stmt_update = select(Store).where(Store.id == store_id_arg)
                s = (await db.execute(stmt_update)).scalar_one_or_none()
                if s:
                    s.parser_strategy = parser_name
                    await db.commit()

                    # Trigger re-ingestion
                    from app.services.dispatcher import IngestionDispatcher
                    dispatcher = IngestionDispatcher(session=db)
                    await dispatcher.reingest_store(store_id_arg)

            # Get store fresh
            async def get_store_fresh(store_id_arg: str):
                stmt_get = select(Store).where(Store.id == store_id_arg)
                return (await db.execute(stmt_get)).scalar_one_or_none()

            result = await run_multi_stage_fallback(
                store_id=str(sid),
                parser_scores=parser_scores,
                re_ingest_func=re_ingest_with_parser,
                get_store_func=get_store_fresh,
            )

            log.info(f"Fallback result: {result}")

        except Exception as e:
            log.error(f"Multi-stage fallback error: {e}")

    background_tasks.add_task(run_fallback)

    return {
        "status": "queued",
        "message": "Multi-stage fallback chain started",
        "store_id": source_id,
        "parsers_to_try": [p["parser"] for p in parser_scores],
    }


@router.post("/sources/{source_id}/test-parsers")
async def test_parsers(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test all parsers on a sample page and return ranked results."""
    # Fetch store
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid store_id UUID")

    stmt = select(Store).where(Store.id == sid)
    store = (await db.execute(stmt)).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {source_id} not found")

    # Fetch a sample source page
    from app.models.source_page import SourcePage
    page_stmt = select(SourcePage).where(SourcePage.store_id == store.id).limit(1)
    sample_page = (await db.execute(page_stmt)).scalar_one_or_none()

    if not sample_page:
        raise HTTPException(
            status_code=422,
            detail="No source pages found for this store. Run discovery first.",
        )

    # Fetch the page content
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                sample_page.url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
                }
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to fetch sample page: HTTP {response.status_code}",
                )
            html_bytes = response.content
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Sample page fetch timeout")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch sample page: {e}")

    # Test all parsers
    try:
        from app.services.extraction.parser_testing import test_all_parsers

        scores = await test_all_parsers(html_bytes, sample_page.url)

        # Return results
        return {
            "store_id": source_id,
            "store_name": store.name,
            "sample_page_url": sample_page.url,
            "parsers": [
                {
                    "name": score.parser_name,
                    "status": score.status,
                    "confidence": round(score.confidence, 3),
                    "fields_extracted": score.fields_extracted,
                    "has_coffee_name": score.has_coffee_name,
                    "has_price": score.has_price,
                    "has_origin": score.has_origin,
                    "has_process": score.has_process,
                    "has_roast_level": score.has_roast_level,
                    "has_varietal": score.has_varietal,
                    "has_flavour_notes": score.has_flavour_notes,
                    "total_score": round(score.total_score, 3),
                }
                for score in scores
            ],
            "best_parser": scores[0].parser_name if scores else None,
            "best_score": round(scores[0].total_score, 3) if scores else 0,
        }

    except Exception as e:
        log.error(f"Parser testing error for {store.domain}: {e}")
        raise HTTPException(status_code=500, detail=f"Parser testing failed: {e}")


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
    """List ingestion run history with store names, newest first."""
    stmt = select(IngestionRun).options(selectinload(IngestionRun.store))
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

    # Build items with store names
    items = []
    for r in rows:
        item = IngestionRunItem.model_validate(r)
        item.store_name = r.store.name if r.store else None
        items.append(item)

    return PaginatedIngestionRuns(
        data=items,
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/ingestion-runs/{run_id}", response_model=IngestionRunItem)
async def get_ingestion_run(run_id: str, db: AsyncSession = Depends(get_db)) -> IngestionRunItem:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    run = (await db.execute(select(IngestionRun).options(selectinload(IngestionRun.store)).where(IngestionRun.id == run_uuid))).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    item = IngestionRunItem.model_validate(run)
    item.store_name = run.store.name if run.store else None
    return item


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


@router.get("/review/unmatched-count")
async def get_unmatched_count(db: AsyncSession = Depends(get_db)) -> dict:
    """Get count of bean listings queued for matching (unmatched)."""
    stmt = select(func.count()).select_from(
        select(BeanListing).where(BeanListing.canonical_bean_id == None).subquery()  # noqa: E712
    )
    count = (await db.execute(stmt)).scalar_one()
    return {"count": count}


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


@router.post("/review/create-canonicals-from-listings", response_model=dict)
async def create_canonicals_from_unmatched(
    limit: int = Query(None, ge=1, description="Max canonicals to create (None = all)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Directly create canonical beans from unmatched bean listings.

    For each unmatched listing, creates a new canonical bean with its extracted data,
    then links the listing to it. This bypasses the matching pipeline and is useful
    when you have many listings with no good matches to existing canonicals.
    """
    from sqlalchemy import and_

    # Get all unmatched listings
    stmt = (
        select(BeanListing)
        .where(BeanListing.canonical_bean_id == None)  # noqa: E712
        .order_by(BeanListing.first_seen_at.desc())
    )

    if limit:
        stmt = stmt.limit(limit)

    unmatched = (await db.execute(stmt)).scalars().all()

    if not unmatched:
        return {
            "status": "ok",
            "message": "No unmatched listings",
            "total": 0,
            "created": 0,
            "linked": 0,
            "errors": 0,
        }

    created_count = 0
    error_count = 0

    for listing in unmatched:
        try:
            # Normalize enum values: convert to lowercase and validate
            process = None
            if listing.process_label_raw and listing.process_label_raw.strip():
                process_str = listing.process_label_raw.strip().lower()
                # Try to match against valid enum values
                try:
                    process = Process(process_str)
                except ValueError:
                    # If not a valid enum value, set to None
                    process = None

            roast_level = None
            if listing.roast_label_raw and listing.roast_label_raw.strip():
                roast_str = listing.roast_label_raw.strip().lower()
                # Try to match against valid enum values
                try:
                    roast_level = RoastLevel(roast_str)
                except ValueError:
                    # If not a valid enum value, set to None
                    roast_level = None

            canonical = CanonicalBean(
                canonical_name=listing.raw_title or "Unknown",
                origin_country=listing.origin_label_raw if listing.origin_label_raw and listing.origin_label_raw.strip() else None,
                roast_level=roast_level,
                varietal=[listing.varietal_label_raw] if listing.varietal_label_raw and listing.varietal_label_raw.strip() else [],
                process=process,
                flavour_notes=[],
                decaf_flag=False,
                espresso_suitable_flag=False,
                filter_suitable_flag=False,
                data_completeness_score=0.3,
            )
            db.add(canonical)
            await db.flush()

            # Link listing to canonical
            listing.canonical_bean_id = canonical.id
            created_count += 1

        except Exception as exc:
            log.error(f"Error creating canonical for listing {listing.id}: {exc}")
            error_count += 1
            await db.rollback()
            continue

    await db.commit()

    return {
        "status": "ok",
        "message": f"Created {created_count} canonical beans",
        "total": len(unmatched),
        "created": created_count,
        "linked": created_count,
        "errors": error_count,
    }


@router.post("/review/match-unmatched", response_model=dict)
async def match_all_unmatched_listings(
    limit: int = Query(None, ge=1, description="Max listings to match (None = all)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Bulk match all unmatched bean listings.

    For each listing without a canonical_bean_id:
    1. Run the matching pipeline
    2. Auto-accept high-confidence matches (≥0.78)
    3. Create pending matches for review (0.55-0.78)
    4. Create new canonical beans for unmatched (<0.55)

    This operation is safe to run repeatedly (idempotent).
    """
    from sqlalchemy import and_

    # Fetch all unmatched listings
    stmt = (
        select(BeanListing)
        .where(BeanListing.canonical_bean_id == None)  # noqa: E712
        .order_by(BeanListing.first_seen_at.desc())
    )

    if limit:
        stmt = stmt.limit(limit)

    unmatched_listings = (await db.execute(stmt)).scalars().all()

    if not unmatched_listings:
        return {
            "status": "ok",
            "message": "No unmatched listings found",
            "total": 0,
            "matched": 0,
            "auto_accepted": 0,
            "pending_review": 0,
            "new_canonical": 0,
            "errors": 0,
        }

    # Run matching batch
    service = CanonicalMatchingService(db)
    decisions = await service.match_batch(unmatched_listings)

    # Summarize results
    auto_accepted = sum(1 for d in decisions if d.outcome == "auto_accepted")
    pending = sum(1 for d in decisions if d.outcome == "review_queued")
    new_canonical = sum(1 for d in decisions if d.outcome == "new_canonical")
    errors = sum(1 for d in decisions if d.outcome == "error")
    already = sum(1 for d in decisions if d.outcome == "already_matched")

    return {
        "status": "ok",
        "message": f"Matched {len(unmatched_listings)} listings",
        "total": len(unmatched_listings),
        "auto_accepted": auto_accepted,
        "pending_review": pending,
        "new_canonical": new_canonical,
        "already_matched": already,
        "errors": errors,
    }


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
# Automatic matching (prevent stalling)

@router.post("/matching/auto-match-new-listings", response_model=dict)
async def auto_match_new_listings(
    background_tasks: BackgroundTasks,
    limit: int = Query(1000, ge=1, description="Max listings to process"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Automatically match any new unmatched listings.

    This endpoint is designed to be called periodically by a scheduler
    to prevent the matching pipeline from stalling.

    Process:
    1. Find all unmatched listings (limit=1000 per run)
    2. Run matching pipeline on them
    3. Create new canonicals for low-confidence matches
    4. Return summary of actions taken
    """
    # Count unmatched
    unmatched_stmt = (
        select(func.count())
        .select_from(BeanListing)
        .where(BeanListing.canonical_bean_id == None)  # noqa: E712
    )
    unmatched_count = (await db.execute(unmatched_stmt)).scalar_one() or 0

    if unmatched_count == 0:
        return {
            "status": "ok",
            "message": "No unmatched listings",
            "total_unmatched": 0,
            "processed": 0,
            "background_task_queued": False,
        }

    async def run_auto_match():
        """Background task to match and canonicalize unmatched listings."""
        try:
            # Step 1: Try matching
            from app.services.matching import CanonicalMatchingService
            service = CanonicalMatchingService(db)

            stmt = (
                select(BeanListing)
                .where(BeanListing.canonical_bean_id == None)  # noqa: E712
                .order_by(BeanListing.first_seen_at.desc())
                .limit(limit)
            )
            unmatched_listings = (await db.execute(stmt)).scalars().all()

            if not unmatched_listings:
                log.info("No unmatched listings found for auto-match")
                return

            matched_count = 0
            auto_accepted = 0
            pending = 0

            # Try to match each listing
            for listing in unmatched_listings:
                decision = await service.match_listing(listing)
                if decision.outcome == "auto_accepted":
                    auto_accepted += 1
                    matched_count += 1
                elif decision.outcome == "review_queued":
                    pending += 1
                    matched_count += 1

            await db.commit()

            # Step 2: Create new canonicals from remaining unmatched
            stmt = (
                select(BeanListing)
                .where(BeanListing.canonical_bean_id == None)  # noqa: E712
                .order_by(BeanListing.first_seen_at.desc())
            )
            still_unmatched = (await db.execute(stmt)).scalars().all()

            created_count = 0
            for listing in still_unmatched:
                try:
                    process = None
                    if listing.process_label_raw and listing.process_label_raw.strip():
                        process_str = listing.process_label_raw.strip().lower()
                        try:
                            process = Process(process_str)
                        except ValueError:
                            process = None

                    roast_level = None
                    if listing.roast_label_raw and listing.roast_label_raw.strip():
                        roast_str = listing.roast_label_raw.strip().lower()
                        try:
                            roast_level = RoastLevel(roast_str)
                        except ValueError:
                            roast_level = None

                    canonical = CanonicalBean(
                        canonical_name=listing.raw_title or "Unknown",
                        origin_country=listing.origin_label_raw if listing.origin_label_raw and listing.origin_label_raw.strip() else None,
                        roast_level=roast_level,
                        varietal=[listing.varietal_label_raw] if listing.varietal_label_raw and listing.varietal_label_raw.strip() else [],
                        process=process,
                        flavour_notes=[],
                        decaf_flag=False,
                        espresso_suitable_flag=False,
                        filter_suitable_flag=False,
                        data_completeness_score=0.3,
                    )
                    db.add(canonical)
                    await db.flush()
                    listing.canonical_bean_id = canonical.id
                    created_count += 1
                except Exception as exc:
                    log.error(f"Error creating canonical for listing {listing.id}: {exc}")
                    await db.rollback()

            await db.commit()

            log.info(
                f"Auto-match completed: {matched_count} matched ({auto_accepted} auto-accepted, "
                f"{pending} pending), {created_count} new canonicals created"
            )

        except Exception as exc:
            log.error(f"Auto-match task failed: {exc}", exc_info=True)
            await db.rollback()

    # Queue background task
    background_tasks.add_task(run_auto_match)

    return {
        "status": "queued",
        "message": f"Auto-matching queued for up to {limit} unmatched listings",
        "total_unmatched": unmatched_count,
        "processed": min(unmatched_count, limit),
        "background_task_queued": True,
    }


@router.post("/beans/extract-flavours-from-descriptions", response_model=dict)
async def extract_flavours_from_descriptions(
    limit: int = Query(500, ge=1, le=1000, description="Max beans to process"),
    confidence_threshold: float = Query(0.7, ge=0.5, le=0.99, description="Min confidence to accept extraction"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Extract flavour notes from product descriptions using LLM.

    For each canonical bean without flavour notes:
    1. Collect descriptions from linked listings
    2. Use LLM to identify flavour notes
    3. Only update if confidence >= threshold
    4. Preserve existing (don't overwrite manual data)
    """
    import anthropic
    import os
    import json

    # Get beans without flavour notes
    stmt = (
        select(CanonicalBean)
        .where(
            or_(
                CanonicalBean.flavour_notes == [],
                CanonicalBean.flavour_notes == None
            )
        )
        .order_by(CanonicalBean.data_completeness_score.desc().nullslast())
        .limit(limit)
    )

    beans = (await db.execute(stmt)).scalars().all()

    if not beans:
        return {
            "status": "ok",
            "message": "No beans without flavour notes",
            "processed": 0,
            "updated": 0,
        }

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    updated_count = 0
    skipped_count = 0

    for bean in beans:
        try:
            # Get all descriptions from linked listings
            listings_stmt = (
                select(BeanListing.raw_description)
                .where(BeanListing.canonical_bean_id == bean.id)
                .where(BeanListing.raw_description != None)
            )
            result = await db.execute(listings_stmt)
            descriptions = [row[0] for row in result]

            if not descriptions:
                skipped_count += 1
                continue

            # Combine descriptions (take first few to avoid token limits)
            combined_text = " | ".join(descriptions[:3])

            # Call LLM to extract flavours
            prompt = f"""Extract coffee flavour notes from this product description.

Description: {combined_text}

Return ONLY a JSON object with:
{{"flavours": ["note1", "note2", "note3"], "confidence": 0.85}}

Guidelines:
- Extract specific sensory descriptors (fruity, floral, nutty, chocolate, etc)
- Be conservative - only extract if clearly mentioned
- Max 12 notes
- Confidence 0.5-1.0 based on how clear the description is
- Return empty array if no flavours found

JSON only, no other text:"""

            message = client.messages.create(
                model="claude-opus-4-1",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Parse JSON
            data = json.loads(response_text)
            confidence = data.get("confidence", 0)
            flavours = data.get("flavours", [])

            # Only update if confidence is high and flavours exist
            if confidence >= confidence_threshold and flavours:
                bean.flavour_notes = flavours
                updated_count += 1

                if updated_count % 50 == 0:
                    log.info(f"Extracted flavours for {updated_count} beans")
            else:
                skipped_count += 1

        except Exception as exc:
            log.warning(f"Error extracting flavours for {bean.id}: {exc}")
            skipped_count += 1

    await db.commit()

    return {
        "status": "ok",
        "message": f"Extracted flavours for {updated_count} beans",
        "processed": len(beans),
        "updated": updated_count,
        "skipped_low_confidence": skipped_count,
        "confidence_threshold": confidence_threshold,
        "note": "Only updated beans with high-confidence extractions. Flavour atlas should expand accordingly.",
    }


@router.post("/beans/merge-duplicates", response_model=dict)
async def merge_duplicate_canonical_beans(
    limit: int = Query(None, ge=1, description="Max groups to merge (None = all)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Merge duplicate canonical beans with same name.

    For each group of canonicals with the same canonical_name:
    1. Keep the one with highest data_completeness_score
    2. Relink all other beans' listings to the kept bean
    3. Delete duplicate beans

    Only uses facts in the database - does NOT create, invent, or assume data.
    """
    # Find all duplicate groups
    stmt = select(CanonicalBean.canonical_name).distinct().where(
        CanonicalBean.canonical_name.in_(
            select(CanonicalBean.canonical_name)
            .group_by(CanonicalBean.canonical_name)
            .having(func.count() > 1)
        )
    )

    if limit:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    dup_names = [row[0] for row in result]

    if not dup_names:
        return {
            "status": "ok",
            "message": "No duplicate canonical beans found",
            "groups_merged": 0,
            "beans_deleted": 0,
            "listings_relinked": 0,
        }

    merged = 0
    deleted = 0
    relinked = 0

    for dup_name in dup_names:
        try:
            # Get all beans with this name, sorted by completeness (keep best)
            beans_stmt = (
                select(CanonicalBean)
                .where(CanonicalBean.canonical_name == dup_name)
                .order_by(
                    CanonicalBean.data_completeness_score.desc().nullslast(),
                    CanonicalBean.created_at.asc()
                )
            )
            result = await db.execute(beans_stmt)
            beans = result.scalars().all()

            if len(beans) > 1:
                master_bean = beans[0]  # Keep best (highest completeness)

                # Relink all other beans' listings to master
                for duplicate_bean in beans[1:]:
                    # Find all listings pointing to this duplicate
                    listings_stmt = (
                        select(BeanListing)
                        .where(BeanListing.canonical_bean_id == duplicate_bean.id)
                    )
                    result = await db.execute(listings_stmt)
                    listings = result.scalars().all()

                    for listing in listings:
                        listing.canonical_bean_id = master_bean.id
                        relinked += 1

                    # Delete canonical matches that reference this bean
                    from app.models.resolution import CanonicalMatch
                    del_matches_stmt = delete(CanonicalMatch).where(
                        or_(
                            CanonicalMatch.proposed_canonical_bean_id == duplicate_bean.id,
                        )
                    )
                    await db.execute(del_matches_stmt)

                    # Delete the duplicate bean
                    await db.delete(duplicate_bean)
                    deleted += 1

                merged += 1

        except Exception as exc:
            log.error(f"Error merging '{dup_name}': {exc}")

    await db.commit()

    return {
        "status": "ok",
        "message": f"Merged {merged} duplicate canonical groups",
        "groups_merged": merged,
        "beans_deleted": deleted,
        "listings_relinked": relinked,
        "note": "All listings preserved by relinking to master canonical beans. No data invented.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parser Testing (Smart Selection)

@router.post("/test-parser")
async def test_parser(
    store_id: str = Query(...),
    parser: str = Query(...),
    url: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test a specific parser on a URL and return extraction results."""
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    store = (await db.execute(select(Store).where(Store.id == store_uuid))).scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    # Validate parser
    valid_parsers = ["html", "schema_org", "llm"]
    if parser not in valid_parsers:
        raise HTTPException(status_code=422, detail=f"Invalid parser. Must be one of: {', '.join(valid_parsers)}")

    try:
        import httpx
        from app.services.extraction.schema_org_parser import SchemaOrgParser
        from app.services.extraction.html_parser import HtmlRulesParser
        from app.services.extraction.llm_parser import LLMParser

        # Fetch page
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {
                    "parser": parser,
                    "status": "error",
                    "confidence": 0,
                    "fields_extracted": 0,
                    "extraction_summary": f"Failed to fetch page (HTTP {resp.status_code})",
                }
            html_bytes = resp.content

        # Test parser
        if parser == "html":
            extractor = HtmlRulesParser()
        elif parser == "schema_org":
            extractor = SchemaOrgParser()
        else:  # llm
            extractor = LLMParser()

        result = extractor.extract(html_bytes, url)

        # Count extracted fields
        payload = result.payload
        if payload:
            fields_count = sum(1 for field in [
                payload.coffee_name,
                payload.origin_country,
                payload.roast_level,
                payload.process,
                payload.varietal,
                payload.flavour_notes,
                payload.price_variants,
            ] if field)
            confidence = float(payload.confidence) if payload.confidence else 0
        else:
            fields_count = 0
            confidence = 0

        return {
            "parser": parser,
            "status": result.validation_status,
            "confidence": confidence,
            "fields_extracted": fields_count,
            "extraction_summary": f"Extracted {fields_count} fields with {result.validation_status} status",
        }

    except Exception as e:
        log.exception(f"Parser test error for {parser}:")
        return {
            "parser": parser,
            "status": "error",
            "confidence": 0,
            "fields_extracted": 0,
            "extraction_summary": f"Test error: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Feedback loops (Phase 4)

# Include feedback router endpoints
router.include_router(admin_feedback.router)
