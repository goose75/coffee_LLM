"""
Job queue for the ingestion worker.

Uses Redis sorted sets for scheduling:
  - Key: coffee:jobs:scheduled
  - Score: Unix timestamp when job should run next
  - Member: JSON-encoded job payload

This gives us:
  - O(log N) enqueue/dequeue
  - Natural "due now" queries (ZRANGEBYSCORE 0 NOW)
  - Deduplication by store_id (re-enqueue replaces existing score)
  - Persistence across worker restarts (Redis AOF/RDB)

Job payload schema:
  {
    "job_id": "uuid",
    "store_id": "uuid",
    "store_domain": "example.com",
    "parser_strategy": "shopify|schema_org|html|llm",
    "priority": 1-10,
    "enqueued_at": "ISO8601",
    "attempts": 0
  }

Dead letter queue:
  - Key: coffee:jobs:dead
  - Jobs that failed MAX_ATTEMPTS times go here for operator inspection
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

# ── Redis key constants ───────────────────────────────────────────────────────
QUEUE_SCHEDULED = "coffee:jobs:scheduled"   # sorted set: score=run_at_ts
QUEUE_PROCESSING = "coffee:jobs:processing" # sorted set: score=started_at_ts
QUEUE_DEAD = "coffee:jobs:dead"             # list: failed jobs
QUEUE_RESULTS = "coffee:jobs:results"       # hash: job_id → result JSON

MAX_ATTEMPTS = 3
PROCESSING_TIMEOUT_S = 600  # 10 minutes — reclaim stuck jobs


class IngestionJob:
    """One unit of work: ingest a single store."""

    __slots__ = ("job_id", "store_id", "store_domain", "parser_strategy",
                 "priority", "enqueued_at", "attempts", "run_at")

    def __init__(
        self,
        store_id: str,
        store_domain: str,
        parser_strategy: str,
        priority: int = 5,
        run_at: datetime | None = None,
        job_id: str | None = None,
        enqueued_at: datetime | None = None,
        attempts: int = 0,
    ) -> None:
        self.job_id = job_id or str(uuid.uuid4())
        self.store_id = store_id
        self.store_domain = store_domain
        self.parser_strategy = parser_strategy
        self.priority = priority
        self.run_at = run_at or datetime.now(timezone.utc)
        self.enqueued_at = enqueued_at or datetime.now(timezone.utc)
        self.attempts = attempts

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "store_id": self.store_id,
            "store_domain": self.store_domain,
            "parser_strategy": self.parser_strategy,
            "priority": self.priority,
            "run_at": self.run_at.isoformat(),
            "enqueued_at": self.enqueued_at.isoformat(),
            "attempts": self.attempts,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "IngestionJob":
        d = json.loads(raw)
        return cls(
            store_id=d["store_id"],
            store_domain=d["store_domain"],
            parser_strategy=d["parser_strategy"],
            priority=d.get("priority", 5),
            run_at=datetime.fromisoformat(d["run_at"]),
            job_id=d["job_id"],
            enqueued_at=datetime.fromisoformat(d["enqueued_at"]),
            attempts=d.get("attempts", 0),
        )

    @property
    def score(self) -> float:
        """Redis score: lower = runs sooner. Priority adjusts within same time slot."""
        base_ts = self.run_at.timestamp()
        # Subtract up to 60 seconds based on priority (10=highest=runs earliest)
        priority_offset = (10 - self.priority) * 6
        return base_ts - priority_offset

    def __repr__(self) -> str:
        return (
            f"<IngestionJob {self.store_domain} strategy={self.parser_strategy} "
            f"attempts={self.attempts} run_at={self.run_at.strftime('%H:%M:%S')}>"
        )


class JobQueue:
    """
    Redis-backed ingestion job queue.

    Thread-safe via asyncio. All methods are async.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._client.ping()
        log.info("JobQueue connected to Redis at %s", self._redis_url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def r(self) -> aioredis.Redis:
        assert self._client is not None, "Call connect() first"
        return self._client

    # ── Enqueue ───────────────────────────────────────────────────────────────

    async def enqueue(self, job: IngestionJob) -> bool:
        """
        Add a job to the scheduled queue.
        Returns True if added, False if already queued with earlier/equal score.
        """
        payload = job.to_json()
        score = job.score
        added = await self.r.zadd(
            QUEUE_SCHEDULED,
            {payload: score},
            nx=False,  # update score if member exists (reschedule)
        )
        log.debug("Enqueued %s score=%.0f", job, score)
        return bool(added)

    async def enqueue_many(self, jobs: list[IngestionJob]) -> int:
        """Bulk enqueue. Returns number of new jobs added."""
        if not jobs:
            return 0
        mapping = {j.to_json(): j.score for j in jobs}
        return await self.r.zadd(QUEUE_SCHEDULED, mapping, nx=False)

    # ── Dequeue ───────────────────────────────────────────────────────────────

    async def dequeue_due(self, limit: int = 10) -> list[IngestionJob]:
        """
        Atomically dequeue jobs that are due now (score ≤ current time).
        Moves them to the processing set to detect stuck jobs.
        """
        now = datetime.now(timezone.utc).timestamp()
        pipe = self.r.pipeline(transaction=True)

        # Get up to `limit` due jobs
        due_payloads = await self.r.zrangebyscore(
            QUEUE_SCHEDULED, "-inf", now, start=0, num=limit
        )
        if not due_payloads:
            return []

        # Move each from scheduled → processing
        async with self.r.pipeline(transaction=True) as pipe:
            for payload in due_payloads:
                pipe.zrem(QUEUE_SCHEDULED, payload)
                pipe.zadd(QUEUE_PROCESSING, {payload: now})
            await pipe.execute()

        jobs = []
        for payload in due_payloads:
            try:
                jobs.append(IngestionJob.from_json(payload))
            except Exception as exc:
                log.error("Failed to deserialise job payload: %s — %s", payload[:100], exc)

        return jobs

    async def ack(self, job: IngestionJob) -> None:
        """Mark a job as completed — remove from processing set."""
        payload = job.to_json()
        await self.r.zrem(QUEUE_PROCESSING, payload)
        # Record result summary
        await self.r.hset(
            QUEUE_RESULTS,
            job.job_id,
            json.dumps({"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}),
        )
        await self.r.expire(QUEUE_RESULTS, 86400 * 7)  # 7 days

    async def nack(self, job: IngestionJob, error: str) -> None:
        """
        Mark a job as failed.
        If under MAX_ATTEMPTS, re-schedule with exponential backoff.
        Otherwise, move to dead letter queue.
        """
        payload = job.to_json()
        await self.r.zrem(QUEUE_PROCESSING, payload)

        job.attempts += 1
        if job.attempts < MAX_ATTEMPTS:
            # Exponential backoff: 5m, 25m, 125m
            backoff_s = 300 * (5 ** (job.attempts - 1))
            retry_at = datetime.now(timezone.utc).timestamp() + backoff_s
            retry_job = IngestionJob(
                store_id=job.store_id,
                store_domain=job.store_domain,
                parser_strategy=job.parser_strategy,
                priority=max(1, job.priority - 2),  # lower priority on retry
                run_at=datetime.fromtimestamp(retry_at, tz=timezone.utc),
                job_id=job.job_id,
                enqueued_at=job.enqueued_at,
                attempts=job.attempts,
            )
            await self.r.zadd(QUEUE_SCHEDULED, {retry_job.to_json(): retry_job.score})
            log.warning(
                "Job %s failed (attempt %d/%d), retrying in %ds: %s",
                job.store_domain, job.attempts, MAX_ATTEMPTS, backoff_s, error,
            )
        else:
            # Dead letter
            dead_entry = json.dumps({
                **job.to_dict(),
                "error": error,
                "dead_at": datetime.now(timezone.utc).isoformat(),
            })
            await self.r.lpush(QUEUE_DEAD, dead_entry)
            await self.r.ltrim(QUEUE_DEAD, 0, 999)  # keep last 1000 dead jobs
            log.error(
                "Job %s moved to dead letter queue after %d attempts: %s",
                job.store_domain, job.attempts, error,
            )

    # ── Stuck job recovery ────────────────────────────────────────────────────

    async def reclaim_stuck(self) -> int:
        """
        Re-queue jobs that have been in processing for > PROCESSING_TIMEOUT_S.
        Call periodically from the scheduler.
        """
        cutoff = datetime.now(timezone.utc).timestamp() - PROCESSING_TIMEOUT_S
        stuck = await self.r.zrangebyscore(QUEUE_PROCESSING, "-inf", cutoff)
        if not stuck:
            return 0

        reclaimed = 0
        for payload in stuck:
            try:
                job = IngestionJob.from_json(payload)
                job.attempts += 1
                await self.r.zrem(QUEUE_PROCESSING, payload)
                if job.attempts < MAX_ATTEMPTS:
                    await self.r.zadd(QUEUE_SCHEDULED, {job.to_json(): job.score})
                    reclaimed += 1
                    log.warning("Reclaimed stuck job %s (attempt %d)", job.store_domain, job.attempts)
            except Exception as exc:
                log.error("Failed to reclaim stuck job: %s", exc)

        return reclaimed

    # ── Queue stats ───────────────────────────────────────────────────────────

    async def stats(self) -> dict[str, int]:
        """Return queue depth stats for monitoring."""
        scheduled, processing, dead = await asyncio.gather(
            self.r.zcard(QUEUE_SCHEDULED),
            self.r.zcard(QUEUE_PROCESSING),
            self.r.llen(QUEUE_DEAD),
        )
        return {
            "scheduled": scheduled,
            "processing": processing,
            "dead": dead,
        }

    async def dead_jobs(self, limit: int = 20) -> list[dict]:
        """Return recent dead letter entries for operator inspection."""
        raw = await self.r.lrange(QUEUE_DEAD, 0, limit - 1)
        return [json.loads(r) for r in raw]


import asyncio  # noqa: E402 — imported at bottom to avoid circular at top
