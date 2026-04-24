"""
Ingestion dispatcher.

Takes a dequeued IngestionJob and routes it to the appropriate
ingestion pipeline based on parser_strategy.

Strategy routing:
  shopify    → ShopifyIngestionPipeline (structured, reliable)
  schema_org → ExtractionService with SchemaOrgParser (semi-structured)
  html       → ExtractionService with HtmlRulesParser (deterministic selectors)
  llm        → ExtractionService with LLMParser fallback (last resort)

Each dispatcher call:
  1. Opens a DB session
  2. Fetches the Store record
  3. Fetches the store's source pages (product listing pages)
  4. Runs the appropriate pipeline
  5. Returns a DispatchResult

Error handling:
  - Pipeline errors are caught and returned as failures (not re-raised)
  - The worker decides whether to ack or nack based on the result
  - Network errors from the target site are "soft" failures (nack → retry)
  - Programming errors are "hard" failures (nack → eventually dead letter)

The dispatcher is stateless — a new instance per job is fine.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from ingestion.queue import IngestionJob

log = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Outcome of dispatching one job."""

    job_id: str
    store_id: str
    store_domain: str
    strategy: str
    success: bool
    pages_processed: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    price_writes: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    is_soft_failure: bool = False  # True = network/timeout, worth retrying

    @property
    def duration_s(self) -> float:
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    def finish(self) -> "DispatchResult":
        self.completed_at = datetime.now(timezone.utc)
        return self


class IngestionDispatcher:
    """
    Routes ingestion jobs to the correct pipeline.

    One instance per worker process. Uses a shared async engine for DB connections.
    """

    def __init__(self, db_url: str) -> None:
        self._engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def dispatch(self, job: IngestionJob) -> DispatchResult:
        """Dispatch a job to its pipeline. Never raises."""
        result = DispatchResult(
            job_id=job.job_id,
            store_id=job.store_id,
            store_domain=job.store_domain,
            strategy=job.parser_strategy,
            success=False,
        )
        log.info("Dispatching %s (strategy=%s attempt=%d)", job.store_domain, job.parser_strategy, job.attempts)

        try:
            async with self._session_factory() as session:
                store = await self._get_store(session, job.store_id)
                if store is None:
                    result.errors.append(f"Store {job.store_id} not found in DB")
                    return result.finish()

                if job.parser_strategy == "shopify":
                    await self._run_shopify(session, store, job, result)
                elif job.parser_strategy in ("schema_org", "html", "llm"):
                    await self._run_extraction(session, store, job, result)
                else:
                    result.errors.append(f"Unknown parser_strategy: {job.parser_strategy}")
                    return result.finish()

                if not result.errors:
                    result.success = True

        except (ConnectionError, TimeoutError, OSError) as exc:
            result.errors.append(f"Network error: {exc}")
            result.is_soft_failure = True
            log.warning("Soft failure for %s: %s", job.store_domain, exc)
        except asyncio.TimeoutError:
            result.errors.append("Timeout during dispatch")
            result.is_soft_failure = True
        except Exception as exc:
            result.errors.append(f"Unexpected error: {exc}")
            log.error("Hard failure for %s: %s", job.store_domain, exc, exc_info=True)

        return result.finish()

    async def _run_shopify(
        self,
        session: AsyncSession,
        store,
        job: IngestionJob,
        result: DispatchResult,
    ) -> None:
        """Run the Shopify products.json pipeline."""
        from app.services.shopify.pipeline import ShopifyIngestionPipeline
        from app.services.storage.backend import get_storage_backend
        from app.core.config import settings

        storage = get_storage_backend(
            backend=settings.STORAGE_BACKEND,
            local_path=settings.STORAGE_LOCAL_PATH,
        )
        pipeline = ShopifyIngestionPipeline(session=session, store=store, storage=storage)

        try:
            counters = await asyncio.wait_for(
                pipeline.run(),
                timeout=300.0,  # 5 minutes per store
            )
            result.listings_created = counters.products_created
            result.listings_updated = counters.products_updated
            result.price_writes = counters.price_history_writes
            result.pages_processed = counters.pages_fetched
            if counters.errors:
                result.errors.extend(counters.errors[:5])  # cap at 5 errors

        except asyncio.TimeoutError:
            result.errors.append("Shopify pipeline timed out after 300s")
            result.is_soft_failure = True

    async def _run_extraction(
        self,
        session: AsyncSession,
        store,
        job: IngestionJob,
        result: DispatchResult,
    ) -> None:
        """
        Run the schema.org / HTML / LLM extraction pipeline for a store.

        For non-Shopify stores, we fetch each product URL from source_pages
        and run the extraction chain.
        """
        import httpx
        from app.services.extraction import ExtractionService, ParserChain, SchemaOrgParser, HtmlRulesParser
        from app.models.source_page import SourcePage
        from sqlalchemy import select

        # Get product pages for this store
        pages_result = await session.execute(
            select(SourcePage).where(
                SourcePage.store_id == store.id,
                SourcePage.page_type == "product",
            ).limit(200)
        )
        pages = pages_result.scalars().all()

        if not pages:
            log.info("No product pages found for %s — skipping extraction", job.store_domain)
            result.pages_processed = 0
            return

        # Configure parser chain based on strategy
        if job.parser_strategy == "schema_org":
            chain = ParserChain([SchemaOrgParser()])
        elif job.parser_strategy == "html":
            chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
        else:  # llm
            chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
            # LLM fallback is enabled in ExtractionService via use_llm=True

        service = ExtractionService(
            session=session,
            chain=chain,
            use_llm=(job.parser_strategy == "llm"),
        )

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "CoffeePlatformBot/1.0 (+https://coffeeintelligence.co.uk/bot)"},
        ) as client:
            for page in pages:
                try:
                    resp = await asyncio.wait_for(
                        client.get(page.url),
                        timeout=20.0,
                    )
                    if resp.status_code == 200:
                        await service.extract_and_save(
                            html=resp.content,
                            url=str(resp.url),
                            source_page=page,
                        )
                        result.pages_processed += 1
                        result.listings_updated += 1
                    else:
                        result.errors.append(f"{page.url}: HTTP {resp.status_code}")

                except asyncio.TimeoutError:
                    result.errors.append(f"{page.url}: timeout")
                    result.is_soft_failure = True
                except Exception as exc:
                    result.errors.append(f"{page.url}: {exc}")

                # Polite crawl delay
                await asyncio.sleep(1.5)

        await session.commit()

    async def _get_store(self, session: AsyncSession, store_id: str):
        """Fetch store from DB."""
        from app.models.store import Store
        from sqlalchemy import select
        import uuid
        try:
            uid = uuid.UUID(store_id)
        except ValueError:
            return None
        result = await session.execute(select(Store).where(Store.id == uid))
        return result.scalar_one_or_none()

    async def close(self) -> None:
        await self._engine.dispose()
