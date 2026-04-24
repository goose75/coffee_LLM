"""
Extended seed script — adds everything needed to demo price + taste intelligence.

Run after: alembic upgrade head && python scripts/seed.py

New in this script (safe to re-run via ON CONFLICT DO NOTHING):
  - bean_listings  (3 beans × 3 stores = 9 listings)
  - listing_variants with weight/grind/price
  - price_history  (60 days of synthetic history per variant)
  - flavour_taxonomy (full 3-level tree)
  - bean_flavour_tags (pre-normalised, source='rule')

Run the original seed.py first to create stores and canonical beans.
This script assumes those exist.
"""

import asyncio
import os
import sys
import hashlib
from datetime import datetime, timedelta, timezone
from math import sin, pi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.core.config import settings
from app.services.taste.taxonomy import TAXONOMY


# ─── Price history helpers ─────────────────────────────────────────────────────

def _synth_price(base: float, day: int, amplitude: float = 0.08) -> float:
    """Generate a realistic-looking price with slow drift and small noise."""
    noise = sin(day * 0.3) * amplitude * base + sin(day * 1.1) * amplitude * 0.5 * base
    return round(base + noise, 2)


def _p100(price: float, weight_g: int) -> float:
    return round(price / weight_g * 100, 4)


# ─── Listing / variant definitions ────────────────────────────────────────────

LISTING_SPECS = [
    # bean_name_key, store_domain, raw_title, product_url, variants
    {
        "bean_key": "Ethiopia Yirgacheffe Konga Washed",
        "store": "shop.squaremilecoffee.com",
        "raw_title": "Yirgacheffe Konga",
        "product_url": "https://shop.squaremilecoffee.com/products/yirgacheffe-konga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 12.50, "avail": "in_stock", "sku": "SMC-ETH-250-WB"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean", "base_price": 42.00, "avail": "in_stock", "sku": "SMC-ETH-1K-WB"},
        ],
    },
    {
        "bean_key": "Ethiopia Yirgacheffe Konga Washed",
        "store": "www.workshopcoffee.com",
        "raw_title": "Ethiopia Konga Washed 2024",
        "product_url": "https://www.workshopcoffee.com/products/ethiopia-konga",
        "variants": [
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 13.50, "avail": "in_stock", "sku": "WC-ETH-250"},
            {"title": "250g / Filter",     "weight_g": 250, "grind": "filter",     "base_price": 13.50, "avail": "in_stock", "sku": "WC-ETH-250-F"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000, "grind": "whole_bean","base_price": 44.00, "avail": "out_of_stock","sku": "WC-ETH-1K"},
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
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 18.50, "avail": "in_stock", "sku": "SMC-COL-250"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000,"grind": "whole_bean", "base_price": 62.00, "avail": "in_stock", "sku": "SMC-COL-1K"},
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
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 14.00, "avail": "in_stock", "sku": "SMC-KEN-250"},
            {"title": "1kg / Whole Bean",  "weight_g": 1000,"grind": "whole_bean", "base_price": 48.00, "avail": "in_stock", "sku": "SMC-KEN-1K"},
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
            {"title": "250g / Whole Bean", "weight_g": 250, "grind": "whole_bean", "base_price": 14.50, "avail": "in_stock", "sku": "MON-KEN-250"},
            {"title": "250g / Espresso",   "weight_g": 250, "grind": "espresso",   "base_price": 14.50, "avail": "in_stock", "sku": "MON-KEN-250-ESP"},
        ],
    },
]


# ─── Seed runner ──────────────────────────────────────────────────────────────

async def seed_extended(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    # ── Fetch store IDs ────────────────────────────────────────────────────────
    print("\nFetching store IDs...")
    store_rows = await session.execute(text("SELECT id, domain FROM stores"))
    store_ids: dict[str, str] = {row.domain: str(row.id) for row in store_rows}
    if not store_ids:
        print("  ⚠ No stores found — run seed.py first")
        return
    print(f"  ✓ {len(store_ids)} stores found")

    # ── Fetch canonical bean IDs ───────────────────────────────────────────────
    print("\nFetching canonical bean IDs...")
    bean_rows = await session.execute(text("SELECT id, canonical_name FROM canonical_beans"))
    bean_ids: dict[str, str] = {row.canonical_name: str(row.id) for row in bean_rows}
    if not bean_ids:
        print("  ⚠ No canonical beans found — run seed.py first")
        return
    print(f"  ✓ {len(bean_ids)} beans found")

    # ── Seed listings + variants + price history ───────────────────────────────
    print("\nSeeding bean listings, variants, and price history...")
    for spec in LISTING_SPECS:
        bean_name = spec["bean_key"]
        store_domain = spec["store"]
        bean_id = bean_ids.get(bean_name)
        store_id = store_ids.get(store_domain)

        if not bean_id or not store_id:
            print(f"  ⚠ Skipping {bean_name[:30]} @ {store_domain} — not found")
            continue

        content = hashlib.sha256(f"{spec['raw_title']}{spec['variants']}".encode()).hexdigest()

        # Upsert bean_listing
        listing_row = await session.execute(text("""
            INSERT INTO bean_listings (
                store_id, canonical_bean_id, raw_title, product_url,
                listing_status, active_flag, first_seen_at, last_seen_at,
                content_hash
            ) VALUES (
                :store_id::uuid, :bean_id::uuid, :raw_title, :product_url,
                'active'::listing_status, true, :first_seen, :first_seen,
                :content_hash
            )
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {
            "store_id": store_id, "bean_id": bean_id,
            "raw_title": spec["raw_title"], "product_url": spec["product_url"],
            "first_seen": now - timedelta(days=60),
            "content_hash": content,
        })
        listing_id_row = listing_row.fetchone()
        if not listing_id_row:
            # Already exists — fetch it
            existing = await session.execute(text("""
                SELECT id FROM bean_listings
                WHERE store_id = :store_id::uuid AND canonical_bean_id = :bean_id::uuid
                  AND raw_title = :raw_title
                LIMIT 1
            """), {"store_id": store_id, "bean_id": bean_id, "raw_title": spec["raw_title"]})
            row = existing.fetchone()
            if not row:
                continue
            listing_id = str(row.id)
        else:
            listing_id = str(listing_id_row.id)

        # Variants + history
        for v in spec["variants"]:
            p100 = _p100(v["base_price"], v["weight_g"])
            variant_row = await session.execute(text("""
                INSERT INTO listing_variants (
                    bean_listing_id, variant_title_raw, weight_g,
                    grind_type, price_gbp, price_per_100g_gbp,
                    availability_status, sku, seller_variant_id, recorded_at
                ) VALUES (
                    :listing_id::uuid, :title, :weight_g,
                    :grind::grind_type, :price, :p100,
                    :avail::availability_status, :sku, :sku, :now
                )
                ON CONFLICT DO NOTHING
                RETURNING id
            """), {
                "listing_id": listing_id, "title": v["title"],
                "weight_g": v["weight_g"], "grind": v["grind"],
                "price": v["base_price"], "p100": p100,
                "avail": v["avail"], "sku": v["sku"], "now": now,
            })
            variant_id_row = variant_row.fetchone()
            if not variant_id_row:
                existing_v = await session.execute(text(
                    "SELECT id FROM listing_variants WHERE sku = :sku LIMIT 1"
                ), {"sku": v["sku"]})
                row_v = existing_v.fetchone()
                if not row_v:
                    continue
                variant_id = str(row_v.id)
            else:
                variant_id = str(variant_id_row.id)

            # 60 days of price history (daily snapshots with realistic drift)
            for day in range(60):
                ts = now - timedelta(days=59 - day)
                hist_price = _synth_price(v["base_price"], day)
                hist_p100 = _p100(hist_price, v["weight_g"])
                await session.execute(text("""
                    INSERT INTO price_history (
                        listing_variant_id, price_gbp, price_per_100g_gbp,
                        availability_status, recorded_at
                    ) VALUES (
                        :vid::uuid, :price, :p100, :avail::availability_status, :ts
                    )
                    ON CONFLICT DO NOTHING
                """), {
                    "vid": variant_id, "price": hist_price,
                    "p100": hist_p100, "avail": v["avail"], "ts": ts,
                })

        print(f"  ✓ {bean_name[:35]:<35} @ {store_domain}")

    # ── Seed flavour taxonomy ──────────────────────────────────────────────────
    print("\nSeeding flavour taxonomy...")
    # Insert families first, then categories, then tags (depth order)
    slug_to_id: dict[str, str] = {}

    for depth in [0, 1, 2]:
        nodes = [n for n in TAXONOMY if n["depth"] == depth]
        for node in nodes:
            parent_id = slug_to_id.get(node["parent"]) if node["parent"] else None
            result = await session.execute(text("""
                INSERT INTO flavour_taxonomy (slug, label, depth, parent_id, colour, synonyms, sort_order)
                VALUES (:slug, :label, :depth, :parent_id::uuid, :colour, :synonyms, :sort_order)
                ON CONFLICT (slug) DO UPDATE SET label = EXCLUDED.label, synonyms = EXCLUDED.synonyms
                RETURNING id, slug
            """), {
                "slug": node["slug"], "label": node["label"], "depth": node["depth"],
                "parent_id": parent_id, "colour": node.get("colour"),
                "synonyms": node["synonyms"], "sort_order": node.get("sort_order", 0),
            })
            row = result.fetchone()
            if row:
                slug_to_id[row.slug] = str(row.id)

    print(f"  ✓ {len(TAXONOMY)} taxonomy nodes")

    # ── Seed bean_flavour_tags (rule-based, from existing flavour_notes) ───────
    print("\nSeeding bean flavour tags...")
    from app.services.taste.normaliser import match_note

    bean_note_rows = await session.execute(
        text("SELECT id, flavour_notes FROM canonical_beans WHERE array_length(flavour_notes, 1) > 0")
    )
    tag_count = 0
    for row in bean_note_rows:
        bean_id = str(row.id)
        notes: list[str] = row.flavour_notes or []
        for note in notes:
            match = match_note(note)
            if match is None:
                continue
            tax_id = slug_to_id.get(match.slug)
            if not tax_id:
                continue
            await session.execute(text("""
                INSERT INTO bean_flavour_tags
                    (bean_id, taxonomy_id, raw_note, confidence, source, review_status)
                VALUES
                    (:bean_id::uuid, :tax_id::uuid, :raw_note, :conf, 'rule', 'accepted')
                ON CONFLICT (bean_id, taxonomy_id, raw_note) DO NOTHING
            """), {
                "bean_id": bean_id, "tax_id": tax_id,
                "raw_note": note, "conf": match.confidence,
            })
            tag_count += 1

    print(f"  ✓ {tag_count} flavour tags created")

    await session.commit()
    print("\n✅ Extended seed complete.")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await seed_extended(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
