"""
reingest_all.py — run the Shopify ingestion pipeline for every active
Shopify-strategy store, sequentially.

Useful right after a bug fix: once the new code is live, every store needs a
fresh run before the diagnostic shows the new state. This script does that
without you having to click "Ingest" 30+ times.

Concurrency is intentionally 1: each pipeline run hits the same Postgres
connection pool and we don't want to thrash. For a few dozen UK roasters this
takes a couple of minutes total.

Usage:
    docker exec coffee_api python scripts/reingest_all.py
    docker exec coffee_api python scripts/reingest_all.py --only-failing
    docker exec coffee_api python scripts/reingest_all.py --domains a.com,b.com
    docker exec coffee_api python scripts/reingest_all.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from app.core.database import AsyncSessionLocal
from app.models.enums import ParserStrategy, RunStatus
from app.models.ingestion_run import IngestionRun
from app.models.store import Store
from app.services.shopify import ShopifyIngestionPipeline


async def select_stores(
    session, only_failing: bool, explicit: list[str] | None
) -> list[Store]:
    if explicit:
        stmt = select(Store).where(Store.domain.in_(explicit))
        return list((await session.execute(stmt)).scalars().all())

    stmt = select(Store).where(
        Store.active_flag == True,
        Store.parser_strategy == ParserStrategy.shopify,
    ).order_by(Store.name)
    stores = list((await session.execute(stmt)).scalars().all())

    if not only_failing:
        return stores

    last_run_stmt = (
        select(IngestionRun)
        .order_by(IngestionRun.store_id, desc(IngestionRun.started_at))
        .distinct(IngestionRun.store_id)
    )
    last = {r.store_id: r for r in (await session.execute(last_run_stmt)).scalars().all()}

    keep: list[Store] = []
    for s in stores:
        run = last.get(s.id)
        if run is None or run.status in (RunStatus.failed, RunStatus.partial, RunStatus.running):
            keep.append(s)
    return keep


async def run(only_failing: bool, domains: list[str] | None, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        targets = await select_stores(session, only_failing, domains)
        if not targets:
            print("No stores match.")
            return 0

        print(f"Re-ingesting {len(targets)} stores:")
        for s in targets:
            print(f"  {s.domain}")
        if dry_run:
            print("\n--dry-run: nothing run.")
            return 0
        print()

        ok = partial = failed = 0
        start = time.monotonic()
        for s in targets:
            t0 = time.monotonic()
            try:
                pipeline = ShopifyIngestionPipeline(session=session, store=s)
                run_obj = await pipeline.run()
                status = run_obj.status.value
                ok      += int(status == "completed")
                partial += int(status == "partial")
                failed  += int(status == "failed")
                err_count = len(run_obj.errors or [])
                print(
                    f"  {s.domain:40} → {status:<10} seen={run_obj.records_seen:<4} "
                    f"created={run_obj.records_created:<4} errors={err_count:<3} "
                    f"({time.monotonic() - t0:.1f}s)"
                )
            except Exception as exc:
                failed += 1
                print(f"  {s.domain:40} ! pipeline raised: {exc}")

        total_s = time.monotonic() - start
        print(f"\nDone. completed={ok} partial={partial} failed={failed} ({total_s:.1f}s total)")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only-failing", action="store_true",
                   help="restrict to stores whose latest run was failed/partial/running")
    p.add_argument("--domains", type=str, default=None,
                   help="comma-separated explicit domain list")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    domains = [d.strip() for d in args.domains.split(",")] if args.domains else None
    return asyncio.run(run(args.only_failing, domains, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
