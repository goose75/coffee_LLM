"""
Extended seed script — ORM version (no raw SQL).
Adds listings, variants, price history, and flavour taxonomy.
Run after: python scripts/seed.py
"""

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from math import sin

sys.path.insert(0, "/app")

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.pricing import ListingVariant, PriceHistory
from app.models.store import Store
import app.models  # noqa: register all

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://coffee:coffee@postgres:5432/coffee_platform",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def synth_price(base: float, day: int) -> float:
    noise = sin(day * 0.3) * 0.08 * base + sin(day * 1.1) * 0.04 * base
    return round(max(base * 0.85, base + noise), 2)


def p100(price: float, weight_g: int) -> float:
    return round(price / weight_g * 100, 4)


# ── Listing specs ─────────────────────────────────────────────────────────────

LISTING_SPECS = [
    {
        "bean_key": "Ethiopia Yirgacheffe Konga Washed",
        "store": "shop.squaremilecoffee.com",
        "raw_title": "Yirgacheffe Konga",
        "product_url": "https://shop.squaremilecoffee.com/products/yirgacheffe-konga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250,  "grind": "whole_bean", "base_price": 12.50, "avail": "in_stock",     "sku": "SMC-ETH-250-WB"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean", "base_price": 42.00, "avail": "in_stock",     "sku": "SMC-ETH-1K-WB"},
        ],
    },
    {
        "bean_key": "Ethiopia Yirgacheffe Konga Washed",
        "store": "www.workshopcoffee.com",
        "raw_title": "Ethiopia Konga Washed 2024",
        "product_url": "https://www.workshopcoffee.com/products/ethiopia-konga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250,  "grind": "whole_bean", "base_price": 13.50, "avail": "in_stock",     "sku": "WC-ETH-250"},
            {"title": "250g / Filter",     "weight_g": 250,  "grind": "filter",     "base_price": 13.50, "avail": "in_stock",     "sku": "WC-ETH-250-F"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean", "base_price": 44.00, "avail": "out_of_stock", "sku": "WC-ETH-1K"},
        ],
    },
    {
        "bean_key": "Ethiopia Yirgacheffe Konga Washed",
        "store": "www.ravecoffee.co.uk",
        "raw_title": "Yirgacheffe Konga Filter",
        "product_url": "https://www.ravecoffee.co.uk/products/yirgacheffe",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 11.50, "avail": "in_stock", "sku": "RAVE-ETH-250"},
            {"title": "500g / Whole Bean", "weight_g": 500, "grind": "whole_bean", "base_price": 21.50, "avail": "in_stock", "sku": "RAVE-ETH-500"},
        ],
    },
    {
        "bean_key": "Colombia El Paraiso Anaerobic Natural",
        "store": "shop.squaremilecoffee.com",
        "raw_title": "El Paraiso Anaerobic Natural",
        "product_url": "https://shop.squaremilecoffee.com/products/el-paraiso",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250,  "grind": "whole_bean", "base_price": 18.50, "avail": "in_stock", "sku": "SMC-COL-250"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean", "base_price": 62.00, "avail": "in_stock", "sku": "SMC-COL-1K"},
        ],
    },
    {
        "bean_key": "Colombia El Paraiso Anaerobic Natural",
        "store": "www.workshopcoffee.com",
        "raw_title": "Colombia El Paraiso",
        "product_url": "https://www.workshopcoffee.com/products/el-paraiso",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 19.00, "avail": "in_stock", "sku": "WC-COL-250"},
        ],
    },
    {
        "bean_key": "Kenya Kirinyaga AB Washed",
        "store": "shop.squaremilecoffee.com",
        "raw_title": "Kenya Kirinyaga AB",
        "product_url": "https://shop.squaremilecoffee.com/products/kenya-kirinyaga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250,  "grind": "whole_bean", "base_price": 14.00, "avail": "in_stock", "sku": "SMC-KEN-250"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean", "base_price": 48.00, "avail": "in_stock", "sku": "SMC-KEN-1K"},
        ],
    },
    {
        "bean_key": "Kenya Kirinyaga AB Washed",
        "store": "www.ravecoffee.co.uk",
        "raw_title": "Kirinyaga AB Washed",
        "product_url": "https://www.ravecoffee.co.uk/products/kirinyaga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 13.00, "avail": "in_stock", "sku": "RAVE-KEN-250"},
            {"title": "500g / Whole Bean", "weight_g": 500, "grind": "whole_bean", "base_price": 24.50, "avail": "in_stock", "sku": "RAVE-KEN-500"},
        ],
    },
    {
        "bean_key": "Kenya Kirinyaga AB Washed",
        "store": "www.monmouthcoffee.co.uk",
        "raw_title": "Kenya Kirinyaga",
        "product_url": "https://www.monmouthcoffee.co.uk/products/kenya",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 14.50, "avail": "in_stock",  "sku": "MON-KEN-250"},
            {"title": "250g / Espresso",   "weight_g": 250, "grind": "espresso",   "base_price": 14.50, "avail": "in_stock",  "sku": "MON-KEN-250-ESP"},
        ],
    },
]

FLAVOUR_FAMILIES = [
    {"slug": "fruity",    "label": "Fruity",    "colour": "#e05c3a", "sort_order": 1},
    {"slug": "floral",    "label": "Floral",    "colour": "#c084c0", "sort_order": 2},
    {"slug": "sweet",     "label": "Sweet",     "colour": "#d4a84b", "sort_order": 3},
    {"slug": "chocolate", "label": "Chocolate", "colour": "#7c4b2a", "sort_order": 4},
    {"slug": "nutty",     "label": "Nutty",     "colour": "#a07850", "sort_order": 5},
    {"slug": "spice",     "label": "Spice",     "colour": "#c47820", "sort_order": 6},
    {"slug": "earthy",    "label": "Earthy",    "colour": "#6b7c4a", "sort_order": 7},
    {"slug": "fermented", "label": "Fermented", "colour": "#8b6bab", "sort_order": 8},
]

BEAN_FLAVOUR_TAGS = {
    "Ethiopia Yirgacheffe Konga Washed": [
        ("jasmine",  "floral"),
        ("bergamot", "floral"),
        ("lemon",    "fruity"),
        ("peach",    "fruity"),
    ],
    "Colombia El Paraiso Anaerobic Natural": [
        ("tropical fruit", "fruity"),
        ("strawberry",     "fruity"),
        ("passionfruit",   "fruity"),
        ("candy",          "sweet"),
    ],
    "Kenya Kirinyaga AB Washed": [
        ("blackcurrant", "fruity"),
        ("grapefruit",   "fruity"),
        ("brown sugar",  "sweet"),
        ("tomato",       "earthy"),
    ],
}


# ── Seed runner ───────────────────────────────────────────────────────────────

async def seed_extended(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    # Fetch stores and beans
    store_rows = (await session.execute(select(Store))).scalars().all()
    store_ids = {s.domain: s.id for s in store_rows}
    bean_rows = (await session.execute(select(CanonicalBean))).scalars().all()
    bean_ids = {b.canonical_name: b.id for b in bean_rows}

    print(f"Found {len(store_ids)} stores, {len(bean_ids)} beans")

    # ── Flavour taxonomy ──────────────────────────────────────────────────────
    print("Seeding flavour taxonomy...")
    family_ids: dict[str, object] = {}
    for fam in FLAVOUR_FAMILIES:
        existing = (await session.execute(
            select(FlavourTaxonomy).where(FlavourTaxonomy.slug == fam["slug"])
        )).scalar_one_or_none()
        if existing is None:
            ft = FlavourTaxonomy(
                slug=fam["slug"],
                label=fam["label"],
                colour=fam["colour"],
                depth=0,
                sort_order=fam["sort_order"],
                synonyms=[],
            )
            session.add(ft)
            await session.flush()
            family_ids[fam["slug"]] = ft.id
            print(f"  + {fam['label']}")
        else:
            family_ids[fam["slug"]] = existing.id
    await session.flush()

    # ── Listings, variants, price history ─────────────────────────────────────
    print("Seeding listings and price history...")
    for spec in LISTING_SPECS:
        store_id = store_ids.get(spec["store"])
        bean_id = bean_ids.get(spec["bean_key"])
        if not store_id or not bean_id:
            print(f"  ⚠ Skipping {spec['raw_title']} — store or bean not found")
            continue

        content_hash = hashlib.sha256(
            f"{spec['raw_title']}{spec['product_url']}".encode()
        ).hexdigest()

        # Find or create listing
        existing_listing = (await session.execute(
            select(BeanListing).where(
                BeanListing.store_id == store_id,
                BeanListing.canonical_bean_id == bean_id,
            )
        )).scalar_one_or_none()

        if existing_listing is None:
            listing = BeanListing(
                store_id=store_id,
                canonical_bean_id=bean_id,
                raw_title=spec["raw_title"],
                product_url=spec["product_url"],
                listing_status="active",
                active_flag=True,
                first_seen_at=now - timedelta(days=60),
                last_seen_at=now,
                content_hash=content_hash,
            )
            session.add(listing)
            await session.flush()
            print(f"  + {spec['raw_title']} @ {spec['store']}")
        else:
            listing = existing_listing

        # Variants and price history
        for v in spec["variants"]:
            existing_variant = (await session.execute(
                select(ListingVariant).where(ListingVariant.sku == v["sku"])
            )).scalar_one_or_none()

            if existing_variant is None:
                variant = ListingVariant(
                    bean_listing_id=listing.id,
                    variant_title_raw=v["title"],
                    weight_g=v["weight_g"],
                    grind_type=v["grind"],
                    price_gbp=v["base_price"],
                    price_per_100g_gbp=p100(v["base_price"], v["weight_g"]),
                    currency_code="GBP",
                    availability_status=v["avail"],
                    sku=v["sku"],
                    seller_variant_id=v["sku"],
                )
                session.add(variant)
                await session.flush()

                # 60 days of price history
                for day in range(60, -1, -1):
                    price = synth_price(v["base_price"], day)
                    session.add(PriceHistory(
                        listing_variant_id=variant.id,
                        price_gbp=price,
                        price_per_100g_gbp=p100(price, v["weight_g"]),
                        availability_status=v["avail"],
                        recorded_at=now - timedelta(days=day),
                    ))

    await session.flush()

    # ── Bean flavour tags ─────────────────────────────────────────────────────
    print("Seeding flavour tags...")
    for bean_name, tags in BEAN_FLAVOUR_TAGS.items():
        bean_id = bean_ids.get(bean_name)
        if not bean_id:
            continue
        for note, family_slug in tags:
            tax_id = family_ids.get(family_slug)
            if not tax_id:
                continue
            existing = (await session.execute(
                select(BeanFlavourTag).where(
                    BeanFlavourTag.bean_id == bean_id,
                    BeanFlavourTag.raw_note == note,
                )
            )).scalar_one_or_none()
            if existing is None:
                session.add(BeanFlavourTag(
                    bean_id=bean_id,
                    taxonomy_id=tax_id,
                    raw_note=note,
                    confidence=0.9,
                    source="rule",
                    review_status="accepted",
                ))

    await session.commit()
    print("\nExtended seed complete!")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create PostgreSQL extensions required by models
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # Create all tables (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        await seed_extended(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
