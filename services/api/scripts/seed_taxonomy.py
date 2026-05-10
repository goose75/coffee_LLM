#!/usr/bin/env python3
"""
seed_taxonomy.py — Populate the flavour_taxonomy table with the full 3-level tree.

The initial migration only seeded depth-0 family nodes. This script inserts
all missing depth-1 (category) and depth-2 (tag) nodes, then updates synonyms
on all nodes.

Run inside the API container:
    docker exec coffee_api python scripts/seed_taxonomy.py
"""

from __future__ import annotations
import asyncio
import sys

sys.path.insert(0, "/app")


async def run() -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.flavour import FlavourTaxonomy
    from app.services.taste.taxonomy import TAXONOMY
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Load existing nodes by slug
        existing = (await session.execute(select(FlavourTaxonomy))).scalars().all()
        existing_by_slug: dict[str, FlavourTaxonomy] = {n.slug: n for n in existing}
        print(f"Existing nodes in DB: {len(existing_by_slug)}")

        # Build slug → UUID map for parent lookups
        slug_to_id = {slug: node.id for slug, node in existing_by_slug.items()}

        inserted = 0
        updated = 0

        for entry in TAXONOMY:
            slug = entry["slug"]
            parent_slug = entry.get("parent")
            parent_id = slug_to_id.get(parent_slug) if parent_slug else None

            if slug in existing_by_slug:
                # Update synonyms and colour if changed
                node = existing_by_slug[slug]
                changed = False
                if node.synonyms != entry.get("synonyms", []):
                    node.synonyms = entry.get("synonyms", [])
                    changed = True
                if entry.get("colour") and node.colour != entry["colour"]:
                    node.colour = entry["colour"]
                    changed = True
                if node.sort_order != entry.get("sort_order", 0):
                    node.sort_order = entry.get("sort_order", 0)
                    changed = True
                if parent_id and node.parent_id != parent_id:
                    node.parent_id = parent_id
                    changed = True
                if changed:
                    updated += 1
            else:
                # Insert new node
                node = FlavourTaxonomy(
                    slug=slug,
                    label=entry["label"],
                    depth=entry["depth"],
                    parent_id=parent_id,
                    colour=entry.get("colour"),
                    synonyms=entry.get("synonyms", []),
                    sort_order=entry.get("sort_order", 0),
                )
                session.add(node)
                slug_to_id[slug] = node.id
                inserted += 1

        await session.commit()
        print(f"Done: {inserted} inserted, {updated} updated")

        # Verify
        total = (await session.execute(
            select(FlavourTaxonomy)
        )).scalars().all()
        by_depth = {}
        for n in total:
            by_depth[n.depth] = by_depth.get(n.depth, 0) + 1
        for d, count in sorted(by_depth.items()):
            label = {0: "families", 1: "categories", 2: "tags"}.get(d, f"depth-{d}")
            print(f"  depth {d} ({label}): {count} nodes")


if __name__ == "__main__":
    asyncio.run(run())
