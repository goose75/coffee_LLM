"""
diagnose_taste_review.py — find out why /taste/review returns no rows.

Reports:
  1. How many canonical beans have flavour_notes at all
  2. Total bean_flavour_tags rows by review_status × source
  3. Confidence distribution for tags whose status is `pending`
  4. Whether tag-all has ever produced LLM-source tags
  5. The exact filter the page applies + how many rows it returns

Usage:
    docker exec coffee_api python scripts/diagnose_taste_review.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.canonical_bean import CanonicalBean
from app.models.flavour import BeanFlavourTag


async def main() -> int:
    async with AsyncSessionLocal() as session:
        # 1. Canonicals with flavour_notes
        total_beans = (await session.execute(
            select(func.count()).select_from(CanonicalBean)
        )).scalar_one()
        beans_with_notes = (await session.execute(
            select(func.count()).select_from(CanonicalBean).where(
                func.array_length(CanonicalBean.flavour_notes, 1) > 0
            )
        )).scalar_one()

        # 2. Tag breakdown by status × source
        rows = (await session.execute(
            select(BeanFlavourTag.review_status, BeanFlavourTag.source, func.count())
            .group_by(BeanFlavourTag.review_status, BeanFlavourTag.source)
        )).all()

        # 3. Pending tag confidence distribution
        pendings = (await session.execute(
            select(BeanFlavourTag.confidence)
            .where(BeanFlavourTag.review_status == "pending")
        )).all()
        pending_confidences = [r[0] for r in pendings]

        # 4. The exact query the page runs
        page_results = (await session.execute(
            select(func.count()).select_from(BeanFlavourTag).where(
                BeanFlavourTag.review_status == "pending",
                BeanFlavourTag.confidence >= 0.0,
                BeanFlavourTag.confidence <= 0.75,
            )
        )).scalar_one()

        print("=" * 70)
        print("CANONICAL BEAN STATE")
        print("=" * 70)
        print(f"  Total canonical beans:      {total_beans}")
        print(f"  …with non-empty flavour_notes: {beans_with_notes} "
              f"({beans_with_notes * 100 // max(total_beans, 1)}%)")

        print()
        print("=" * 70)
        print("BEAN_FLAVOUR_TAGS BY status × source")
        print("=" * 70)
        if not rows:
            print("  (no tags exist at all)")
        else:
            for status, source, count in rows:
                status_str = status.value if hasattr(status, 'value') else str(status)
                print(f"  status={status_str:<10}  source={source:<8}  count={count}")

        print()
        print("=" * 70)
        print("PENDING TAG CONFIDENCE DISTRIBUTION")
        print("=" * 70)
        if not pending_confidences:
            print("  No pending tags exist.")
        else:
            buckets: Counter[str] = Counter()
            for c in pending_confidences:
                lo = int(c * 10) / 10
                buckets[f"{lo:.1f}-{lo + 0.1:.1f}"] += 1
            for k in sorted(buckets):
                print(f"  {k}  {buckets[k]}")

        print()
        print("=" * 70)
        print("WHAT /taste/review RETURNS WITH PAGE'S DEFAULT FILTER")
        print("=" * 70)
        print(f"  Filter: review_status = pending AND 0.0 <= confidence <= 0.75")
        print(f"  Matching rows: {page_results}")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
