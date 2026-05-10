"""
run_bulk_enhance.py — convenience wrapper that calls
app.services.matching.enhancement.bulk_enhance from the shell without
needing python -c with embedded asyncio.

Usage:
    docker exec coffee_api python scripts/run_bulk_enhance.py
    docker exec coffee_api python scripts/run_bulk_enhance.py --max-completeness 0.5 --auto-apply 0.7
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal
from app.services.matching.enhancement import bulk_enhance


async def main_async(max_completeness: float, limit: int, auto_apply: float) -> int:
    async with AsyncSessionLocal() as session:
        result = await bulk_enhance(
            session,
            max_completeness=max_completeness,
            limit=limit,
            auto_apply_threshold=auto_apply,
        )
    print(json.dumps(result, indent=2, default=str))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-completeness", type=float, default=0.5)
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--auto-apply", type=float, default=0.7)
    args = p.parse_args()
    return asyncio.run(main_async(args.max_completeness, args.limit, args.auto_apply))


if __name__ == "__main__":
    raise SystemExit(main())
