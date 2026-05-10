"""
backfill_listing_labels.py — populate origin_label_raw, process_label_raw,
and varietal_label_raw on existing BeanListings by mining their
raw_description field.

Most Shopify ingestions before today only extracted these labels from
product tags + product titles. Stores that put their detail in the body_html
description left every listing with blank labels, which made the matcher
unable to compare structured fields and produced a "sparse_canonical"
backlog. This script walks active listings missing any of those labels and
re-extracts from the description text using the same regex helpers the
extraction parsers use.

Idempotent: only writes to columns that are currently NULL/empty.

Usage:
    docker exec coffee_api python scripts/backfill_listing_labels.py
    docker exec coffee_api python scripts/backfill_listing_labels.py --limit 1000 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select

from app.core.database import AsyncSessionLocal
from app.models.bean_listing import BeanListing
from app.services.extraction.text_utils import (
    clean_html, extract_origin_country, extract_process, extract_varietal,
)


def _is_blank(v) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return not s


async def backfill(limit: int, dry_run: bool, batch_size: int) -> dict:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(BeanListing)
            .where(BeanListing.active_flag == True)  # noqa: E712
            .where(BeanListing.raw_description.isnot(None))
            .where(or_(
                BeanListing.origin_label_raw.is_(None),
                BeanListing.process_label_raw.is_(None),
                BeanListing.varietal_label_raw.is_(None),
            ))
            .limit(limit)
        )
        listings = (await session.execute(stmt)).scalars().all()
        if not listings:
            print("No active listings need label backfill.")
            return {"examined": 0, "updated": 0, "fields_filled": 0}

        print(f"Examining {len(listings)} listing(s)…")

        examined = 0
        updated_listings = 0
        fields_filled = 0
        t0 = time.monotonic()

        for i in range(0, len(listings), batch_size):
            batch = listings[i:i + batch_size]
            batch_updated = 0
            for listing in batch:
                examined += 1
                description = clean_html(listing.raw_description or "")
                if not description:
                    continue

                changed = False
                if _is_blank(listing.origin_label_raw):
                    v = extract_origin_country(description)
                    if v:
                        if not dry_run:
                            listing.origin_label_raw = v
                        fields_filled += 1
                        changed = True
                if _is_blank(listing.process_label_raw):
                    v = extract_process(description)
                    if v:
                        if not dry_run:
                            listing.process_label_raw = v
                        fields_filled += 1
                        changed = True
                if _is_blank(listing.varietal_label_raw):
                    vs = extract_varietal(description)
                    if vs:
                        if not dry_run:
                            listing.varietal_label_raw = ", ".join(vs[:3])
                        fields_filled += 1
                        changed = True
                if changed:
                    updated_listings += 1
                    batch_updated += 1

            if not dry_run and batch_updated:
                await session.commit()
            print(
                f"  batch {i // batch_size + 1}: {len(batch)} listings "
                f"({batch_updated} updated, {time.monotonic() - t0:.1f}s)"
            )

        if dry_run:
            print("\n--dry-run: no writes performed.")
        return {
            "examined": examined,
            "updated": updated_listings,
            "fields_filled": fields_filled,
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = asyncio.run(backfill(args.limit, args.dry_run, args.batch_size))
    print(f"\nDone. Examined {summary['examined']}, updated {summary['updated']} listing(s), "
          f"filled {summary['fields_filled']} field(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
