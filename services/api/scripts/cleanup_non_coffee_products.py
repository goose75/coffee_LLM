#!/usr/bin/env python3
"""
cleanup_non_coffee_products.py — Remove non-coffee products from the database.

This script identifies and removes products that are not coffee beans:
- Teas, chais, and herbal beverages
- Coffee pods, capsules, and machines
- Barista courses and training
- Subscriptions, bundles, and gift sets
- Chocolate bars and other non-coffee items
- Equipment, utensils, and accessories

Run inside the API container:
    docker exec coffee_api python scripts/cleanup_non_coffee_products.py --dry-run
    docker exec coffee_api python scripts/cleanup_non_coffee_products.py --confirm
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict

sys.path.insert(0, "/app")


async def run(dry_run: bool = True, show_all: bool = False) -> None:
    """
    Identify and remove non-coffee products from canonical_beans.

    Args:
        dry_run: If True, show what would be deleted without deleting
        show_all: If True, show all non-coffee products (not just first 20)
    """
    from app.core.database import AsyncSessionLocal
    from app.models.canonical_bean import CanonicalBean
    from app.models.bean_listing import BeanListing
    from app.models.flavour import BeanFlavourTag
    from app.services.extraction.product_classifier import ProductClassifier
    from sqlalchemy import select, delete

    async with AsyncSessionLocal() as session:
        # Load all canonical beans
        result = await session.execute(select(CanonicalBean))
        all_beans = result.scalars().all()

        print(f"Total canonical beans in database: {len(all_beans)}")
        print()

        # Classify each bean
        coffee_beans = []
        non_coffee_beans = []

        for bean in all_beans:
            is_coffee, reason = ProductClassifier.is_coffee_bean_product(
                title=bean.canonical_name, description=None
            )
            if is_coffee:
                coffee_beans.append(bean)
            else:
                non_coffee_beans.append((bean, reason))

        print(f"Coffee beans to keep:          {len(coffee_beans)}")
        print(f"Non-coffee products to remove: {len(non_coffee_beans)}")
        print()

        # Show examples of what will be removed
        print("=" * 80)
        print("NON-COFFEE PRODUCTS TO REMOVE")
        print("=" * 80)

        if non_coffee_beans:
            # Group by reason
            by_reason: dict[str, list] = defaultdict(list)
            for bean, reason in non_coffee_beans:
                by_reason[reason].append(bean)

            for reason in sorted(by_reason.keys()):
                items = by_reason[reason]
                print(f"\n{reason.upper()}: {len(items)} items")
                print("-" * 80)

                display_items = items if show_all else items[:10]
                for bean in display_items:
                    print(f"  ✗ {bean.canonical_name[:70]}")

                if not show_all and len(items) > 10:
                    print(f"  ... and {len(items) - 10} more")

        print("\n" + "=" * 80)

        if dry_run:
            print("DRY RUN: No changes made")
            print()
            print("To actually delete non-coffee products, run:")
            print("  docker exec coffee_api python scripts/cleanup_non_coffee_products.py --confirm")
            return

        # DELETION PHASE (only if --confirm was passed)
        print("DELETING NON-COFFEE PRODUCTS...")
        print()

        from sqlalchemy import text

        bean_ids_to_delete = [str(bean.id) for bean, _ in non_coffee_beans]
        bean_ids_str = ", ".join(f"'{id}'" for id in bean_ids_to_delete)

        print(f"Will delete {len(non_coffee_beans)} non-coffee canonical beans and all related records")
        print()

        try:
            # Use raw SQL with CASCADE to handle all dependencies
            print("Step 1: Deleting canonical matches...")
            await session.execute(
                text(f"""
                    DELETE FROM canonical_matches
                    WHERE proposed_canonical_bean_id IN ({bean_ids_str})
                       OR bean_listing_id IN (
                           SELECT id FROM bean_listings
                           WHERE canonical_bean_id IN ({bean_ids_str})
                       )
                """)
            )
            print("  ✓ Canonical matches deleted")

            print("Step 2: Deleting flavour tags...")
            await session.execute(
                text(f"DELETE FROM bean_flavour_tags WHERE bean_id IN ({bean_ids_str})")
            )
            print("  ✓ Flavour tags deleted")

            print("Step 3: Deleting bean listings and variants...")
            await session.execute(
                text(f"""
                    DELETE FROM listing_variants
                    WHERE bean_listing_id IN (
                        SELECT id FROM bean_listings
                        WHERE canonical_bean_id IN ({bean_ids_str})
                    )
                """)
            )
            await session.execute(
                text(f"""
                    DELETE FROM price_history
                    WHERE listing_variant_id IN (
                        SELECT id FROM listing_variants
                        WHERE bean_listing_id IN (
                            SELECT id FROM bean_listings
                            WHERE canonical_bean_id IN ({bean_ids_str})
                        )
                    )
                """)
            )
            await session.execute(
                text(f"""
                    DELETE FROM bean_listings
                    WHERE canonical_bean_id IN ({bean_ids_str})
                """)
            )
            print("  ✓ Bean listings, variants, and price history deleted")

            print("Step 4: Deleting canonical beans...")
            await session.execute(
                text(f"DELETE FROM canonical_beans WHERE id IN ({bean_ids_str})")
            )
            print("  ✓ Canonical beans deleted")

            # Commit all deletions
            await session.commit()
            print()
            print("=" * 80)
            print("CLEANUP COMPLETE")
            print("=" * 80)
            print(f"✓ Deleted {len(non_coffee_beans)} non-coffee canonical beans")
            print(f"✓ Deleted all associated bean listings, variants, and price history")
            print(f"✓ Deleted all associated flavour tags and canonical matches")
            print()
            print(f"Database now contains {len(coffee_beans)} genuine coffee beans")
            print("=" * 80)

        except Exception as exc:
            await session.rollback()
            print(f"ERROR during deletion: {exc}")
            print("All changes rolled back.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove non-coffee products from canonical_beans table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without actually deleting (default)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete non-coffee products (required to make changes)",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all non-coffee products (not just first 10 per category)",
    )

    args = parser.parse_args()

    # If --confirm is passed, don't do dry-run
    dry_run = not args.confirm

    asyncio.run(run(dry_run=dry_run, show_all=args.show_all))


if __name__ == "__main__":
    main()
