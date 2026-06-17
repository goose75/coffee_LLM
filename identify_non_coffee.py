#!/usr/bin/env python3
"""
Identify non-coffee items in the database using the coffee_classifier.
"""
import os
import sys
import re
from collections import defaultdict

# Add the API service path
sys.path.insert(0, '/Users/travisganz/coffee_LLM/services/api')

# We'll use the shopify classifier since it's more comprehensive
_EXCLUDE_PATTERNS = [
    re.compile(p, re.I) for p in [
        # Subscriptions
        r"\bsubscription\b",
        r"\b(?:weekly|monthly|fortnightly|quarterly)\s+(?:plan|box|delivery)\b",
        r"\b(?:one|two|three|four|six|twelve)[\s-]*month\b",

        # Gift sets, bundles
        r"\bgift\s*(set|box|pack|card|message)\b",
        r"\bbundle\b",

        # Capsules/pods
        r"\bcapsule[s]?\b", r"\bpod[s]?\b", r"\bnespresso\b",

        # Equipment
        r"\bgrinder\b", r"\bkettle\b", r"\bscale[s]?\b",
        r"\bfellow\b", r"\bbialetti\b", r"\bchemex\b",
        r"\baeropress\b",

        # Courses/classes
        r"\bcourse\b", r"\bclass\b", r"\bworkshop\b",

        # Merchandise
        r"\bposter\b", r"\bprint\b", r"\bt-?shirt\b",

        # Non-coffee
        r"\bmatcha\b", r"\bdrinking\s+chocolate\b",
    ]
]

async def main():
    import asyncpg

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Parse connection string
    conn = await asyncpg.connect(db_url)

    try:
        # Get all canonical beans
        beans = await conn.fetch(
            'SELECT id, canonical_name FROM canonical_beans ORDER BY canonical_name'
        )

        print(f"Total canonical beans: {len(beans)}\n")

        non_coffee = []
        by_category = defaultdict(list)

        for bean_id, name in beans:
            name_lower = name.lower()

            # Check against exclude patterns
            for pattern in _EXCLUDE_PATTERNS:
                if pattern.search(name_lower):
                    reason = pattern.pattern[:50]
                    non_coffee.append((bean_id, name, reason))

                    # Categorize
                    if 'subscription' in reason or 'month' in reason:
                        by_category['Subscriptions'].append(name)
                    elif 'gift' in reason or 'bundle' in reason:
                        by_category['Bundles & Gifts'].append(name)
                    elif 'capsule' in reason or 'pod' in reason:
                        by_category['Pods & Capsules'].append(name)
                    elif 'grinder' in reason or 'scale' in reason or 'kettle' in reason:
                        by_category['Equipment'].append(name)
                    elif 'course' in reason or 'class' in reason:
                        by_category['Courses'].append(name)
                    else:
                        by_category['Other'].append(name)
                    break

        print("=" * 80)
        print("NON-COFFEE ITEMS FOUND")
        print("=" * 80)

        for category in sorted(by_category.keys()):
            items = by_category[category]
            print(f"\n{category}: {len(items)} items")
            print("-" * 80)
            for item in items[:10]:
                print(f"  ✗ {item}")
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")

        print(f"\n\nTotal non-coffee items: {len(non_coffee)}")
        print(f"Percentage to remove: {len(non_coffee) / len(beans) * 100:.1f}%")

    finally:
        await conn.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
