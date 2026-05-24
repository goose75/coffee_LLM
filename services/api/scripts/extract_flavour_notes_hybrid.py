#!/usr/bin/env python3
"""
extract_flavour_notes_hybrid.py — Extract flavour notes using hybrid system.

Uses the intelligent three-tier approach:
  1. Rule-based extraction (instant, free) — ~70% of products
  2. Ollama local LLM (free) — ~25% of products
  3. Anthropic API fallback (paid) — ~5% of products

Run inside the API container:
    docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py
    docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run
    docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --limit 10

Usage:
    --dry-run           Show what would be extracted without saving
    --limit N           Process only first N beans
    --force-api-only    Skip Ollama, use API directly (for testing)
    --skip-ollama       Use rules + API only, skip Ollama
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict

sys.path.insert(0, "/app")


async def extract_flavour_notes(
    bean_id: str,
    bean_name: str,
    descriptions: list[str],
    use_hybrid: bool = True,
    use_api_fallback: bool = True,
    skip_ollama: bool = False,
) -> dict:
    """
    Extract flavour notes from descriptions using hybrid system.

    Returns:
        {
            "notes": ["Lemon", "Floral", ...],
            "strategy": "rule" | "ollama" | "llm" | "none",
            "confidence": 0.0-1.0,
            "raw_notes": ["lemon", "floral", ...] (before taxonomy mapping),
        }
    """
    from app.services.extraction.hybrid_extractor import HybridExtractor
    from app.services.extraction.llm_parser import clean_page_text
    from app.services.taste.taxonomy import TAXONOMY

    # Build taxonomy synonym map
    syn_map: dict[str, str] = {}
    for node in TAXONOMY:
        if node["depth"] == 2:  # Only leaf nodes
            for syn in node.get("synonyms", []):
                syn_map[syn.lower()] = node["label"]

    # Combine all descriptions
    combined_text = "\n".join(descriptions)
    html_bytes = combined_text.encode('utf-8')

    # Use hybrid extraction with focus on flavour notes
    # use_hybrid=False means force API only (skip rules)
    # skip_ollama=True means skip Ollama layer (use rules + API)
    # use_api_fallback=False means no API fallback
    extractor = HybridExtractor(
        use_ollama=use_hybrid and not skip_ollama,  # If not skip_ollama, try Ollama
        use_api_fallback=use_api_fallback,  # Whether to use API as final fallback
    )

    try:
        result = await extractor.extract(html_bytes, f"bean:{bean_id}")

        # Extract flavour notes from payload
        raw_notes = result.final_result.payload.flavour_notes

        # Map raw notes to taxonomy
        taxonomy_notes = []
        for note in raw_notes:
            note_lower = note.lower().strip()
            if note_lower in syn_map:
                tax_label = syn_map[note_lower]
                if tax_label not in taxonomy_notes:
                    taxonomy_notes.append(tax_label)

        return {
            "notes": taxonomy_notes,
            "strategy": result.strategy_used,
            "confidence": result.confidence,
            "raw_notes": raw_notes,
            "reasoning": result.reasoning,
        }

    except Exception as exc:
        print(f"    ERROR extracting flavour: {exc}")
        return {
            "notes": [],
            "strategy": "error",
            "confidence": 0.0,
            "raw_notes": [],
            "reasoning": str(exc),
        }


async def run(
    dry_run: bool = False,
    limit: int = 0,
    force_api_only: bool = False,
    skip_ollama: bool = False,
) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.bean_listing import BeanListing
    from app.models.canonical_bean import CanonicalBean
    from app.services.extraction.product_classifier import ProductClassifier
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as session:
        # Load canonical beans with missing/incomplete flavour_notes
        result = await session.execute(
            select(CanonicalBean).where(
                (CanonicalBean.flavour_notes == []) |
                (CanonicalBean.flavour_notes == None) |
                (func.array_length(CanonicalBean.flavour_notes, 1) < 2)
            ).order_by(CanonicalBean.created_at.desc())
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

        if limit:
            beans = beans[:limit]

        print(f"Total beans with missing/sparse flavour notes: {len(all_beans)}")
        print(f"Filtered (non-coffee products): {len(non_coffee_beans)}")
        print(f"Processing (actual coffee): {len(beans)}")
        print(f"Dry-run: {dry_run}")
        print(f"Use Hybrid: {not force_api_only}")
        print(f"Skip Ollama: {skip_ollama}")
        print()

        # Show non-coffee products that were filtered
        if non_coffee_beans and len(non_coffee_beans) <= 20:
            print("Filtered non-coffee products:")
            for bean, reason in non_coffee_beans:
                print(f"  ✗ {bean.canonical_name[:60]:60} ({reason})")
            print()

        # Load all listings
        listings_result = await session.execute(
            select(BeanListing).where(
                BeanListing.canonical_bean_id.in_([b.id for b in beans]),
                BeanListing.raw_description.isnot(None),
            )
        )
        listings = listings_result.scalars().all()

        listings_by_bean: dict = defaultdict(list)
        for listing in listings:
            listings_by_bean[listing.canonical_bean_id].append(listing)

        print(f"Found {len(listings)} listings with descriptions\n")

        # Statistics
        stats = {
            "rule": 0,
            "ollama": 0,
            "llm": 0,
            "error": 0,
            "updated": 0,
            "skipped": 0,
        }

        for i, bean in enumerate(beans):
            bean_listings = listings_by_bean.get(bean.id, [])
            if not bean_listings:
                stats["skipped"] += 1
                continue

            descriptions = [
                l.raw_description or ""
                for l in bean_listings
                if l.raw_description
            ]

            if not descriptions:
                stats["skipped"] += 1
                continue

            # Extract flavour notes
            extraction = await extract_flavour_notes(
                str(bean.id),
                bean.canonical_name,
                descriptions,
                use_hybrid=not force_api_only,
                use_api_fallback=True,  # Always use API as fallback
                skip_ollama=skip_ollama,  # Skip Ollama layer if requested
            )

            # Track strategy
            if extraction["strategy"] in ["rule", "ollama", "llm"]:
                stats[extraction["strategy"]] += 1
            else:
                stats["error"] += 1

            notes = extraction["notes"]

            # Show progress
            if dry_run:
                print(
                    f"[{i+1}/{len(beans)}] {bean.canonical_name[:50]:50} "
                    f"→ {len(notes):2} notes (via {extraction['strategy']:6}, "
                    f"confidence {extraction['confidence']:.2f})"
                )
                if notes:
                    print(f"         {', '.join(notes[:8])}")
            else:
                if notes:
                    bean.flavour_notes = notes
                    stats["updated"] += 1
                    print(
                        f"[{i+1}/{len(beans)}] ✓ {bean.canonical_name[:50]:50} "
                        f"→ {len(notes):2} notes ({extraction['strategy']})"
                    )
                else:
                    stats["skipped"] += 1
                    print(
                        f"[{i+1}/{len(beans)}] ✗ {bean.canonical_name[:50]:50} "
                        f"→ no notes found"
                    )

                # Commit every 10 updates
                if stats["updated"] % 10 == 0:
                    await session.commit()
                    print(f"    Committed {stats['updated']} beans so far...")

        # Final commit
        if not dry_run and stats["updated"] > 0:
            await session.commit()

        # Summary
        print("\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Non-coffee filtered: {len(non_coffee_beans):5} (tea, pods, machines, etc.)")
        print(f"Coffee products:     {len(beans):5} (processed)")
        print(f"Updated beans:       {stats['updated']:5} (with flavour notes)")
        print(f"Skipped:             {stats['skipped']:5} (no descriptions)")
        print(f"Strategy breakdown:")
        print(f"  ├─ Rule extraction: {stats['rule']:5} (instant, free)")
        print(f"  ├─ Ollama (local):  {stats['ollama']:5} (free)")
        print(f"  ├─ API fallback:    {stats['llm']:5} (paid)")
        print(f"  └─ Errors:          {stats['error']:5}")

        total_processed = stats["rule"] + stats["ollama"] + stats["llm"] + stats["error"]
        if total_processed > 0:
            api_percentage = (stats["llm"] / total_processed) * 100
            print(f"\nAPI Usage: {api_percentage:.1f}% (cost savings: {100-api_percentage:.0f}%)")

        print("=" * 70)

        if not dry_run and stats["updated"] > 0:
            print(f"\n✓ Flavour notes updated for {stats['updated']} beans")
            print("\nNow triggering flavour tagger...")
            try:
                import urllib.request
                urllib.request.urlopen(
                    urllib.request.Request(
                        "http://localhost:8000/api/v1/admin/taste/tag-all",
                        method="POST"
                    ),
                    timeout=30
                )
                print("✓ Tagger triggered — check logs for progress")
            except Exception as e:
                print(f"⚠ Could not auto-trigger tagger: {e}")
                print("  Run manually: curl -X POST http://localhost:8000/api/v1/admin/taste/tag-all")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract flavour notes using hybrid system (rule + Ollama + API)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N beans")
    parser.add_argument(
        "--force-api-only",
        action="store_true",
        help="Skip Ollama, use API directly (testing only)"
    )
    parser.add_argument(
        "--skip-ollama",
        action="store_true",
        help="Use rule + API only, skip Ollama"
    )

    args = parser.parse_args()

    asyncio.run(run(
        dry_run=args.dry_run,
        limit=args.limit,
        force_api_only=args.force_api_only,
        skip_ollama=args.skip_ollama,
    ))


if __name__ == "__main__":
    main()
