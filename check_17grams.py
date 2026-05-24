#!/usr/bin/env python3
"""
Debug script: Check 17grams.co.uk ingestion setup and source pages
"""
import asyncio
import sys
from pathlib import Path

# Add app to path
app_path = Path(__file__).parent / "services" / "api"
sys.path.insert(0, str(app_path))

from app.core.database import AsyncSessionLocal
from app.models.store import Store
from app.models.source_page import SourcePage
from app.models.ingestion_run import IngestionRun
from sqlalchemy import select, desc
from datetime import datetime, timedelta

async def check_17grams():
    """Check 17grams setup and recent ingestion runs"""

    async with AsyncSessionLocal() as db:
        # Find 17grams store
        stmt = select(Store).where(Store.domain == "17grams.co.uk")
        store = (await db.execute(stmt)).scalar_one_or_none()

        if not store:
            print("❌ 17grams.co.uk NOT FOUND in stores table")
            return

        print("=" * 80)
        print("17GRAMS.CO.UK STORE STATUS")
        print("=" * 80)
        print(f"Store ID:          {store.id}")
        print(f"Store Name:        {store.name}")
        print(f"Domain:            {store.domain}")
        print(f"Parser Strategy:   {store.parser_strategy}")
        print(f"Health Status:     {store.health_status}")
        print(f"Active:            {store.active_flag}")
        print()

        # Check source pages
        pages_stmt = select(SourcePage).where(SourcePage.store_id == store.id)
        pages = (await db.execute(pages_stmt)).scalars().all()

        print(f"SOURCE PAGES: {len(pages)} configured")
        if pages:
            for p in pages:
                print(f"  ✓ {p.url}")
                print(f"    Page type: {p.page_type}")
                print(f"    Parser strategy: {p.parser_strategy}")
        else:
            print("  ⚠️  NO SOURCE PAGES CONFIGURED!")
            print("     This is why ingestion returns 0 records.")

        print()

        # Check recent ingestion runs
        runs_stmt = (
            select(IngestionRun)
            .where(IngestionRun.store_id == store.id)
            .order_by(desc(IngestionRun.started_at))
            .limit(5)
        )
        runs = (await db.execute(runs_stmt)).scalars().all()

        print(f"RECENT INGESTION RUNS: {len(runs)}")
        if runs:
            for run in runs:
                print(f"  📅 {run.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Status: {run.status}")
                print(f"     Records seen: {run.records_seen}")
                print(f"     Records created: {run.records_created}")
                print(f"     Pages fetched: {run.pages_fetched}")
                print(f"     Pages failed: {run.pages_failed}")
                if run.errors:
                    print(f"     Errors: {len(run.errors)}")
                    for err in run.errors[:2]:
                        print(f"       - {err.get('message', 'Unknown error')}")
        else:
            print("  ℹ️  No ingestion runs yet")

        print()
        print("=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)

        if not pages:
            print("🔴 ISSUE: No source pages configured")
            print("\n   The store is enabled but has no URLs to ingest from.")
            print("   Solution: Run the discovery script to add source pages:")
            print(f"\n     docker exec coffee_api python scripts/discover_source_pages.py --store 17grams.co.uk")
            print("\n   Or manually add:")
            print(f"     https://17grams.co.uk/shop/")
            print(f"     https://17grams.co.uk/products/")

if __name__ == "__main__":
    asyncio.run(check_17grams())
