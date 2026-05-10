#!/usr/bin/env python3
"""
run_entity_resolution.py — Match all unlinked listings to canonical beans.

Run inside the API container:
  docker exec coffee_api python scripts/run_entity_resolution.py

Options:
  --limit N     Process at most N listings (default: 500)
  --batch N     Commit every N listings (default: 50)
  --dry-run     Show what would happen without writing

This script is safe to run multiple times — it skips already-linked listings.
"""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, "/app")


async def run(limit: int, batch_size: int, dry_run: bool) -> None:
    from app.core.database import AsyncSessionLocal
    from app.services.matching.service import CanonicalMatchingService
    from app.models.bean_listing import BeanListing
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as session:
        # Count unlinked
        count_result = await session.execute(
            select(func.count()).where(BeanListing.canonical_bean_id == None)
        )
        total_unlinked = count_result.scalar()
        print(f"Total unlinked listings: {total_unlinked}")
        print(f"Will process: {min(limit, total_unlinked)}")
        if dry_run:
            print("DRY RUN — no changes will be written")

    outcomes: dict[str, int] = {}
    errors = 0
    processed = 0

    async with AsyncSessionLocal() as session:
        svc = CanonicalMatchingService(session)

        offset = 0
        while processed < limit:
            batch_limit = min(batch_size, limit - processed)

            result = await session.execute(
                select(BeanListing)
                .where(BeanListing.canonical_bean_id == None)
                .order_by(BeanListing.first_seen_at.desc())
                .limit(batch_limit)
                .offset(offset)
            )
            listings = result.scalars().all()
            if not listings:
                break

            for listing in listings:
                try:
                    decision = await svc.match_listing(listing)
                    outcome = decision.outcome
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
                    processed += 1
                    if processed % 50 == 0 or processed == 1:
                        print(f"  [{processed}/{min(limit, total_unlinked)}] "
                              f"auto_accepted={outcomes.get('auto_accepted', 0)} "
                              f"review={outcomes.get('review_queued', 0)} "
                              f"new={outcomes.get('new_canonical', 0)}")
                except Exception as e:
                    errors += 1
                    print(f"  ERROR {listing.raw_title[:50]}: {e}")

            if not dry_run:
                await session.commit()
            else:
                await session.rollback()

            offset += batch_limit
            if len(listings) < batch_limit:
                break

    print(f"\nDone. Processed {processed} listings:")
    for outcome, count in sorted(outcomes.items()):
        print(f"  {outcome}: {count}")
    if errors:
        print(f"  errors: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run entity resolution on unlinked listings")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--batch", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.limit, args.batch, args.dry_run))


if __name__ == "__main__":
    main()
