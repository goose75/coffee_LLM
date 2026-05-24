#!/usr/bin/env python3
"""
Fix 17grams.co.uk: Add source pages and trigger ingestion.

The issue: 17grams.co.uk has no source_pages configured, so ingestion returns 0 records.
The fix: Manually add the known product pages and trigger a fresh ingestion run.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

app_path = Path(__file__).parent / "services" / "api"
sys.path.insert(0, str(app_path))

# Suppress logging
import logging
logging.disable(logging.CRITICAL)

from app.core.database import AsyncSessionLocal
from app.models.store import Store
from app.models.source_page import SourcePage
from app.models.enums import PageType, ParserStrategy
from sqlalchemy import select

async def fix_17grams():
    """Add source pages for 17grams and trigger ingestion"""

    async with AsyncSessionLocal() as db:
        # Find the store
        store = (await db.execute(select(Store).where(Store.domain == '17grams.co.uk'))).scalar_one_or_none()

        if not store:
            print("❌ Store not found")
            return

        print(f"✓ Found store: {store.name}")

        # Check existing source pages
        existing_pages = (await db.execute(select(SourcePage).where(SourcePage.store_id == store.id))).scalars().all()
        print(f"  Existing source pages: {len(existing_pages)}")

        if existing_pages:
            print("  Already has pages configured:")
            for p in existing_pages:
                print(f"    - {p.url}")
            return

        # 17grams.co.uk product pages - discovered from manual inspection
        product_page_urls = [
            "https://17grams.co.uk/shop/",           # Main shop page
            "https://17grams.co.uk/products/",       # Alternative products URL
        ]

        print(f"\n📝 Adding {len(product_page_urls)} source pages...")

        created_pages = []
        for url in product_page_urls:
            source_page = SourcePage(
                store_id=store.id,
                url=url,
                page_type=PageType.product_listing,
                parser_strategy=ParserStrategy.html,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(source_page)
            created_pages.append(url)
            print(f"  ✓ {url}")

        await db.commit()
        print(f"\n✅ Added {len(created_pages)} source pages")
        print("\n📌 Next step: Trigger a fresh ingestion run")
        print("   Command: curl -X POST http://localhost:8000/api/v1/admin/ingest/store/17grams.co.uk")

        # Alternatively, show how to trigger via API
        print("\n   Or use the admin endpoint to trigger ingestion for this store")

if __name__ == "__main__":
    asyncio.run(fix_17grams())
