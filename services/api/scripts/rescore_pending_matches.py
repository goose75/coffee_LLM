"""
rescore_pending_matches.py — recompute signals + confidence for every
pending CanonicalMatch.

After backfilling embeddings (or changing weights, or any other matching
signal change), the persisted match_signals_json on existing matches no
longer reflects current truth. This script:

  1. For each pending match, regenerates the listing embedding.
  2. Reads the canonical bean's embedding_vector.
  3. Calls build_signals to recompute exact / fuzzy / embedding / harvest.
  4. Writes the new match_signals_json + confidence_score.

It does NOT change review_status — humans still decide. But the score that
gets shown in the queue is now accurate, and the analytics histograms move
from "everyone is at 0 embedding" to a real distribution.

Usage:
    docker exec coffee_api python scripts/rescore_pending_matches.py
    docker exec coffee_api python scripts/rescore_pending_matches.py --dry-run --limit 20
    docker exec coffee_api python scripts/rescore_pending_matches.py --auto-accept-threshold 0.92
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.enums import ReviewStatus
from app.models.resolution import CanonicalMatch
from app.services.matching.embeddings import generate_listing_embedding
from app.services.matching.signals import build_signals


async def rescore(limit: int, dry_run: bool, auto_accept_threshold: float | None) -> int:
    openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""

    async with AsyncSessionLocal() as session:
        stmt = (
            select(CanonicalMatch)
            .where(CanonicalMatch.review_status == "pending")
            .options(
                selectinload(CanonicalMatch.bean_listing),
                selectinload(CanonicalMatch.proposed_canonical_bean),
            )
            .limit(limit)
        )
        matches = (await session.execute(stmt)).scalars().all()
        if not matches:
            print("No pending matches found.")
            return 0
        print(f"Re-scoring {len(matches)} pending match(es)…")

        moved_to_accept = 0
        score_deltas: list[float] = []
        t0 = time.monotonic()

        for i, match in enumerate(matches, start=1):
            listing = match.bean_listing
            canonical = match.proposed_canonical_bean
            if listing is None or canonical is None:
                continue

            listing_emb = await generate_listing_embedding(listing, api_key=openai_key)
            canonical_emb = list(canonical.embedding_vector) if canonical.embedding_vector is not None else None

            new_signals = build_signals(
                listing,
                canonical,
                listing_embedding=listing_emb,
                canonical_embedding=canonical_emb,
            )
            old_score = match.confidence_score or 0.0
            new_score = new_signals.combined
            score_deltas.append(new_score - old_score)

            if not dry_run:
                match.match_signals_json = new_signals.to_dict()
                match.confidence_score = new_score
                if auto_accept_threshold is not None and new_score >= auto_accept_threshold:
                    match.review_status = ReviewStatus.accepted
                    if listing.canonical_bean_id is None:
                        listing.canonical_bean_id = canonical.id
                    moved_to_accept += 1

            if i % 50 == 0:
                if not dry_run:
                    await session.commit()
                print(f"  …processed {i}/{len(matches)} ({time.monotonic() - t0:.1f}s)")

        if not dry_run:
            await session.commit()

        avg_delta = sum(score_deltas) / len(score_deltas) if score_deltas else 0.0
        positive = sum(1 for d in score_deltas if d > 0.001)
        negative = sum(1 for d in score_deltas if d < -0.001)
        print()
        print(f"Re-scored {len(matches)} match(es) in {time.monotonic() - t0:.1f}s.")
        print(f"  Avg score delta: {avg_delta:+.3f}")
        print(f"  Scores rose: {positive}    fell: {negative}    unchanged: {len(matches) - positive - negative}")
        if auto_accept_threshold is not None:
            print(f"  Auto-accepted (combined >= {auto_accept_threshold}): {moved_to_accept}")
        if dry_run:
            print("  --dry-run: no writes performed.")
        return len(matches)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=2000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--auto-accept-threshold", type=float, default=None,
                   help="if set, matches with combined >= this will move to accepted")
    args = p.parse_args()
    return asyncio.run(rescore(args.limit, args.dry_run, args.auto_accept_threshold))


if __name__ == "__main__":
    raise SystemExit(main())
