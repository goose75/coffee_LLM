"""
Tests for the ingestion worker stack.

Coverage:
  TestIngestionJob      — serialisation, score computation, priority
  TestJobQueue          — enqueue, dequeue, ack, nack, retry, dead letter, reclaim
  TestScheduler         — due store detection, job creation
  TestDispatcher        — strategy routing, result handling
  TestWorkerIntegration — end-to-end flow with mock queue and dispatcher
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_job(
    store_id: str = "00000000-0000-0000-0000-000000000001",
    domain: str = "example.co.uk",
    strategy: str = "shopify",
    priority: int = 5,
    attempts: int = 0,
    run_at: datetime | None = None,
) -> "IngestionJob":
    from ingestion.queue import IngestionJob
    return IngestionJob(
        store_id=store_id,
        store_domain=domain,
        parser_strategy=strategy,
        priority=priority,
        attempts=attempts,
        run_at=run_at or datetime.now(timezone.utc),
    )


def _make_redis_mock(responses: dict | None = None) -> MagicMock:
    """Build a mock aioredis client that returns preset values."""
    r = MagicMock()
    r.ping = AsyncMock(return_value=True)
    r.zadd = AsyncMock(return_value=1)
    r.zrem = AsyncMock(return_value=1)
    r.zrangebyscore = AsyncMock(return_value=[])
    r.zcard = AsyncMock(return_value=0)
    r.llen = AsyncMock(return_value=0)
    r.lrange = AsyncMock(return_value=[])
    r.lpush = AsyncMock(return_value=1)
    r.ltrim = AsyncMock(return_value=True)
    r.hset = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    r.aclose = AsyncMock()
    # Pipeline context manager
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.zrem = MagicMock()
    pipe.zadd = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, 1])
    r.pipeline = MagicMock(return_value=pipe)
    if responses:
        for method, retval in responses.items():
            getattr(r, method).return_value = retval
    return r


# ─────────────────────────────────────────────────────────────────────────────
# TestIngestionJob
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestionJob:

    def test_round_trip_json(self):
        from ingestion.queue import IngestionJob
        job = _make_job(domain="test.co.uk", strategy="schema_org")
        restored = IngestionJob.from_json(job.to_json())
        assert restored.store_id == job.store_id
        assert restored.store_domain == job.store_domain
        assert restored.parser_strategy == job.parser_strategy
        assert restored.job_id == job.job_id
        assert restored.attempts == 0

    def test_to_dict_has_all_fields(self):
        job = _make_job()
        d = job.to_dict()
        for key in ("job_id", "store_id", "store_domain", "parser_strategy",
                    "priority", "run_at", "enqueued_at", "attempts"):
            assert key in d

    def test_score_lower_for_higher_priority(self):
        """Higher priority jobs should have a lower score (run sooner)."""
        run_at = datetime.now(timezone.utc)
        low_priority = _make_job(priority=1, run_at=run_at)
        high_priority = _make_job(priority=10, run_at=run_at)
        assert high_priority.score < low_priority.score

    def test_score_earlier_run_at_is_lower(self):
        """Earlier run_at → lower score → dequeued first."""
        now = datetime.now(timezone.utc)
        earlier = _make_job(run_at=now - timedelta(hours=1))
        later = _make_job(run_at=now + timedelta(hours=1))
        assert earlier.score < later.score

    def test_repr_contains_domain(self):
        job = _make_job(domain="squaremile.co.uk")
        assert "squaremile.co.uk" in repr(job)

    def test_job_id_is_unique(self):
        j1 = _make_job()
        j2 = _make_job()
        assert j1.job_id != j2.job_id

    def test_custom_job_id_preserved(self):
        from ingestion.queue import IngestionJob
        job = IngestionJob(
            store_id="a", store_domain="x.com", parser_strategy="html",
            job_id="fixed-id-123"
        )
        assert job.job_id == "fixed-id-123"


# ─────────────────────────────────────────────────────────────────────────────
# TestJobQueue
# ─────────────────────────────────────────────────────────────────────────────

class TestJobQueue:

    def _make_queue_with_mock(self, responses=None):
        from ingestion.queue import JobQueue
        q = JobQueue.__new__(JobQueue)
        q._redis_url = "redis://test"
        q._client = _make_redis_mock(responses)
        return q

    @pytest.mark.asyncio
    async def test_enqueue_calls_zadd(self):
        q = self._make_queue_with_mock()
        job = _make_job()
        await q.enqueue(job)
        assert q._client.zadd.called
        # First arg is the key
        call_args = q._client.zadd.call_args
        assert call_args.args[0] == "coffee:jobs:scheduled"

    @pytest.mark.asyncio
    async def test_enqueue_many_bulk(self):
        q = self._make_queue_with_mock({"zadd": 3})
        jobs = [_make_job(domain=f"store{i}.co.uk") for i in range(3)]
        added = await q.enqueue_many(jobs)
        assert added == 3

    @pytest.mark.asyncio
    async def test_enqueue_many_empty(self):
        q = self._make_queue_with_mock()
        added = await q.enqueue_many([])
        assert added == 0
        assert not q._client.zadd.called

    @pytest.mark.asyncio
    async def test_dequeue_due_empty_queue(self):
        q = self._make_queue_with_mock({"zrangebyscore": []})
        result = await q.dequeue_due(limit=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_dequeue_due_returns_jobs(self):
        job = _make_job(domain="due.co.uk")
        q = self._make_queue_with_mock({"zrangebyscore": [job.to_json()]})
        result = await q.dequeue_due(limit=5)
        assert len(result) == 1
        assert result[0].store_domain == "due.co.uk"

    @pytest.mark.asyncio
    async def test_dequeue_skips_invalid_payload(self):
        q = self._make_queue_with_mock({"zrangebyscore": ["not-valid-json"]})
        result = await q.dequeue_due(limit=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_ack_removes_from_processing(self):
        q = self._make_queue_with_mock()
        job = _make_job()
        await q.ack(job)
        assert q._client.zrem.called
        assert q._client.zrem.call_args.args[0] == "coffee:jobs:processing"

    @pytest.mark.asyncio
    async def test_nack_retry_schedules_backoff(self):
        """Under MAX_ATTEMPTS, nack should re-enqueue with backoff."""
        q = self._make_queue_with_mock()
        job = _make_job(attempts=0)
        await q.nack(job, "transient error")
        # Should re-enqueue (zadd to scheduled), not dead letter
        assert q._client.zadd.called
        assert not q._client.lpush.called  # not dead letter

    @pytest.mark.asyncio
    async def test_nack_dead_letter_after_max_attempts(self):
        """After MAX_ATTEMPTS, nack should push to dead letter queue."""
        from ingestion.queue import MAX_ATTEMPTS
        q = self._make_queue_with_mock()
        job = _make_job(attempts=MAX_ATTEMPTS - 1)  # will become MAX_ATTEMPTS
        await q.nack(job, "fatal error")
        # Should go to dead letter
        assert q._client.lpush.called
        assert q._client.lpush.call_args.args[0] == "coffee:jobs:dead"

    @pytest.mark.asyncio
    async def test_nack_increments_attempts_on_retry(self):
        """The retry job should have attempts+1."""
        q = self._make_queue_with_mock()
        job = _make_job(attempts=0)
        await q.nack(job, "error")
        # Get the payload that was zadd'd
        call_args = q._client.zadd.call_args
        # second positional arg is the mapping dict
        mapping = call_args.args[1]
        payload_json = list(mapping.keys())[0]
        import json
        payload = json.loads(payload_json)
        assert payload["attempts"] == 1

    @pytest.mark.asyncio
    async def test_stats_returns_counts(self):
        q = self._make_queue_with_mock({"zcard": 10, "llen": 2})
        # Mock separate calls for scheduled vs processing zcard
        q._client.zcard = AsyncMock(side_effect=[10, 5])
        stats = await q.stats()
        assert "scheduled" in stats
        assert "dead" in stats

    @pytest.mark.asyncio
    async def test_reclaim_stuck_returns_count(self):
        """Stuck processing jobs should be re-queued."""
        job = _make_job()
        q = self._make_queue_with_mock({"zrangebyscore": [job.to_json()]})
        count = await q.reclaim_stuck()
        assert count == 1
        assert q._client.zadd.called

    @pytest.mark.asyncio
    async def test_dead_jobs_returns_parsed_entries(self):
        entry = json.dumps({"job_id": "abc", "store_domain": "dead.co.uk"})
        q = self._make_queue_with_mock({"lrange": [entry]})
        dead = await q.dead_jobs(limit=5)
        assert len(dead) == 1
        assert dead[0]["store_domain"] == "dead.co.uk"


# ─────────────────────────────────────────────────────────────────────────────
# TestScheduler
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduler:

    def _make_scheduler(self, due_stores=None):
        from ingestion.scheduler import IngestionScheduler
        queue = MagicMock()
        queue.enqueue_many = AsyncMock(return_value=len(due_stores or []))
        queue.reclaim_stuck = AsyncMock(return_value=0)
        queue.stats = AsyncMock(return_value={"scheduled": 0, "processing": 0, "dead": 0})

        sched = IngestionScheduler.__new__(IngestionScheduler)
        sched._queue = queue
        sched._db_url = "postgresql+asyncpg://test"
        sched._last_reclaim = 0.0
        sched._last_stats_log = 0.0
        sched._due_stores_override = due_stores
        return sched, queue

    @pytest.mark.asyncio
    async def test_tick_enqueues_due_stores(self):
        due = [
            {"id": "00000000-0000-0000-0000-000000000001", "domain": "shop.co.uk",
             "parser_strategy": "shopify", "never_crawled": True},
        ]
        sched, queue = self._make_scheduler(due)

        with patch.object(sched, "_find_due_stores", AsyncMock(return_value=due)):
            await sched._tick()

        assert queue.enqueue_many.called
        jobs = queue.enqueue_many.call_args.args[0]
        assert len(jobs) == 1
        assert jobs[0].store_domain == "shop.co.uk"

    @pytest.mark.asyncio
    async def test_tick_skips_when_no_due_stores(self):
        sched, queue = self._make_scheduler([])
        with patch.object(sched, "_find_due_stores", AsyncMock(return_value=[])):
            await sched._tick()
        queue.enqueue_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_never_crawled_gets_higher_priority(self):
        due = [
            {"id": "00000000-0000-0000-0000-000000000001", "domain": "new.co.uk",
             "parser_strategy": "shopify", "never_crawled": True},
            {"id": "00000000-0000-0000-0000-000000000002", "domain": "old.co.uk",
             "parser_strategy": "shopify", "never_crawled": False},
        ]
        sched, queue = self._make_scheduler(due)
        with patch.object(sched, "_find_due_stores", AsyncMock(return_value=due)):
            await sched._tick()

        jobs = queue.enqueue_many.call_args.args[0]
        new_job = next(j for j in jobs if j.store_domain == "new.co.uk")
        old_job = next(j for j in jobs if j.store_domain == "old.co.uk")
        assert new_job.priority > old_job.priority

    @pytest.mark.asyncio
    async def test_strategy_enum_cleaned(self):
        """Parser strategy may arrive as 'ParserStrategy.shopify' — should be cleaned."""
        due = [
            {"id": "00000000-0000-0000-0000-000000000001", "domain": "x.co.uk",
             "parser_strategy": "ParserStrategy.schema_org", "never_crawled": False},
        ]
        sched, queue = self._make_scheduler(due)
        with patch.object(sched, "_find_due_stores", AsyncMock(return_value=due)):
            await sched._tick()

        jobs = queue.enqueue_many.call_args.args[0]
        assert jobs[0].parser_strategy == "schema_org"


# ─────────────────────────────────────────────────────────────────────────────
# TestDispatcher
# ─────────────────────────────────────────────────────────────────────────────

class TestDispatcher:

    def _make_dispatcher(self) -> "IngestionDispatcher":
        from ingestion.dispatcher import IngestionDispatcher
        d = IngestionDispatcher.__new__(IngestionDispatcher)
        d._engine = MagicMock()
        d._engine.dispose = AsyncMock()
        session_mock = AsyncMock()
        session_mock.__aenter__ = AsyncMock(return_value=session_mock)
        session_mock.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=session_mock)
        d._session_factory = factory
        d._session = session_mock
        return d

    @pytest.mark.asyncio
    async def test_dispatch_store_not_found_returns_failure(self):
        dispatcher = self._make_dispatcher()
        job = _make_job()
        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=None)):
            result = await dispatcher.dispatch(job)
        assert result.success is False
        assert any("not found" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_dispatch_unknown_strategy_returns_failure(self):
        dispatcher = self._make_dispatcher()
        job = _make_job(strategy="unknown_strategy")
        fake_store = MagicMock()
        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=fake_store)):
            result = await dispatcher.dispatch(job)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_dispatch_shopify_success(self):
        dispatcher = self._make_dispatcher()
        job = _make_job(strategy="shopify")
        fake_store = MagicMock()

        # Mock a successful Shopify pipeline run
        mock_counters = MagicMock()
        mock_counters.products_created = 5
        mock_counters.products_updated = 2
        mock_counters.price_history_writes = 14
        mock_counters.pages_fetched = 2
        mock_counters.errors = []

        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=mock_counters)

        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=fake_store)):
            with patch("ingestion.dispatcher.ShopifyIngestionPipeline", return_value=mock_pipeline):
                with patch("ingestion.dispatcher.get_storage_backend", return_value=MagicMock()):
                    with patch("ingestion.dispatcher.settings", STORAGE_BACKEND="local", STORAGE_LOCAL_PATH="/tmp"):
                        result = await dispatcher.dispatch(job)

        assert result.success is True
        assert result.listings_created == 5
        assert result.listings_updated == 2
        assert result.price_writes == 14

    @pytest.mark.asyncio
    async def test_dispatch_network_error_is_soft_failure(self):
        dispatcher = self._make_dispatcher()
        job = _make_job(strategy="shopify")
        fake_store = MagicMock()

        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=fake_store)):
            with patch.object(dispatcher, "_run_shopify", AsyncMock(side_effect=ConnectionError("refused"))):
                result = await dispatcher.dispatch(job)

        assert result.success is False
        assert result.is_soft_failure is True

    @pytest.mark.asyncio
    async def test_dispatch_result_has_duration(self):
        dispatcher = self._make_dispatcher()
        job = _make_job()
        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=None)):
            result = await dispatcher.dispatch(job)
        assert result.duration_s >= 0

    @pytest.mark.asyncio
    async def test_dispatch_timeout_is_soft_failure(self):
        dispatcher = self._make_dispatcher()
        job = _make_job(strategy="shopify")
        fake_store = MagicMock()

        with patch.object(dispatcher, "_get_store", AsyncMock(return_value=fake_store)):
            with patch.object(dispatcher, "_run_shopify", AsyncMock(side_effect=asyncio.TimeoutError())):
                result = await dispatcher.dispatch(job)

        assert result.success is False
        assert result.is_soft_failure is True


# ─────────────────────────────────────────────────────────────────────────────
# TestWorkerIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkerIntegration:
    """Integration tests for the worker coroutine — uses mocked queue and dispatcher."""

    @pytest.mark.asyncio
    async def test_worker_acks_successful_job(self):
        """Successful dispatch → ack called."""
        from ingestion.queue import JobQueue
        from ingestion.dispatcher import IngestionDispatcher, DispatchResult

        job = _make_job(domain="success.co.uk")

        queue = MagicMock()
        queue.dequeue_due = AsyncMock(side_effect=[[job], []])  # job then empty
        queue.ack = AsyncMock()
        queue.nack = AsyncMock()

        success_result = DispatchResult(
            job_id=job.job_id,
            store_id=job.store_id,
            store_domain=job.store_domain,
            strategy="shopify",
            success=True,
            pages_processed=1,
            listings_created=3,
        )
        success_result.completed_at = datetime.now(timezone.utc)

        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock(return_value=success_result)

        import ingestion.worker as wmod
        original_shutdown = wmod._shutdown
        wmod._shutdown = asyncio.Event()

        # Let the worker process one job then shut down
        async def set_shutdown_after_delay():
            await asyncio.sleep(0.1)
            wmod._shutdown.set()

        asyncio.create_task(set_shutdown_after_delay())
        await wmod.run_worker(0, queue, dispatcher)

        assert queue.ack.called
        assert not queue.nack.called

        wmod._shutdown = original_shutdown

    @pytest.mark.asyncio
    async def test_worker_nacks_failed_job(self):
        """Failed dispatch → nack called."""
        from ingestion.dispatcher import DispatchResult
        import ingestion.worker as wmod

        job = _make_job(domain="fail.co.uk")

        queue = MagicMock()
        queue.dequeue_due = AsyncMock(side_effect=[[job], []])
        queue.ack = AsyncMock()
        queue.nack = AsyncMock()

        fail_result = DispatchResult(
            job_id=job.job_id,
            store_id=job.store_id,
            store_domain=job.store_domain,
            strategy="shopify",
            success=False,
            errors=["Fetch failed"],
        )
        fail_result.completed_at = datetime.now(timezone.utc)

        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock(return_value=fail_result)

        original_shutdown = wmod._shutdown
        wmod._shutdown = asyncio.Event()

        async def set_shutdown():
            await asyncio.sleep(0.1)
            wmod._shutdown.set()

        asyncio.create_task(set_shutdown())
        await wmod.run_worker(0, queue, dispatcher)

        assert queue.nack.called
        assert not queue.ack.called

        wmod._shutdown = original_shutdown

    @pytest.mark.asyncio
    async def test_worker_handles_empty_queue_without_spinning(self):
        """Empty queue should wait POLL_INTERVAL_S, not busy-loop."""
        import ingestion.worker as wmod

        queue = MagicMock()
        queue.dequeue_due = AsyncMock(return_value=[])
        queue.ack = AsyncMock()
        queue.nack = AsyncMock()
        dispatcher = MagicMock()

        original_shutdown = wmod._shutdown
        wmod._shutdown = asyncio.Event()
        original_interval = wmod.POLL_INTERVAL_S
        wmod.POLL_INTERVAL_S = 0.05  # tiny for test speed

        async def set_shutdown():
            await asyncio.sleep(0.15)
            wmod._shutdown.set()

        asyncio.create_task(set_shutdown())
        await wmod.run_worker(0, queue, dispatcher)

        # Should have polled a small number of times (not thousands)
        poll_count = queue.dequeue_due.call_count
        assert 1 <= poll_count <= 5, f"Expected 1-5 polls, got {poll_count}"

        wmod._shutdown = original_shutdown
        wmod.POLL_INTERVAL_S = original_interval
