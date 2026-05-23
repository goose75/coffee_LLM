#!/usr/bin/env python3
"""
Enable Batch 2: 30 HTML sites for Phase 2 testing.

This script enables the next 30 HTML sites for crawling, organized by platform:
- 12 WooCommerce sites (similar to 17grams.co.uk)
- 10 Shopify sites
- 8 Custom/Unknown platform sites

Usage:
  docker exec coffee_api python scripts/enable_batch2.py

Expected outcome:
  - All 30 sites set to active_flag = true
  - Sites ready for next crawl cycle (6-hour schedule)
  - Ingestion runs will generate parse errors for analysis
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "services" / "api"))

from app.core.database import AsyncSessionLocal
from app.models.store import Store
from sqlalchemy import update

# Batch 2 sites organized by platform
BATCH2_WOOCOMMERCE = [
    'balance.co.uk',
    'batchcoffee.co.uk',
    'bbkc.co.uk',
    'belfastcoffee.com',
    'bennachie.co.uk',
    'blindowl.co.uk',
    'bluegoose.co.uk',
    'brazier.co.uk',
    'broadway.co.uk',
    'brewup.co.uk',
    'bridge.com',
    'brightroast.co.uk',
]

BATCH2_SHOPIFY = [
    'bellabarista.co.uk',
    'beanberry.com',
    'brawbeans.com',
    'birdie.com',
    'blendingroom.com',
    'boonaboona.com',
    'boskcoffeeroasters.co.uk',
    'badhandcoffee.com',
    'brewerylane.com',
    'belfastcoffee.com',
]

BATCH2_CUSTOM = [
    'abigo.co.uk',
    'atkinsonscoffee.com',
    'allpressespresso.com',
    'altitudelondon.co.uk',
    'andronicas.com',
    'angelucci.com',
    'aroma.com',
    'anvil.com',
]

ALL_BATCH2 = BATCH2_WOOCOMMERCE + BATCH2_SHOPIFY + BATCH2_CUSTOM


async def enable_batch2():
    """Enable all Batch 2 sites."""

    print("\n" + "=" * 80)
    print("  ENABLING BATCH 2: 30 HTML SITES")
    print("=" * 80 + "\n")

    async with AsyncSessionLocal() as db:
        # Verify all sites exist
        print("Verifying sites exist in database...")
        for domain in ALL_BATCH2:
            stmt = update(Store).where(Store.domain == domain).values(active_flag=True)
            result = await db.execute(stmt)
            if result.rowcount == 0:
                print(f"  ⚠️  {domain:<35} NOT FOUND")
            elif result.rowcount == 1:
                print(f"  ✓ {domain:<35} enabled")
            else:
                print(f"  ⚠️  {domain:<35} found {result.rowcount} records")

        await db.commit()

    # Summary
    print("\n" + "=" * 80)
    print("  BATCH 2 ACTIVATION SUMMARY")
    print("=" * 80)
    print(f"  WooCommerce sites:  {len(BATCH2_WOOCOMMERCE):2} enabled")
    print(f"  Shopify sites:      {len(BATCH2_SHOPIFY):2} enabled")
    print(f"  Custom sites:       {len(BATCH2_CUSTOM):2} enabled")
    print(f"  Total Batch 2:      {len(ALL_BATCH2):2} sites\n")

    print("  Next steps:")
    print("    1. Wait for next crawl cycle (within 6 hours)")
    print("    2. Monitor with: curl http://localhost:8000/api/v1/learning/status")
    print("    3. Check errors: curl http://localhost:8000/api/v1/learning/error-recovery")
    print("    4. View ingestion runs: curl http://localhost:8000/api/v1/admin/ingestion-runs")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(enable_batch2())
