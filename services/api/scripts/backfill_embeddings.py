"""
backfill_embeddings.py — populate embedding_vector on canonical beans and
listings that don't have one.

For every CanonicalBean with embedding_vector IS NULL, generate an embedding
from canonical_name + structured fields and persist it. Same for every
active BeanListing without an embedding (listings persist their embedding on
the canonical they were merged into, so we mostly only need canonicals;
this script also writes a listing-side cache via canonical assignment when
a listing has no canonical_bean_id yet — the matcher will use it on next run).

When OPENAI_API_KEY is set, OpenAI is used. Otherwise the local hash-based
fallback in embeddings.py generates deterministic 1536-dim vectors. Either
way, no zero vectors are written.

Usage:
    docker exec coffee_api python scripts/backfill_embeddings.py
    docker exec coffee_api python scripts/backfill_embeddings.py --limit 500 --batch-size 50
    docker exec coffee_api python scripts/backfill_embeddings.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.services.matching.embeddings import (
    generate_bean_embedding,
    generate_listing_embedding,
)


async def backfill_canonicals(
    limit: int, batch_size: int, dry_run: bool, openai_key: str
) -> int:
    """Backfill embedding_vector for canonical beans missing one."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(CanonicalBean)
            .where(CanonicalBean.embedding_vector.is_(None))
            .order_by(CanonicalBean.created_at)
            .limit(limit)
        )
        beans = (await session.execute(stmt)).scalars().all()
        if not beans:
            print("No canonical beans need embedding backfill.")
            return 0
        print(f"Backfilling {len(beans)} canonical bean embedding(s)…")
        if dry_run:
            for b in beans[:10]:
                print(f"  would embed: {b.canonical_name}")
            if len(beans) > 10:
                print(f"  …and {len(beans) - 10} more")
            return 0

        written = 0
        for i in range(0, len(beans), batch_size):
            batch = beans[i:i + batch_size]
            t0 = time.monotonic()
            for bean in batch:
                vec = await generate_bean_embedding(bean, api_key=openai_key)
                bean.embedding_vector = vec
                written += 1
            await session.commit()
            print(
                f"  canonical batch {i // batch_size + 1}: {len(batch)} beans "
                f"({time.monotonic() - t0:.1f}s, total written {written})"
            )
        return written


async def backfill_listings(
    limit: int, batch_size: int, dry_run: bool, openai_key: str
) -> int:
    """
    Backfill embedding-derived ANN signals for unmatched listings.

    BeanListing has no embedding_vector column today — matching computes the
    embedding on-the-fly via _get_listing_embedding and uses it for ANN.
    What we DO want is to ensure each listing has a canonical_bean it's
    associated with that has an embedding. So this pass walks listings whose
    matched canonical has no embedding, and generates one.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(BeanListing, CanonicalBean)
            .join(CanonicalBean, BeanListing.canonical_bean_id == CanonicalBean.id)
            .where(CanonicalBean.embedding_vector.is_(None))
            .where(BeanListing.active_flag == True)  # noqa: E712
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        if not rows:
            return 0
        print(f"Backfilling embeddings via {len(rows)} active listings → their canonicals…")
        if dry_run:
            return 0

        written = 0
        seen: set = set()
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            t0 = time.monotonic()
            for listing, canonical in batch:
                if canonical.id in seen or canonical.embedding_vector is not None:
                    continue
                vec = await generate_listing_embedding(listing, api_key=openai_key)
                canonical.embedding_vector = vec
                seen.add(canonical.id)
                written += 1
            await session.commit()
            print(
                f"  listing-side batch {i // batch_size + 1}: {len(batch)} rows "
                f"({time.monotonic() - t0:.1f}s, total canonicals enriched {written})"
            )
        return written


async def main_async() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=2000)
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--canonicals-only", action="store_true")
    p.add_argument("--listings-only", action="store_true")
    args = p.parse_args()

    openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not openai_key:
        print("OPENAI_API_KEY not set — using deterministic local hash embedding.")
    else:
        print(f"Using OpenAI embeddings (key length {len(openai_key)}).")

    total = 0
    if not args.listings_only:
        total += await backfill_canonicals(args.limit, args.batch_size, args.dry_run, openai_key)
    if not args.canonicals_only:
        total += await backfill_listings(args.limit, args.batch_size, args.dry_run, openai_key)

    print(f"\nDone. {total} embedding(s) written.")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
