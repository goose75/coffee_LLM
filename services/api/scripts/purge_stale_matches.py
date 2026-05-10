"""
purge_stale_matches.py — clean up the pending-match queue.

Removes two classes of debris that accumulate in the canonical_matches
table over time:

  1. Low-confidence pendings — match records whose confidence is below
     today's review threshold (0.75). These got created when older
     versions of the matcher had different thresholds; they were never
     going to be human-actionable and they pollute the analytics view.

  2. Non-coffee matches — listings whose titles match the (now broader)
     coffee-classifier exclusion patterns (subscriptions, loyalty SKUs,
     gift boxes, equipment that slipped through earlier ingestions).
     Both the pending match AND the underlying listing get marked: the
     match becomes `rejected`, the listing's `active_flag` flips false
     so it stops being matched against on subsequent runs.

Default behaviour is dry-run. Pass --apply to actually write changes.

Usage:
    docker exec coffee_api python scripts/purge_stale_matches.py
    docker exec coffee_api python scripts/purge_stale_matches.py --apply
    docker exec coffee_api python scripts/purge_stale_matches.py --apply --review-threshold 0.75
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.bean_listing import BeanListing
from app.models.enums import ListingStatus, ReviewStatus
from app.models.resolution import CanonicalMatch
from app.services.shopify.coffee_classifier import is_coffee_product


PURGE_NOTE_LOW_CONF = "purged: confidence below current review threshold"
PURGE_NOTE_NOT_COFFEE = "purged: listing reclassified as non-coffee by tightened classifier"


async def purge(review_threshold: float, apply: bool) -> dict:
    async with AsyncSessionLocal() as session:
        # Pull every pending match with its listing — needed for both passes
        stmt = (
            select(CanonicalMatch)
            .where(CanonicalMatch.review_status == "pending")
            .options(selectinload(CanonicalMatch.bean_listing))
        )
        pendings = (await session.execute(stmt)).scalars().all()

        low_conf: list[CanonicalMatch] = []
        non_coffee: list[CanonicalMatch] = []
        non_coffee_listing_ids: set = set()

        for m in pendings:
            l = m.bean_listing
            # Always check non-coffee classification first — if a listing is a
            # subscription / loyalty SKU / merch, we want to deactivate the
            # underlying listing regardless of whether the match was also
            # low-confidence. Otherwise the next ingestion will re-create it.
            if l is not None:
                shopify_like_dict = {
                    "title": l.raw_title or "",
                    "tags": [],
                    "product_type": "",
                }
                is_coffee, _reason = is_coffee_product(shopify_like_dict)
                if not is_coffee:
                    non_coffee.append(m)
                    non_coffee_listing_ids.add(l.id)
                    continue   # already accounted for; don't double-count as low_conf

            if (m.confidence_score or 0) < review_threshold:
                low_conf.append(m)

        print(f"Found {len(low_conf)} low-confidence pendings (< {review_threshold}).")
        print(f"Found {len(non_coffee)} non-coffee pendings (after re-classification).")
        print(f"  → {len(non_coffee_listing_ids)} underlying listing(s) will be deactivated.")

        if not apply:
            # Show a few samples so the operator can sanity-check
            print("\nSample low-confidence pendings:")
            for m in low_conf[:5]:
                print(f"  conf={m.confidence_score:.2f}  '{(m.bean_listing.raw_title or '')[:60]}'"
                      if m.bean_listing else f"  conf={m.confidence_score:.2f}  (orphaned)")
            print("\nSample non-coffee pendings:")
            for m in non_coffee[:5]:
                print(f"  '{(m.bean_listing.raw_title or '')[:60]}'")
            print("\n--dry-run by default. Pass --apply to write changes.")
            return {"low_conf": len(low_conf), "non_coffee": len(non_coffee), "applied": False}

        now = datetime.now(timezone.utc)
        for m in low_conf:
            m.review_status = ReviewStatus.rejected
            m.reviewed_at = now
            m.review_notes = PURGE_NOTE_LOW_CONF
        for m in non_coffee:
            m.review_status = ReviewStatus.rejected
            m.reviewed_at = now
            m.review_notes = PURGE_NOTE_NOT_COFFEE

        # Deactivate the listings that are now classified as non-coffee
        if non_coffee_listing_ids:
            listings_stmt = select(BeanListing).where(BeanListing.id.in_(non_coffee_listing_ids))
            for listing in (await session.execute(listings_stmt)).scalars().all():
                listing.active_flag = False
                listing.listing_status = ListingStatus.inactive

        await session.commit()

        return {
            "low_conf": len(low_conf),
            "non_coffee": len(non_coffee),
            "deactivated_listings": len(non_coffee_listing_ids),
            "applied": True,
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--review-threshold", type=float, default=0.75)
    p.add_argument("--apply", action="store_true", help="actually write changes (default is dry-run)")
    args = p.parse_args()
    summary = asyncio.run(purge(args.review_threshold, args.apply))
    print(f"\nDone: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
