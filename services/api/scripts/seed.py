"""
Seed script — inserts reference data into a fresh database.

Usage:
    cd services/api
    python scripts/seed.py

Inserts:
  - 5 UK coffee roasters (stores)
  - 1 source_page (Shopify feed) per roaster
  - Normalisation mappings for roast_level, grind_type, process
  - 3 canonical beans with realistic attributes

Run after `alembic upgrade head`. Safe to re-run — uses upsert logic.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.core.config import settings


# ─── Sample data ──────────────────────────────────────────────────────────────

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

# Normalisation mappings — covers the most common raw label variations
NORMALISATION_MAPPINGS = [
    # ── roast_level ────────────────────────────────────────────────────────
    ("roast_level", "light roast", "light"),
    ("roast_level", "Light", "light"),
    ("roast_level", "lightly roasted", "light"),
    ("roast_level", "blonde", "light"),
    ("roast_level", "city roast", "medium"),
    ("roast_level", "City+", "medium_light"),
    ("roast_level", "full city", "medium_dark"),
    ("roast_level", "Full City+", "medium_dark"),
    ("roast_level", "medium roast", "medium"),
    ("roast_level", "Medium", "medium"),
    ("roast_level", "medium-light", "medium_light"),
    ("roast_level", "medium-dark", "medium_dark"),
    ("roast_level", "dark roast", "dark"),
    ("roast_level", "Dark", "dark"),
    ("roast_level", "espresso roast", "medium_dark"),
    ("roast_level", "Italian roast", "dark"),
    ("roast_level", "French roast", "dark"),
    ("roast_level", "filter roast", "light"),
    # ── grind_type ─────────────────────────────────────────────────────────
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
    ("grind", "pour over", "pour_over"),
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
    # ── process ────────────────────────────────────────────────────────────
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


# ─── Seed runner ──────────────────────────────────────────────────────────────

async def seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    # ── Stores ─────────────────────────────────────────────────────────────
    print("Seeding stores...")
    store_ids: dict[str, str] = {}
    for store_data in STORES:
        result = await session.execute(
            text("""
                INSERT INTO stores (
                    name, domain, homepage_url, source_type, parser_strategy,
                    country_code, uk_region, roaster_flag, cafe_flag,
                    ecommerce_flag, active_flag, crawl_frequency_hours
                ) VALUES (
                    :name, :domain, :homepage_url, :source_type::source_type,
                    :parser_strategy::parser_strategy,
                    :country_code, :uk_region, :roaster_flag, :cafe_flag,
                    :ecommerce_flag, :active_flag, :crawl_frequency_hours
                )
                ON CONFLICT (domain) DO UPDATE
                    SET name = EXCLUDED.name,
                        updated_at = now()
                RETURNING id, domain
            """),
            store_data,
        )
        row = result.fetchone()
        store_ids[row.domain] = str(row.id)
        print(f"  ✓ {store_data['name']} ({store_data['domain']})")

    # ── Source pages (one Shopify feed per Shopify store) ──────────────────
    print("\nSeeding source pages...")
    for store_data in STORES:
        if store_data["parser_strategy"] != "shopify":
            continue
        domain = store_data["domain"]
        store_id = store_ids[domain]
        feed_url = f"https://{domain}/products.json"
        await session.execute(
            text("""
                INSERT INTO source_pages (
                    store_id, url, page_type, parser_strategy, discovered_at
                ) VALUES (
                    :store_id::uuid, :url, 'feed'::page_type,
                    'shopify'::parser_strategy, :discovered_at
                )
                ON CONFLICT DO NOTHING
            """),
            {"store_id": store_id, "url": feed_url, "discovered_at": now},
        )
        print(f"  ✓ {feed_url}")

    # ── Normalisation mappings ─────────────────────────────────────────────
    print("\nSeeding normalisation mappings...")
    for mapping_type, raw_value, normalised_value in NORMALISATION_MAPPINGS:
        await session.execute(
            text("""
                INSERT INTO normalisation_mappings (
                    mapping_type, raw_value, normalised_value, confidence_score, source
                ) VALUES (
                    :mapping_type::mapping_type, :raw_value, :normalised_value, 1.0, 'manual'
                )
                ON CONFLICT (mapping_type, raw_value) DO UPDATE
                    SET normalised_value = EXCLUDED.normalised_value,
                        updated_at = now()
            """),
            {
                "mapping_type": mapping_type,
                "raw_value": raw_value,
                "normalised_value": normalised_value,
            },
        )
    print(f"  ✓ {len(NORMALISATION_MAPPINGS)} mappings")

    # ── Canonical beans ────────────────────────────────────────────────────
    print("\nSeeding canonical beans...")
    for bean in CANONICAL_BEANS:
        await session.execute(
            text("""
                INSERT INTO canonical_beans (
                    canonical_name, origin_country, origin_region,
                    farm_or_estate, washing_station, producer,
                    varietal, process, process_detail,
                    altitude_masl_min, altitude_masl_max,
                    harvest_year, roast_level, flavour_notes,
                    decaf_flag, espresso_suitable_flag, filter_suitable_flag,
                    data_completeness_score
                ) VALUES (
                    :canonical_name, :origin_country, :origin_region,
                    :farm_or_estate, :washing_station, :producer,
                    :varietal, :process::process,
                    :process_detail,
                    :altitude_masl_min, :altitude_masl_max,
                    :harvest_year, :roast_level::roast_level, :flavour_notes,
                    :decaf_flag, :espresso_suitable_flag, :filter_suitable_flag,
                    :data_completeness_score
                )
                ON CONFLICT DO NOTHING
            """),
            {
                **bean,
                "varietal": bean["varietal"],
                "flavour_notes": bean["flavour_notes"],
                "process_detail": bean.get("process_detail"),
            },
        )
        print(f"  ✓ {bean['canonical_name']}")

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
