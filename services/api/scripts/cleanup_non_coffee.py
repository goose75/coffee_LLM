#!/usr/bin/env python3
"""
cleanup_non_coffee.py — Remove non-coffee listings from the database.

Runs the coffee_classifier against every existing bean_listing and deletes
those that fail the coffee check.  Also cleans up orphaned canonical_beans
(those with no remaining listings).

Run inside the API container:
  docker exec coffee_api python scripts/cleanup_non_coffee.py

Options:
  --dry-run     Print what would be deleted without deleting
  --limit N     Only process N listings (default: all)
"""

from __future__ import annotations
import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def run(dry_run: bool, limit: int | None, yes: bool = False) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.bean_listing import BeanListing
    from app.models.canonical_bean import CanonicalBean
    from app.models.resolution import CanonicalMatch
    from app.services.shopify.coffee_classifier import is_coffee_product
    from sqlalchemy import select, delete, func, text

    total_checked = 0
    total_deleted = 0
    non_coffee: list[tuple[str, str, str]] = []  # (id, title, reason)

    print("Loading listings...")

    async with AsyncSessionLocal() as session:
        q = select(BeanListing).order_by(BeanListing.first_seen_at)
        if limit:
            q = q.limit(limit)
        result = await session.execute(q)
        listings = result.scalars().all()
        print(f"Loaded {len(listings)} listings")

        for listing in listings:
            total_checked += 1
            # Reconstruct a minimal product dict for the classifier
            product = {
                "title": listing.raw_title or "",
                "product_type": "",
                "tags": [],
            }
            is_coffee, reason = is_coffee_product(product)
            if not is_coffee:
                non_coffee.append((str(listing.id), listing.raw_title or "", reason))

        print(f"\nFound {len(non_coffee)} non-coffee listings to remove:")
        for lid, title, reason in non_coffee[:20]:
            print(f"  [{reason[:40]}] {title[:60]}")
        if len(non_coffee) > 20:
            print(f"  ... and {len(non_coffee) - 20} more")

        if dry_run:
            print("\nDRY RUN — no changes written")
            return

        if not non_coffee:
            print("\nNothing to delete.")
            return

        if not yes:
            confirm = input(f"\nDelete {len(non_coffee)} listings? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return
        else:
            print(f"\nProceeding to delete {len(non_coffee)} listings (--yes flag set)")

        # Delete canonical_matches for these listings first (FK constraint)
        ids = [lid for lid, _, _ in non_coffee]
        from sqlalchemy import text as sql_text
        import uuid

        print(f"Deleting {len(ids)} listings and their matches...")

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i+batch_size]
            uuids = [uuid.UUID(bid) for bid in batch]

            # Delete matches
            await session.execute(
                delete(CanonicalMatch).where(CanonicalMatch.bean_listing_id.in_(uuids))
            )
            # Delete listings
            await session.execute(
                delete(BeanListing).where(BeanListing.id.in_(uuids))
            )
            total_deleted += len(batch)
            print(f"  Deleted batch {i//batch_size + 1} ({total_deleted}/{len(ids)})")

        await session.commit()
        print(f"\n✓ Deleted {total_deleted} non-coffee listings")

        # Cleanup orphaned canonical_beans (no listings attached)
        print("Cleaning up orphaned canonical beans...")
        result2 = await session.execute(
            select(CanonicalBean.id).where(
                ~CanonicalBean.id.in_(
                    select(BeanListing.canonical_bean_id).where(
                        BeanListing.canonical_bean_id.is_not(None)
                    ).scalar_subquery()
                )
            )
        )
        orphan_ids = [row[0] for row in result2.fetchall()]
        if orphan_ids:
            await session.execute(
                delete(CanonicalMatch).where(
                    CanonicalMatch.proposed_canonical_bean_id.in_(orphan_ids)
                )
            )
            await session.execute(
                delete(CanonicalBean).where(CanonicalBean.id.in_(orphan_ids))
            )
            await session.commit()
            print(f"✓ Removed {len(orphan_ids)} orphaned canonical beans")
        else:
            print("✓ No orphaned canonical beans")

        # Final counts
        r3 = await session.execute(select(func.count()).select_from(BeanListing))
        r4 = await session.execute(select(func.count()).select_from(CanonicalBean))
        print(f"\nFinal state: {r3.scalar()} listings, {r4.scalar()} canonical beans")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove non-coffee listings from DB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run, args.limit, args.yes))


if __name__ == "__main__":
    main()
