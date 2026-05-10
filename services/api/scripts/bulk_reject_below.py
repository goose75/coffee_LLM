"""
bulk_reject_below.py — reject all pending matches with confidence below
a threshold. Same operation as the admin UI's "Bulk: reject all ≤X%" preset.

Usage:
    docker exec coffee_api python scripts/bulk_reject_below.py
    docker exec coffee_api python scripts/bulk_reject_below.py --threshold 0.5
    docker exec coffee_api python scripts/bulk_reject_below.py --threshold 0.6 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.resolution import CanonicalMatch
from app.services.matching import CanonicalMatchingService


async def run(threshold: float, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        if dry_run:
            stmt = (
                select(CanonicalMatch.id, CanonicalMatch.confidence_score)
                .where(CanonicalMatch.review_status == "pending")
                .where(CanonicalMatch.confidence_score <= threshold)
            )
            rows = (await session.execute(stmt)).all()
            print(f"Would reject {len(rows)} pending match(es) with confidence ≤ {threshold:.2f}.")
            for row in rows[:5]:
                print(f"  conf={row[1]:.2f}  match_id={row[0]}")
            if len(rows) > 5:
                print(f"  …and {len(rows) - 5} more")
            return 0

        service = CanonicalMatchingService(session)
        affected, skipped = await service.bulk_reject_by_filter(
            max_confidence=threshold,
            notes=f"bulk_reject_below preset (≤{threshold:.2f})",
            limit=10_000,
        )
        print(f"Rejected {affected} match(es). Skipped {len(skipped)} (already decided).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    return asyncio.run(run(args.threshold, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
