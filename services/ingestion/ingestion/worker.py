"""
Ingestion worker — production entry point.

Runs three concurrent coroutines:
  1. Scheduler — queries DB every 60s for due stores, enqueues jobs
  2. N Workers  — dequeue jobs and dispatch to pipelines
  3. Health server — HTTP /health endpoint for Docker healthcheck

Usage:
  python -m ingestion.worker
  python -m ingestion.worker enqueue shop.squaremilecoffee.com shopify

Environment variables:
  DATABASE_URL   — PostgreSQL async connection string
  REDIS_URL      — Redis connection string
  WORKER_COUNT   — concurrent dispatch workers (default: 3)
  LOG_LEVEL      — DEBUG | INFO | WARNING | ERROR (default: INFO)
  POLL_INTERVAL_S — seconds between queue polls (default: 5.0)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone

# Add API service to path so we can import app.* modules
_API_PATH = "/app/services/api"
if _API_PATH not in sys.path:
    sys.path.insert(0, _API_PATH)

from ingestion.dispatcher import IngestionDispatcher
from ingestion.queue import IngestionJob, JobQueue
from ingestion.scheduler import IngestionScheduler

# ── Logging ───────────────────────────────────────────────────────────────────

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("worker")

# ── Configuration ─────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://coffee:coffee@localhost:5432/coffee_platform",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WORKER_COUNT = int(os.getenv("WORKER_COUNT", "3"))
DEQUEUE_BATCH = int(os.getenv("DEQUEUE_BATCH", "5"))
POLL_INTERVAL_S = float(os.getenv("POLL_INTERVAL_S", "5.0"))

# ── Graceful shutdown event ───────────────────────────────────────────────────

_shutdown = asyncio.Event()


def _handle_signal(sig):
    log.info("Received %s — initiating graceful shutdown", sig.name)
    _shutdown.set()


# ── Worker coroutine ──────────────────────────────────────────────────────────

async def run_worker(
    worker_id: int,
    queue: JobQueue,
    dispatcher: IngestionDispatcher,
) -> None:
    """Single worker: dequeues and dispatches jobs until shutdown."""
    log.info("Worker-%d starting", worker_id)
    processed = failed = 0

    while not _shutdown.is_set():
        per_worker_limit = max(1, DEQUEUE_BATCH // WORKER_COUNT)
        jobs = await queue.dequeue_due(limit=per_worker_limit)

        if not jobs:
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=POLL_INTERVAL_S)
            except asyncio.TimeoutError:
                pass
            continue

        for job in jobs:
            if _shutdown.is_set():
                await queue.enqueue(job)
                break

            try:
                result = await dispatcher.dispatch(job)

                if result.success:
                    await queue.ack(job)
                    processed += 1
                    log.info(
                        "Worker-%d ✓ %s %.1fs — %d pages %d listings %d prices",
                        worker_id, job.store_domain, result.duration_s,
                        result.pages_processed,
                        result.listings_created + result.listings_updated,
                        result.price_writes,
                    )
                else:
                    err = "; ".join(result.errors[:3])
                    await queue.nack(job, err)
                    failed += 1
                    log.warning(
                        "Worker-%d ✗ %s — %s (soft=%s)",
                        worker_id, job.store_domain, err, result.is_soft_failure,
                    )

            except Exception as exc:
                await queue.nack(job, f"Unhandled: {exc}")
                log.error("Worker-%d crash for %s: %s", worker_id, job.store_domain, exc, exc_info=True)

    log.info("Worker-%d done — processed=%d failed=%d", worker_id, processed, failed)


# ── Minimal health HTTP server ────────────────────────────────────────────────

async def run_health_server(queue: JobQueue, port: int = 8001) -> None:
    """Tiny asyncio HTTP server — responds to GET /health for Docker."""

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read(1024)  # consume request
        try:
            stats = await queue.stats()
            body = (
                f'{{"status":"ok","queue":{{"scheduled":{stats["scheduled"]},'
                f'"processing":{stats["processing"]},'
                f'"dead":{stats["dead"]}}},'
                f'"workers":{WORKER_COUNT},'
                f'"timestamp":"{datetime.now(timezone.utc).isoformat()}"}}'
            )
            status = "200 OK"
        except Exception as exc:
            body = f'{{"status":"error","error":"{exc}"}}'
            status = "503 Service Unavailable"

        response = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )
        writer.write(response.encode())
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "0.0.0.0", port)
    log.info("Health server on port %d", port)
    async with server:
        await _shutdown.wait()


# ── CLI: manual enqueue ───────────────────────────────────────────────────────

async def enqueue_store(domain: str, strategy: str = "shopify") -> None:
    """Manually enqueue a single store by domain (CLI usage)."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        result = await session.execute(
            text("SELECT id, domain FROM stores WHERE domain = :domain LIMIT 1"),
            {"domain": domain},
        )
        row = result.mappings().first()
        if row is None:
            print(f"Store not found in database: {domain}")
            await engine.dispose()
            return

        q = JobQueue(REDIS_URL)
        await q.connect()
        job = IngestionJob(
            store_id=str(row["id"]),
            store_domain=row["domain"],
            parser_strategy=strategy,
            priority=10,
        )
        await q.enqueue(job)
        print(f"Enqueued: {job}")
        await q.close()

    await engine.dispose()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    log.info("=== Coffee Platform Ingestion Worker ===")
    log.info("DB:      %s", DATABASE_URL.split("@")[-1])
    log.info("Redis:   %s", REDIS_URL)
    log.info("Workers: %d", WORKER_COUNT)

    queue = JobQueue(REDIS_URL)
    await queue.connect()

    dispatcher = IngestionDispatcher(DATABASE_URL)
    scheduler = IngestionScheduler(db_url=DATABASE_URL, queue=queue)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))

    tasks = [
        asyncio.create_task(scheduler.run(),          name="scheduler"),
        asyncio.create_task(run_health_server(queue), name="health"),
        *[
            asyncio.create_task(
                run_worker(i, queue, dispatcher),
                name=f"worker-{i}",
            )
            for i in range(WORKER_COUNT)
        ],
    ]

    log.info("All components running — waiting for shutdown signal")
    try:
        await _shutdown.wait()
    except asyncio.CancelledError:
        pass

    log.info("Shutting down %d tasks", len(tasks))
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await scheduler.close()
    await dispatcher.close()
    await queue.close()
    log.info("Worker exited cleanly")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "enqueue":
        strategy = sys.argv[3] if len(sys.argv) > 3 else "shopify"
        asyncio.run(enqueue_store(sys.argv[2], strategy))
    else:
        asyncio.run(main())
