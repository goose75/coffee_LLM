#!/usr/bin/env python3
"""
Import roasters.csv into the database.

Run from the coffee_LLM root folder:
  docker exec coffee_api python scripts/import_roasters.py

Or with a custom CSV path:
  docker exec coffee_api python scripts/import_roasters.py data/roasters.csv

Place roasters.csv in: coffee_LLM/services/api/data/roasters.csv
(The /app/data/ path inside Docker maps to services/api/data/)
"""

import asyncio
import csv
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.store import Store
import app.models

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://coffee:coffee@postgres:5432/coffee_platform",
)

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "/app/data/roasters.csv"


async def import_roasters() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found at {CSV_PATH}")
        print(f"Place roasters.csv in services/api/data/ and re-run")
        await engine.dispose()
        return

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Importing {len(rows)} roasters from {CSV_PATH}")
    added = skipped = 0

    async with Session() as session:
        for row in rows:
            domain = row["domain"].strip()
            existing = (await session.execute(
                select(Store).where(Store.domain == domain)
            )).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            store = Store(
                name=row["name"].strip(),
                domain=domain,
                homepage_url=f"https://{domain}",
                source_type=row.get("source_type", "shopify").strip(),
                parser_strategy=row.get("parser_strategy", "shopify").strip(),
                country_code="GB",
                uk_region=row.get("uk_region", "").strip() or None,
                roaster_flag=True,
                cafe_flag=False,
                ecommerce_flag=True,
                active_flag=True,
                crawl_frequency_hours=int(row.get("crawl_frequency_hours", 24)),
            )
            session.add(store)
            added += 1
            print(f"  + {row['name']} ({domain})")

        await session.commit()

    print(f"\nDone: {added} added, {skipped} already existed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_roasters())
