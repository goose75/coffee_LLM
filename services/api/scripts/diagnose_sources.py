"""
diagnose_sources.py — print why each source is in a non-healthy state.

Reads the latest IngestionRun per Store, groups errors by the leading
classifier bucket (the prefix before ':'), and prints a table:

    DOMAIN                              HEALTH     STATUS    TOP ERRORS
    onyxcoffeespirits.co.uk             failing    failed    DNS_OR_CONNECT_ERROR ×1
    monmouthcoffee.co.uk                degraded   partial   name 'logger' is not defined ×287
    workshopcoffee.com                  healthy    completed
    ...

Run inside the api container:

    docker exec coffee_api python scripts/diagnose_sources.py
    # or
    docker exec coffee_api python scripts/diagnose_sources.py --json > diag.json

Optional flags:
    --only-failing    only show stores whose health is not "healthy"
    --top N           show top N error buckets per store (default 3)
    --since DAYS      only consider runs in the last N days (default 14)
    --json            emit JSON instead of a table
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Make the API package importable when run from inside the container.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.ingestion_run import IngestionRun
from app.models.store import Store
from app.schemas.sources import StoreListItem, LastRunSummary


def _bucket_of(message: str) -> str:
    """Take the substring before the first colon — that's our bucket label."""
    if not message:
        return "(empty)"
    return message.split(":", 1)[0].strip()


async def gather(session: AsyncSession, since_days: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    stores = (await session.execute(select(Store).order_by(Store.name))).scalars().all()

    # Latest run per store (DISTINCT ON), constrained to the lookback window.
    last_run_stmt = (
        select(IngestionRun)
        .where(IngestionRun.started_at >= cutoff)
        .order_by(IngestionRun.store_id, desc(IngestionRun.started_at))
        .distinct(IngestionRun.store_id)
    )
    last_runs = (await session.execute(last_run_stmt)).scalars().all()
    last_run_by_store = {r.store_id: r for r in last_runs}

    results: list[dict[str, Any]] = []
    for store in stores:
        run = last_run_by_store.get(store.id)
        item = StoreListItem.model_validate(store)
        if run is not None:
            errors_list = list(run.errors or [])
            buckets = Counter(_bucket_of((e or {}).get("message", "")) for e in errors_list)
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
                top_error_buckets=dict(buckets.most_common(5)),
            )
        results.append({
            "domain": store.domain,
            "name": store.name,
            "parser_strategy": store.parser_strategy.value if hasattr(store.parser_strategy, "value") else str(store.parser_strategy),
            "active": store.active_flag,
            "health": item.health_status,
            "last_run": item.last_run.model_dump(mode="json") if item.last_run else None,
        })
    return results


def render_table(rows: list[dict[str, Any]], top_n: int) -> str:
    lines: list[str] = []
    header = f"{'DOMAIN':<40} {'HEALTH':<10} {'STATUS':<10} {'SEEN':>6}  TOP ERRORS"
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        lr = r.get("last_run")
        status = (lr or {}).get("status", "—")
        seen = (lr or {}).get("records_seen", 0) if lr else 0
        buckets = (lr or {}).get("top_error_buckets", {}) if lr else {}
        top = ", ".join(f"{msg} ×{count}" for msg, count in list(buckets.items())[:top_n]) or "(none)"
        lines.append(f"{r['domain']:<40} {r['health']:<10} {status:<10} {seen:>6}  {top[:120]}")
    return "\n".join(lines)


async def main_async() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only-failing", action="store_true")
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--since", type=int, default=14, help="lookback window in days")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    async with AsyncSessionLocal() as session:
        rows = await gather(session, since_days=args.since)

    if args.only_failing:
        # `no_pipeline` is informational, not a failure — exclude unless the
        # operator explicitly asks for the full picture.
        rows = [r for r in rows if r["health"] not in ("healthy", "inactive", "no_pipeline")]

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        print(render_table(rows, top_n=args.top))
        print(f"\n{len(rows)} sources shown. Lookback: {args.since}d.")
        # Aggregate counts so the operator gets a one-line summary too.
        agg: Counter[str] = Counter()
        for r in rows:
            lr = r.get("last_run")
            if lr:
                for msg, count in (lr.get("top_error_buckets") or {}).items():
                    agg[msg] += count
        if agg:
            print("\nGlobal top error buckets:")
            for msg, count in agg.most_common(10):
                print(f"  {count:>6}  {msg}")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
