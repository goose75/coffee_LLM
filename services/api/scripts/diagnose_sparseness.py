"""
diagnose_sparseness.py — find out exactly *why* sparse_canonical is still
the top blocker.

Reports:
  1. Listing-side: how many active listings have origin/process/varietal
     populated, and how many have non-empty raw_description
  2. Canonical-side: how many canonical beans have each key field
  3. Linked-listings: distribution of "listings per canonical"
  4. A sample of 5 pending matches whose field_matches is mostly None,
     showing the actual listing + canonical values side-by-side

That tells us whether the backfill never ran, ran but extracted nothing,
or ran but didn't propagate to canonicals.

Usage:
    docker exec coffee_api python scripts/diagnose_sparseness.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.resolution import CanonicalMatch


async def main() -> int:
    async with AsyncSessionLocal() as session:
        # ── Listings ────────────────────────────────────────────────────────
        listings_total = (await session.execute(
            select(func.count()).select_from(BeanListing).where(BeanListing.active_flag == True)  # noqa: E712
        )).scalar_one()
        listings_with_desc = (await session.execute(
            select(func.count()).select_from(BeanListing).where(
                BeanListing.active_flag == True,  # noqa: E712
                BeanListing.raw_description.isnot(None),
                func.length(BeanListing.raw_description) > 50,
            )
        )).scalar_one()

        async def _count_filled(col):
            return (await session.execute(
                select(func.count()).select_from(BeanListing).where(
                    BeanListing.active_flag == True,  # noqa: E712
                    col.isnot(None),
                    func.length(col) > 0,
                )
            )).scalar_one()

        listings_with_origin = await _count_filled(BeanListing.origin_label_raw)
        listings_with_process = await _count_filled(BeanListing.process_label_raw)
        listings_with_varietal = await _count_filled(BeanListing.varietal_label_raw)

        print("=" * 70)
        print("LISTING SIDE")
        print("=" * 70)
        print(f"  Active listings:         {listings_total}")
        print(f"  …with raw_description:   {listings_with_desc}  ({listings_with_desc * 100 // max(listings_total, 1)}%)")
        print(f"  …with origin_label_raw:  {listings_with_origin}  ({listings_with_origin * 100 // max(listings_total, 1)}%)")
        print(f"  …with process_label_raw: {listings_with_process}  ({listings_with_process * 100 // max(listings_total, 1)}%)")
        print(f"  …with varietal_label_raw:{listings_with_varietal}  ({listings_with_varietal * 100 // max(listings_total, 1)}%)")

        # ── Canonical beans ─────────────────────────────────────────────────
        canon_total = (await session.execute(
            select(func.count()).select_from(CanonicalBean)
        )).scalar_one()
        canon_with_country = (await session.execute(
            select(func.count()).select_from(CanonicalBean).where(
                CanonicalBean.origin_country.isnot(None),
                func.length(CanonicalBean.origin_country) > 0,
            )
        )).scalar_one()
        canon_with_process = (await session.execute(
            select(func.count()).select_from(CanonicalBean).where(
                CanonicalBean.process.isnot(None)
            )
        )).scalar_one()
        canon_with_varietal = (await session.execute(
            select(func.count()).select_from(CanonicalBean).where(
                func.array_length(CanonicalBean.varietal, 1) > 0
            )
        )).scalar_one()
        canon_with_farm = (await session.execute(
            select(func.count()).select_from(CanonicalBean).where(
                CanonicalBean.farm_or_estate.isnot(None),
                func.length(CanonicalBean.farm_or_estate) > 0,
            )
        )).scalar_one()

        print()
        print("=" * 70)
        print("CANONICAL SIDE")
        print("=" * 70)
        print(f"  Canonical beans:         {canon_total}")
        print(f"  …with origin_country:    {canon_with_country}  ({canon_with_country * 100 // max(canon_total, 1)}%)")
        print(f"  …with process:           {canon_with_process}  ({canon_with_process * 100 // max(canon_total, 1)}%)")
        print(f"  …with varietal:          {canon_with_varietal}  ({canon_with_varietal * 100 // max(canon_total, 1)}%)")
        print(f"  …with farm_or_estate:    {canon_with_farm}  ({canon_with_farm * 100 // max(canon_total, 1)}%)")

        # ── Listings-per-canonical distribution ─────────────────────────────
        rows = (await session.execute(
            select(BeanListing.canonical_bean_id, func.count())
            .where(BeanListing.canonical_bean_id.isnot(None))
            .group_by(BeanListing.canonical_bean_id)
        )).all()
        per_canon = Counter([r[1] for r in rows])
        total_linked = sum(per_canon.values())
        print()
        print("=" * 70)
        print("LISTINGS PER CANONICAL")
        print("=" * 70)
        print(f"  Canonicals with N linked listings:")
        for n in sorted(per_canon.keys()):
            print(f"    {n:>3} listing(s) → {per_canon[n]} canonical(s)")
        print(f"  Total linked listings: {total_linked}, total canonicals with ≥1 listing: {sum(per_canon.values())}")

        # ── Sample 5 sparse pending matches ─────────────────────────────────
        pending_stmt = (
            select(CanonicalMatch)
            .where(CanonicalMatch.review_status == "pending")
            .options(
                selectinload(CanonicalMatch.bean_listing),
                selectinload(CanonicalMatch.proposed_canonical_bean),
            )
            .limit(50)
        )
        pendings = (await session.execute(pending_stmt)).scalars().all()
        sparse_examples = []
        for m in pendings:
            sigs = m.match_signals_json or {}
            fm = sigs.get("field_matches", {}) or {}
            skipped = sum(1 for v in fm.values() if v is None)
            if skipped >= 3:
                sparse_examples.append(m)
                if len(sparse_examples) >= 5:
                    break

        print()
        print("=" * 70)
        print("FIVE SAMPLE SPARSE PENDING MATCHES")
        print("=" * 70)
        if not sparse_examples:
            print("  (none found in first 50 pending — query bound)")
        for m in sparse_examples:
            l = m.bean_listing
            c = m.proposed_canonical_bean
            print(f"\n  Match {m.id}  confidence={m.confidence_score:.2f}")
            print(f"    Listing: '{(l.raw_title or '')[:60]}'")
            print(f"      origin_label_raw  = {l.origin_label_raw!r}")
            print(f"      process_label_raw = {l.process_label_raw!r}")
            print(f"      varietal_label_raw= {l.varietal_label_raw!r}")
            print(f"      raw_description  : {len(l.raw_description or '')} chars")
            print(f"    Canonical: '{c.canonical_name[:60]}'")
            print(f"      origin_country = {c.origin_country!r}")
            print(f"      process        = {c.process!r}")
            print(f"      varietal       = {c.varietal!r}")
            print(f"      farm_or_estate = {c.farm_or_estate!r}")
            print(f"      completeness   = {c.data_completeness_score}")
            print(f"    field_matches  : {(m.match_signals_json or {}).get('field_matches')}")

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
