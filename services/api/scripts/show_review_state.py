"""
show_review_state.py — concise pending count and top blockers.

Usage:
    docker exec coffee_api python scripts/show_review_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal
from app.api.v1.admin import review_analytics


async def main_async() -> int:
    async with AsyncSessionLocal() as session:
        r = await review_analytics(db=session)
    print(f"pending:  {r.pending_count}")
    print(f"accepted: {r.accepted_count}")
    print(f"rejected: {r.rejected_count}")
    print()
    print(f"avg canonical completeness: {r.avg_canonical_completeness * 100:.0f}% across {r.canonical_bean_count} beans")
    print()
    if r.top_blockers:
        print("top blockers:")
        for b in r.top_blockers:
            print(f"  {b.count:>4}  {b.label:20}  {b.description}")
    else:
        print("(no top blockers identified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
