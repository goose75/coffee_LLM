"""
reap_stale_runs.py — close out IngestionRuns left in `running` state.

A run is considered stale if its status is `running` and `started_at` is older
than `--older-than` hours (default 2). Stale runs are marked `failed` with an
explanatory error so the latest-run logic in /admin/sources doesn't keep
showing them as "in flight" forever.

Usage:
    docker exec coffee_api python scripts/reap_stale_runs.py
    docker exec coffee_api python scripts/reap_stale_runs.py --older-than 1 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import RunStatus
from app.models.ingestion_run import IngestionRun


REAP_MESSAGE = "REAPED: run was left in 'running' state — process likely died before _close_run."


async def reap(older_than_hours: int, dry_run: bool) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(IngestionRun)
            .where(IngestionRun.status == RunStatus.running)
            .where(IngestionRun.started_at < cutoff)
        )
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            print(f"No stale `running` runs older than {older_than_hours}h found.")
            return 0

        print(f"Found {len(rows)} stale runs:")
        for r in rows:
            print(f"  {r.id}  store={r.store_id}  started_at={r.started_at}")

        if dry_run:
            print("\n--dry-run: no changes written.")
            return 0

        for r in rows:
            r.status = RunStatus.failed
            r.completed_at = datetime.now(timezone.utc)
            existing = list(r.errors or [])
            existing.append({"message": REAP_MESSAGE, "url": None, "detail": None})
            r.errors = existing
        await session.commit()
        print(f"\nMarked {len(rows)} runs as failed.")
        return len(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--older-than", type=int, default=2, help="hours")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    return asyncio.run(reap(args.older_than, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
