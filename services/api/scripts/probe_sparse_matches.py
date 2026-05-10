"""
probe_sparse_matches.py — print a sample of pending matches whose
field_matches has 3+ skipped fields, to help the operator decide whether
the remaining sparse_canonical bucket is real coffees worth enriching
or non-coffee debris that should be purged.

Usage:
    docker exec coffee_api python scripts/probe_sparse_matches.py
    docker exec coffee_api python scripts/probe_sparse_matches.py --limit 30
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.resolution import CanonicalMatch


async def probe(limit: int) -> int:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(CanonicalMatch)
            .where(CanonicalMatch.review_status == "pending")
            .options(
                selectinload(CanonicalMatch.bean_listing),
                selectinload(CanonicalMatch.proposed_canonical_bean),
            )
            .order_by(CanonicalMatch.confidence_score.desc())
        )
        all_pending = (await session.execute(stmt)).scalars().all()

        sparse: list = []
        for m in all_pending:
            sigs = m.match_signals_json or {}
            fm = sigs.get("field_matches", {}) or {}
            skipped = sum(1 for v in fm.values() if v is None)
            if skipped >= 3:
                sparse.append(m)
            if len(sparse) >= limit:
                break

        print(f"Showing {len(sparse)} sparse pending matches (3+ skipped fields):\n")
        for m in sparse:
            l = m.bean_listing
            c = m.proposed_canonical_bean
            l_title = (l.raw_title if l else "(no listing)")[:55]
            c_name = (c.canonical_name if c else "(no canonical)")[:55]
            desc_len = len(l.raw_description or "") if l else 0
            print(f"  [{m.confidence_score:.2f}]  {l_title:<55}  →  {c_name}")
            print(f"           desc={desc_len} chars  origin/process/varietal on listing: "
                  f"{l.origin_label_raw or '—'} / {l.process_label_raw or '—'} / {l.varietal_label_raw or '—'}")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    return asyncio.run(probe(args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
