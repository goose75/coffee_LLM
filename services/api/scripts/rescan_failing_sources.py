"""
rescan_failing_sources.py — re-run domain detection for sources whose latest
ingestion run failed with a 404 / FEED_NOT_JSON / DNS_OR_CONNECT_ERROR bucket.

These failures usually mean the store isn't actually Shopify (or the feed has
moved), so re-detecting parser_strategy is the right move. After this runs,
the affected stores will have a fresh strategy and source_pages, ready for
the next ingestion attempt.

Usage:
    docker exec coffee_api python scripts/rescan_failing_sources.py
    docker exec coffee_api python scripts/rescan_failing_sources.py --dry-run
    docker exec coffee_api python scripts/rescan_failing_sources.py --domains a.com,b.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from app.core.database import AsyncSessionLocal
from app.models.enums import RunStatus
from app.models.ingestion_run import IngestionRun
from app.models.store import Store
from app.services.source_inventory import SourceInventoryImporter


# Patterns in the LATEST run's first error message that indicate a strategy
# mismatch — i.e. the store isn't Shopify (or feed has moved).
TRIGGER_SUBSTRINGS = [
    "404 Not Found",
    "FEED_NOT_JSON",
    "DNS_OR_CONNECT_ERROR",
    "HTTP_404",
    "Server disconnected",       # transient — rescan won't fix it but won't hurt
]


async def candidates(session, explicit_domains: list[str] | None) -> list[Store]:
    if explicit_domains:
        stmt = select(Store).where(Store.domain.in_(explicit_domains))
        return list((await session.execute(stmt)).scalars().all())

    stores = (await session.execute(select(Store).where(Store.active_flag == True))).scalars().all()
    last_run_stmt = (
        select(IngestionRun)
        .order_by(IngestionRun.store_id, desc(IngestionRun.started_at))
        .distinct(IngestionRun.store_id)
    )
    last_runs = {r.store_id: r for r in (await session.execute(last_run_stmt)).scalars().all()}

    out: list[Store] = []
    for s in stores:
        run = last_runs.get(s.id)
        # Stores that have never been ingested (no run + never crawled) are
        # also worth rescanning so the strategy can be set before the first
        # ingest attempt instead of after a failed one.
        if run is None:
            if s.last_successful_crawl_at is None:
                out.append(s)
            continue
        if run.status != RunStatus.failed:
            continue
        first_msg = ((run.errors or [{}])[0] or {}).get("message", "") or ""
        if any(sub in first_msg for sub in TRIGGER_SUBSTRINGS):
            out.append(s)
    return out


async def run(domains: list[str] | None, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        targets = await candidates(session, domains)

        if not targets:
            print("No stores match the rescan triggers.")
            return 0

        print(f"Will rescan {len(targets)} stores:")
        for s in targets:
            print(f"  {s.domain}")
        if dry_run:
            print("\n--dry-run: no changes written.")
            return 0

        importer = SourceInventoryImporter(session=session)
        for s in targets:
            try:
                result = await importer.rescan_store(s)
                print(
                    f"  {s.domain:40} → strategy={result['parser_strategy']:<10} "
                    f"reachable={result['reachable']}  pages={result['pages_upserted']}"
                )
            except Exception as exc:
                print(f"  {s.domain:40} ! rescan failed: {exc}")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--domains", type=str, default=None,
                   help="comma-separated list of domains to rescan (skip auto-detect)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    domains = [d.strip() for d in args.domains.split(",")] if args.domains else None
    return asyncio.run(run(domains, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
