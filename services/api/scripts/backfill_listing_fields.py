#!/usr/bin/env python3
"""
backfill_listing_fields.py — Backfill structured fields on existing listings
from their raw_title using the enhanced parser logic.

Run inside the API container:
    docker exec coffee_api python scripts/backfill_listing_fields.py
    docker exec coffee_api python scripts/backfill_listing_fields.py --dry-run
"""
from __future__ import annotations
import argparse, asyncio, re, sys
sys.path.insert(0, "/app")

_TITLE_ORIGINS = {
    "costa rica": "Costa Rica", "el salvador": "El Salvador",
    "papua new guinea": "Papua New Guinea",
    "ethiopian": "Ethiopia", "ethiopia": "Ethiopia",
    "kenyan": "Kenya", "kenya": "Kenya",
    "colombian": "Colombia", "colombia": "Colombia",
    "brazilian": "Brazil", "brazil": "Brazil",
    "guatemalan": "Guatemala", "guatemala": "Guatemala",
    "rwandan": "Rwanda", "rwanda": "Rwanda",
    "panamanian": "Panama", "panama": "Panama",
    "honduran": "Honduras", "honduras": "Honduras",
    "peruvian": "Peru", "peru": "Peru",
    "burundian": "Burundi", "burundi": "Burundi",
    "ugandan": "Uganda", "uganda": "Uganda",
    "indonesian": "Indonesia", "indonesia": "Indonesia",
    "yemeni": "Yemen", "yemen": "Yemen",
    "indian": "India", "india": "India",
    "mexican": "Mexico", "mexico": "Mexico",
    "nicaraguan": "Nicaragua", "nicaragua": "Nicaragua",
    "tanzanian": "Tanzania", "tanzania": "Tanzania",
    "bolivian": "Bolivia", "bolivia": "Bolivia",
    "ecuadorian": "Ecuador", "ecuador": "Ecuador",
    "thailand": "Thailand",
}
_TITLE_PROCESSES = {
    "pulped natural": "natural", "wet process": "washed",
    "carbonic maceration": "anaerobic", "anaerobic": "anaerobic",
    "washed": "washed", "natural": "natural", "honey": "honey",
}
_TITLE_ROASTS = {
    "lightly roasted": "light", "light roast": "light",
    "medium roast": "medium", "dark roast": "dark", "espresso roast": "dark",
}
_TITLE_VARIETALS = [
    "pink bourbon", "sl28", "sl34", "pacamara", "geisha", "gesha",
    "typica", "bourbon", "caturra", "catuai", "sidra", "mejorado",
    "tabi", "java", "s795", "heirloom", "arabica",
]

def extract_from_title(title: str) -> dict:
    t = title.lower()
    return {
        "origin": next((v for k,v in sorted(_TITLE_ORIGINS.items(), key=lambda x:-len(x[0])) if k in t), None),
        "process": next((v for k,v in sorted(_TITLE_PROCESSES.items(), key=lambda x:-len(x[0])) if k in t), None),
        "roast": next((v for k,v in sorted(_TITLE_ROASTS.items(), key=lambda x:-len(x[0])) if k in t), None),
        "varietal": next((v for v in sorted(_TITLE_VARIETALS, key=len, reverse=True) if v in t), None),
    }

async def run(dry_run: bool) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.bean_listing import BeanListing
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BeanListing))
        listings = result.scalars().all()
        print(f"Loaded {len(listings)} listings")

        updated = 0
        for listing in listings:
            fields = extract_from_title(listing.raw_title or "")
            changed = False

            if not listing.origin_label_raw and fields["origin"]:
                listing.origin_label_raw = fields["origin"]
                changed = True
            if not listing.process_label_raw and fields["process"]:
                listing.process_label_raw = fields["process"]
                changed = True
            if not listing.roast_label_raw and fields["roast"]:
                listing.roast_label_raw = fields["roast"]
                changed = True
            if not listing.varietal_label_raw and fields["varietal"]:
                listing.varietal_label_raw = fields["varietal"]
                changed = True

            if changed:
                updated += 1
                if dry_run and updated <= 15:
                    print(f"  {listing.raw_title[:60]}")
                    print(f"    origin={fields['origin']} process={fields['process']} roast={fields['roast']} varietal={fields['varietal']}")

        if not dry_run:
            await session.commit()
            print(f"\n✓ Updated {updated}/{len(listings)} listings")
        else:
            print(f"\nDRY RUN: would update {updated}/{len(listings)} listings")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args.dry_run))

if __name__ == "__main__":
    main()
