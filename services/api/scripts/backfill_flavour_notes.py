#!/usr/bin/env python3
"""
backfill_flavour_notes.py — Extract flavour notes from listing descriptions
and write them to canonical_beans.flavour_notes, then re-run the tagger.

Run inside the API container:
    docker exec coffee_api python scripts/backfill_flavour_notes.py
    docker exec coffee_api python scripts/backfill_flavour_notes.py --dry-run
"""
from __future__ import annotations
import argparse
import asyncio
import re
import sys
from collections import defaultdict

sys.path.insert(0, "/app")

# ── Supplement the taxonomy with extra common coffee notes ────────────────────
# These are real flavour descriptors used by UK roasters that aren't in the
# base taxonomy. We map them to the closest taxonomy label for now.

EXTRA_SYNONYMS: dict[str, str] = {
    # Stone / pome fruit
    "apple": "Apple",
    "red apple": "Apple",
    "green apple": "Apple",
    "cooking apple": "Apple",
    "pear": "Pear",
    "boysenberry": "Berry",
    "gooseberry": "Berry",
    "mulberry": "Berry",
    "loganberry": "Berry",
    "cranberry": "Berry",
    "redcurrant": "Berry",
    # Nuts
    "macadamia": "Nutty",
    "macadamia nut": "Nutty",
    "peanut": "Nutty",
    "pistachio": "Nutty",
    "cashew": "Nutty",
    "walnut": "Nutty",
    "pecan": "Nutty",
    # Chocolate / sweet
    "cocoa": "Chocolate",
    "cacao": "Chocolate",
    "toffee": "Caramel",
    "butterscotch": "Caramel",
    "fudge": "Caramel",
    "praline": "Caramel",
    "nougat": "Caramel",
    "marzipan": "Almond",
    "marshmallow": "Sweet",
    "vanilla pod": "Vanilla",
    "cream": "Sweet",
    "condensed milk": "Sweet",
    "milk chocolate": "Milk Chocolate",
    "dark chocolate": "Dark Chocolate",
    "white chocolate": "Sweet",
    # Floral
    "elderflower": "Elderflower",
    "rose water": "Rose",
    "violet": "Floral",
    "lavender": "Floral",
    "hibiscus": "Floral",
    "blossom": "Floral",
    "orange blossom": "Floral",
    # Spice
    "cinnamon": "Spice",
    "cardamom": "Spice",
    "clove": "Spice",
    "nutmeg": "Spice",
    "ginger": "Spice",
    "black pepper": "Spice",
    "allspice": "Spice",
    # Earthy / fermented
    "agave": "Sweet",
    "molasses": "Fermented",
    "treacle": "Fermented",
    "miso": "Fermented",
    "soy sauce": "Fermented",
    "kombucha": "Fermented",
    # Tea-like
    "green tea": "Tea",
    "black tea": "Tea",
    "oolong": "Tea",
    "chamomile": "Floral",
    # Other fruit
    "grape": "Fruity",
    "melon": "Fruity",
    "watermelon": "Fruity",
    "kiwi": "Fruity",
    "pomegranate": "Fruity",
    "lychee": "Lychee",
    "jackfruit": "Fruity",
    "nectarine": "Peach",
    "damson": "Plum",
    "sloe": "Berry",
    # Savoury
    "tobacco": "Earthy",
    "cedar": "Earthy",
    "oak": "Earthy",
    "leather": "Earthy",
    "mushroom": "Earthy",
}


def strip_html(html: str) -> str:
    """Remove HTML tags and decode basic entities."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&#39;', "'").replace('&quot;', '"')
    return re.sub(r'\s+', ' ', text).strip()


def extract_notes_from_text(text: str, syn_map: dict[str, str]) -> list[str]:
    """
    Extract flavour note labels from plain text using synonym matching.
    Returns deduplicated list of canonical label strings.
    """
    text_lower = text.lower()
    found: list[str] = []
    seen_labels: set[str] = set()

    # Sort by length descending — match "tropical fruit" before "fruit"
    for syn in sorted(syn_map.keys(), key=len, reverse=True):
        # Word-boundary aware match to avoid "lemon" matching "lemonade" etc.
        pattern = r'(?<![a-z])' + re.escape(syn) + r'(?![a-z])'
        if re.search(pattern, text_lower):
            label = syn_map[syn]
            if label not in seen_labels:
                found.append(label)
                seen_labels.add(label)
    return found


async def run(dry_run: bool) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.bean_listing import BeanListing
    from app.models.canonical_bean import CanonicalBean
    from app.services.extraction.product_classifier import ProductClassifier
    from app.services.taste.taxonomy import TAXONOMY
    from sqlalchemy import select, update

    # Build synonym map from taxonomy + extras
    syn_map: dict[str, str] = {}
    for node in TAXONOMY:
        if node["depth"] == 2:
            for syn in node.get("synonyms", []):
                syn_map[syn.lower()] = node["label"]
    # Add extra synonyms (lower priority — don't overwrite taxonomy)
    for syn, label in EXTRA_SYNONYMS.items():
        if syn not in syn_map:
            syn_map[syn] = label

    print(f"Synonym vocabulary: {len(syn_map)} terms")

    async with AsyncSessionLocal() as session:
        # Load canonical beans with empty flavour_notes that have listings
        result = await session.execute(
            select(CanonicalBean).where(CanonicalBean.flavour_notes == [])
        )
        all_beans = result.scalars().all()

        # Filter out non-coffee products
        beans = []
        non_coffee_beans = []
        for bean in all_beans:
            is_coffee, reason = ProductClassifier.is_coffee_bean_product(
                title=bean.canonical_name,
                description=None
            )
            if is_coffee:
                beans.append(bean)
            else:
                non_coffee_beans.append((bean, reason))

        print(f"Beans with empty flavour_notes: {len(all_beans)}")
        print(f"Non-coffee products filtered: {len(non_coffee_beans)}")
        print(f"Coffee beans to process: {len(beans)}")
        print()

        # Show filtered non-coffee products
        if non_coffee_beans and len(non_coffee_beans) <= 20:
            print("Filtered non-coffee products:")
            for bean, reason in non_coffee_beans:
                print(f"  ✗ {bean.canonical_name[:60]:60} ({reason})")
            print()

        bean_ids = [b.id for b in beans]

        # Load all listings for these beans that have descriptions
        listings_result = await session.execute(
            select(BeanListing).where(
                BeanListing.canonical_bean_id.in_(bean_ids),
                BeanListing.raw_description.isnot(None),
            )
        )
        listings = listings_result.scalars().all()

        # Group listings by bean_id
        listings_by_bean: dict = defaultdict(list)
        for listing in listings:
            listings_by_bean[listing.canonical_bean_id].append(listing)

        print(f"Listings with descriptions: {len(listings)} across {len(listings_by_bean)} beans")

        updated = 0
        skipped = 0

        for bean in beans:
            bean_listings = listings_by_bean.get(bean.id, [])
            if not bean_listings:
                skipped += 1
                continue

            # Combine all description text for this bean
            all_text = " ".join(
                strip_html(l.raw_description or "")
                for l in bean_listings
            )

            notes = extract_notes_from_text(all_text, syn_map)

            if not notes:
                skipped += 1
                continue

            if dry_run:
                print(f"  DRY: {bean.canonical_name[:50]} → {notes[:6]}")
            else:
                bean.flavour_notes = notes
                updated += 1

            if not dry_run and updated % 10 == 0:
                await session.commit()
                print(f"  Committed {updated} beans so far...")

        if not dry_run:
            await session.commit()

        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Non-coffee products filtered: {len(non_coffee_beans)} (tea, pods, machines, etc.)")
        print(f"Coffee beans processed:      {len(beans)}")
        print(f"Updated with flavour notes:  {updated}")
        print(f"Skipped (no descriptions):   {skipped}")
        print(f"{'='*70}")

        if not dry_run and updated > 0:
            print("\nNow triggering flavour tagger on updated beans...")
            # Trigger the admin taste/tag-all endpoint via internal call
            import urllib.request
            try:
                urllib.request.urlopen(
                    urllib.request.Request(
                        "http://localhost:8000/api/v1/admin/taste/tag-all",
                        method="POST"
                    ),
                    timeout=10
                )
                print("✓ Tagger triggered — check logs for progress")
            except Exception as e:
                print(f"Could not auto-trigger tagger: {e}")
                print("Run manually: curl -X POST http://localhost:8000/api/v1/admin/taste/tag-all")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
