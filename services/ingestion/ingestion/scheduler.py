"""
Ingestion scheduler.

Runs on a tight loop, querying the database for stores that are due for
a crawl and enqueuing them into the Redis job queue.

Scheduling logic per store:
  - due = last_successful_crawl_at + crawl_frequency_hours < now
  - OR last_successful_crawl_at IS NULL (never crawled)
  - Only active stores (active_flag=True) are scheduled
  - Priority is boosted for stores never crawled (priority=8)
  - Priority is normal (5) for regular refresh cycles
  - Shopify stores get a slightly higher priority (6) since they're faster

The scheduler also:
  - Reclaims stuck processing jobs every 5 minutes
  - Logs queue stats every 10 minutes
  - Handles DB reconnect on transient failures

The scheduler does NOT run the ingestion itself — it only queues jobs.
The worker module picks jobs off the queue and dispatches them.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from ingestion.queue import IngestionJob, JobQueue

log = logging.getLogger(__name__)

# How often the scheduler loop runs
SCHEDULER_INTERVAL_S = 60  # 1 minute
STATS_LOG_INTERVAL_S = 600  # 10 minutes
RECLAIM_INTERVAL_S = 300    # 5 minutes


class IngestionScheduler:
    """
    Queries the store table for due crawls and enqueues them.

    Designed to run as a single long-lived coroutine alongside the worker.
    """

    def __init__(self, db_url: str, queue: JobQueue) -> None:
        self._db_url = db_url
        self._queue = queue
        self._engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=5)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._last_reclaim = 0.0
        self._last_stats_log = 0.0

    async def run(self) -> None:
        """Main scheduler loop — runs indefinitely."""
        log.info("Scheduler starting")
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                log.info("Scheduler cancelled")
                break
            except Exception as exc:
                log.error("Scheduler tick failed: %s", exc, exc_info=True)

            await asyncio.sleep(SCHEDULER_INTERVAL_S)

    async def _tick(self) -> None:
        """One scheduling cycle: find due stores → enqueue jobs."""
        now_ts = datetime.now(timezone.utc).timestamp()

        # Reclaim stuck jobs periodically
        if now_ts - self._last_reclaim > RECLAIM_INTERVAL_S:
            reclaimed = await self._queue.reclaim_stuck()
            if reclaimed:
                log.info("Reclaimed %d stuck jobs", reclaimed)
            self._last_reclaim = now_ts

        # Log queue stats periodically
        if now_ts - self._last_stats_log > STATS_LOG_INTERVAL_S:
            stats = await self._queue.stats()
            log.info("Queue stats: %s", stats)
            self._last_stats_log = now_ts

        # Find stores due for crawl
        due_stores = await self._find_due_stores()
        if not due_stores:
            log.debug("No stores due for crawl")
            return

        jobs: list[IngestionJob] = []
        for store in due_stores:
            strategy = store["parser_strategy"] or "html"
            # Enum value may be "ParserStrategy.shopify" format from ORM
            if "." in strategy:
                strategy = strategy.split(".")[-1]

            priority = 8 if store["never_crawled"] else (6 if strategy == "shopify" else 5)

            job = IngestionJob(
                store_id=str(store["id"]),
                store_domain=store["domain"],
                parser_strategy=strategy,
                priority=priority,
            )
            jobs.append(job)

        added = await self._queue.enqueue_many(jobs)
        log.info(
            "Scheduled %d stores for crawl (%d new jobs enqueued)",
            len(due_stores), added,
        )

    async def _find_due_stores(self) -> list[dict]:
        """
        Query stores that need crawling.
        A store is due if:
          - It has never been crawled (last_successful_crawl_at IS NULL), OR
          - It was last crawled more than crawl_frequency_hours ago
        """
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            # Import here to avoid circular imports at module level
            from sqlalchemy import text

            result = await session.execute(text("""
                SELECT
                    id,
                    domain,
                    parser_strategy,
                    crawl_frequency_hours,
                    last_successful_crawl_at,
                    (last_successful_crawl_at IS NULL) AS never_crawled
                FROM stores
                WHERE active_flag = TRUE
                  AND (
                    last_successful_crawl_at IS NULL
                    OR last_successful_crawl_at + (crawl_frequency_hours * INTERVAL '1 hour') < :now
                  )
                ORDER BY
                    last_successful_crawl_at ASC NULLS FIRST,
                    crawl_frequency_hours ASC
                LIMIT 100
            """), {"now": now})

            rows = result.mappings().all()
            return [dict(r) for r in rows]

    async def close(self) -> None:
        await self._engine.dispose()
