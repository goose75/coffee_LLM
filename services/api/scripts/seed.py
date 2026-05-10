"""
Seed script — inserts reference data into a fresh database.

FIXED: Rewrites all raw SQL text() calls as SQLAlchemy ORM operations.
Original used :name style named parameters which asyncpg rejects.

Usage:
    docker exec coffee_api python scripts/seed.py

Inserts (idempotent — safe to re-run):
  - 5 UK coffee roasters (stores)
  - 1 source_page (Shopify feed) per Shopify store
  - Normalisation mappings for roast_level, grind, process
  - 3 canonical beans with realistic attributes
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.store import Store
from app.models.source_page import SourcePage
from app.models.resolution import NormalisationMapping
from app.models.canonical_bean import CanonicalBean
import app.models  # noqa: F401 — register all models


# ── Sample data ───────────────────────────────────────────────────────────────

STORES = [
    {
        "name": "Square Mile Coffee Roasters",
        "domain": "shop.squaremilecoffee.com",
        "homepage_url": "https://shop.squaremilecoffee.com",
        "source_type": "shopify",
        "parser_strategy": "shopify",
        "country_code": "GB",
        "uk_region": "London",
        "roaster_flag": True,
        "cafe_flag": False,
        "ecommerce_flag": True,
        "active_flag": True,
        "crawl_frequency_hours": 12,
    },
    {
        "name": "Hasbean",
        "domain": "www.hasbean.co.uk",
        "homepage_url": "https://www.hasbean.co.uk",
        "source_type": "shopify",
        "parser_strategy": "shopify",
        "country_code": "GB",
        "uk_region": "Midlands",
        "roaster_flag": True,
        "cafe_flag": False,
        "ecommerce_flag": True,
        "active_flag": True,
        "crawl_frequency_hours": 12,
    },
    {
        "name": "Monmouth Coffee Company",
        "domain": "www.monmouthcoffee.co.uk",
        "homepage_url": "https://www.monmouthcoffee.co.uk",
        "source_type": "html",
        "parser_strategy": "html",
        "country_code": "GB",
        "uk_region": "London",
        "roaster_flag": True,
        "cafe_flag": True,
        "ecommerce_flag": True,
        "active_flag": True,
        "crawl_frequency_hours": 24,
    },
    {
        "name": "Workshop Coffee",
        "domain": "www.workshopcoffee.com",
        "homepage_url": "https://www.workshopcoffee.com",
        "source_type": "shopify",
        "parser_strategy": "shopify",
        "country_code": "GB",
        "uk_region": "London",
        "roaster_flag": True,
        "cafe_flag": True,
        "ecommerce_flag": True,
        "active_flag": True,
        "crawl_frequency_hours": 12,
    },
    {
        "name": "Rave Coffee",
        "domain": "www.ravecoffee.co.uk",
        "homepage_url": "https://www.ravecoffee.co.uk",
        "source_type": "shopify",
        "parser_strategy": "shopify",
        "country_code": "GB",
        "uk_region": "South West",
        "roaster_flag": True,
        "cafe_flag": False,
        "ecommerce_flag": True,
        "active_flag": True,
        "crawl_frequency_hours": 24,
    },
]

NORMALISATION_MAPPINGS = [
    # roast_level
    ("roast_level", "light roast", "light"),
    ("roast_level", "Light", "light"),
    ("roast_level", "lightly roasted", "light"),
    ("roast_level", "blonde", "light"),
    ("roast_level", "filter roast", "light"),
    ("roast_level", "city roast", "medium"),
    ("roast_level", "City+", "medium_light"),
    ("roast_level", "medium roast", "medium"),
    ("roast_level", "Medium", "medium"),
    ("roast_level", "medium-light", "medium_light"),
    ("roast_level", "medium-dark", "medium_dark"),
    ("roast_level", "full city", "medium_dark"),
    ("roast_level", "Full City+", "medium_dark"),
    ("roast_level", "espresso roast", "medium_dark"),
    ("roast_level", "dark roast", "dark"),
    ("roast_level", "Dark", "dark"),
    ("roast_level", "Italian roast", "dark"),
    ("roast_level", "French roast", "dark"),
    # grind
    ("grind", "Whole Bean", "whole_bean"),
    ("grind", "whole bean", "whole_bean"),
    ("grind", "Unground", "whole_bean"),
    ("grind", "Beans", "whole_bean"),
    ("grind", "Espresso", "espresso"),
    ("grind", "espresso grind", "espresso"),
    ("grind", "Fine", "espresso"),
    ("grind", "Filter", "filter"),
    ("grind", "filter grind", "filter"),
    ("grind", "Pour Over", "pour_over"),
    ("grind", "V60", "pour_over"),
    ("grind", "Cafetiere", "cafetiere"),
    ("grind", "cafetière", "cafetiere"),
    ("grind", "French Press", "cafetiere"),
    ("grind", "Plunger", "cafetiere"),
    ("grind", "Moka Pot", "moka"),
    ("grind", "Stovetop", "moka"),
    ("grind", "AeroPress", "aeropress"),
    ("grind", "Aeropress", "aeropress"),
    ("grind", "Omni", "omni"),
    ("grind", "omni grind", "omni"),
    ("grind", "All Brew Methods", "omni"),
    # process
    ("process", "Washed", "washed"),
    ("process", "washed process", "washed"),
    ("process", "Fully Washed", "washed"),
    ("process", "Wet Process", "washed"),
    ("process", "Natural", "natural"),
    ("process", "natural process", "natural"),
    ("process", "Dry Process", "natural"),
    ("process", "Sun Dried", "natural"),
    ("process", "Honey", "honey"),
    ("process", "honey process", "honey"),
    ("process", "Yellow Honey", "honey"),
    ("process", "Red Honey", "honey"),
    ("process", "Black Honey", "honey"),
    ("process", "Anaerobic", "anaerobic"),
    ("process", "anaerobic fermentation", "anaerobic"),
    ("process", "anaerobic natural", "anaerobic"),
    ("process", "anaerobic washed", "anaerobic"),
    ("process", "Wet Hulled", "wet_hulled"),
    ("process", "Giling Basah", "wet_hulled"),
    ("process", "Carbonic Maceration", "carbonic_maceration"),
    ("process", "CO2 Maceration", "carbonic_maceration"),
]

CANONICAL_BEANS = [
    {
        "canonical_name": "Ethiopia Yirgacheffe Konga Washed",
        "origin_country": "Ethiopia",
        "origin_region": "Yirgacheffe",
        "farm_or_estate": "Konga Cooperative",
        "washing_station": "Konga Washing Station",
        "producer": "Konga Cooperative",
        "varietal": ["Heirloom", "74110"],
        "process": "washed",
        "altitude_masl_min": 1800,
        "altitude_masl_max": 2200,
        "harvest_year": 2024,
        "roast_level": "light",
        "flavour_notes": ["jasmine", "bergamot", "lemon", "peach"],
        "decaf_flag": False,
        "espresso_suitable_flag": True,
        "filter_suitable_flag": True,
        "data_completeness_score": 0.9,
    },
    {
        "canonical_name": "Colombia El Paraiso Anaerobic Natural",
        "origin_country": "Colombia",
        "origin_region": "Cauca",
        "farm_or_estate": "El Paraiso",
        "washing_station": None,
        "producer": "Diego Samuel Bermudez",
        "varietal": ["Castillo"],
        "process": "anaerobic",
        "process_detail": "Double anaerobic fermentation, natural dried",
        "altitude_masl_min": 1750,
        "altitude_masl_max": 1900,
        "harvest_year": 2024,
        "roast_level": "light",
        "flavour_notes": ["tropical fruit", "strawberry", "passionfruit", "candy"],
        "decaf_flag": False,
        "espresso_suitable_flag": True,
        "filter_suitable_flag": True,
        "data_completeness_score": 0.85,
    },
    {
        "canonical_name": "Kenya Kirinyaga AB Washed",
        "origin_country": "Kenya",
        "origin_region": "Kirinyaga",
        "farm_or_estate": None,
        "washing_station": "Kamwangi Factory",
        "producer": "Thimu Farmers Cooperative Society",
        "varietal": ["SL28", "SL34", "Ruiru 11"],
        "process": "washed",
        "altitude_masl_min": 1600,
        "altitude_masl_max": 1850,
        "harvest_year": 2023,
        "roast_level": "light",
        "flavour_notes": ["blackcurrant", "tomato", "grapefruit", "brown sugar"],
        "decaf_flag": False,
        "espresso_suitable_flag": True,
        "filter_suitable_flag": True,
        "data_completeness_score": 0.8,
    },
]


# ── Seed runner ───────────────────────────────────────────────────────────────

async def seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    # ── Stores ────────────────────────────────────────────────────────────────
    print("Seeding stores...")
    store_objects: dict[str, Store] = {}
    for data in STORES:
        existing = (await session.execute(
            select(Store).where(Store.domain == data["domain"])
        )).scalar_one_or_none()

        if existing is None:
            store = Store(**data)
            session.add(store)
            await session.flush()  # get the id
            store_objects[data["domain"]] = store
            print(f"  ✓ {data['name']} ({data['domain']}) — created")
        else:
            existing.name = data["name"]
            store_objects[data["domain"]] = existing
            print(f"  = {data['name']} ({data['domain']}) — already exists")

    await session.flush()

    # ── Source pages (one Shopify feed per Shopify store) ─────────────────────
    print("\nSeeding source pages...")
    for data in STORES:
        if data["parser_strategy"] != "shopify":
            continue
        store = store_objects.get(data["domain"])
        if store is None:
            continue
        feed_url = f"https://{data['domain']}/products.json"
        existing_page = (await session.execute(
            select(SourcePage).where(SourcePage.url == feed_url)
        )).scalar_one_or_none()
        if existing_page is None:
            page = SourcePage(
                store_id=store.id,
                url=feed_url,
                page_type="feed",
                parser_strategy="shopify",
                discovered_at=now,
                changed_flag=True,
            )
            session.add(page)
            print(f"  ✓ {feed_url}")

    await session.flush()

    # ── Normalisation mappings ─────────────────────────────────────────────────
    print("\nSeeding normalisation mappings...")
    added = 0
    for mapping_type, raw_value, normalised_value in NORMALISATION_MAPPINGS:
        existing = (await session.execute(
            select(NormalisationMapping).where(
                NormalisationMapping.mapping_type == mapping_type,
                NormalisationMapping.raw_value == raw_value,
            )
        )).scalar_one_or_none()
        if existing is None:
            session.add(NormalisationMapping(
                mapping_type=mapping_type,
                raw_value=raw_value,
                normalised_value=normalised_value,
                confidence_score=1.0,
                source="manual",
            ))
            added += 1
    print(f"  ✓ {added} mappings added ({len(NORMALISATION_MAPPINGS) - added} already existed)")

    await session.flush()

    # ── Canonical beans ───────────────────────────────────────────────────────
    print("\nSeeding canonical beans...")
    for bean_data in CANONICAL_BEANS:
        existing = (await session.execute(
            select(CanonicalBean).where(
                CanonicalBean.canonical_name == bean_data["canonical_name"]
            )
        )).scalar_one_or_none()
        if existing is None:
            # Build kwargs — process_detail is optional
            kwargs = {k: v for k, v in bean_data.items()}
            bean = CanonicalBean(**kwargs)
            session.add(bean)
            print(f"  ✓ {bean_data['canonical_name']} — created")
        else:
            print(f"  = {bean_data['canonical_name']} — already exists")

    await session.commit()
    print("\n✅ Seed complete.")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
