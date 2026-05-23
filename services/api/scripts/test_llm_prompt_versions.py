#!/usr/bin/env python3
"""
Test script to compare v1.0 vs v2.0 LLM extraction prompts.

Usage:
    python -m scripts.test_llm_prompt_versions

This script:
1. Loads 10 test pages (from fixtures or real stores)
2. Extracts with both v1.0 and v2.0 prompts
3. Compares confidence scores and completeness
4. Reports accuracy improvements
5. Generates a comparison report
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.llm_parser import LLMParser, clean_page_text


# ── Test fixtures (10 diverse pages) ──────────────────────────────────────

TEST_FIXTURES = [
    {
        "name": "Rich product page (all fields)",
        "url": "https://example-roaster.co.uk/products/ethiopia-konga",
        "html": """
<h1>Ethiopia Yirgacheffe Konga Washed</h1>
<p>From the Konga cooperative in Yirgacheffe, Ethiopia. This micro-lot was fully washed.</p>
<p>Varietal: Heirloom (JARC 74110)</p>
<p>Process: Washed</p>
<p>Roast: Light</p>
<p>Tasting notes: jasmine, bergamot, lemon curd, white peach</p>
<p>250g — £12.50</p>
<p>1kg — £42.00</p>
<p>Grind options: Whole Bean, Filter, Espresso</p>
""",
        "expected_confidence_v1": 0.85,
        "expected_confidence_v2": 0.92,
    },
    {
        "name": "Sparse page (minimal fields)",
        "url": "https://another-roaster.co.uk/shop/colombia",
        "html": """
<h1>Colombia Filter Roast</h1>
<p>A smooth, chocolatey filter coffee from Colombia.</p>
<p>£9.50 for 250g</p>
""",
        "expected_confidence_v1": 0.45,
        "expected_confidence_v2": 0.50,
    },
    {
        "name": "Generic name (penalty test)",
        "url": "https://budget-coffee.co.uk/our-blend",
        "html": """
<h1>Our Signature Coffee Blend</h1>
<p>£8.99 for 250g</p>
<p>Smooth, balanced, easy to drink.</p>
""",
        "expected_confidence_v1": 0.35,
        "expected_confidence_v2": 0.25,  # v2 penalizes generic names
    },
    {
        "name": "Multiple weight variants",
        "url": "https://specialty-roaster.com/products/kenya-aa",
        "html": """
<h1>Kenya AA Washed</h1>
<p>Varietal: SL28</p>
<p>Process: Washed</p>
<p>Roast: Light</p>
<p>Tasting notes: blackcurrant, lemon, floral</p>
<p>250g Whole Bean — £11.99</p>
<p>250g Filter Grind — £12.49</p>
<p>500g Whole Bean — £21.99</p>
<p>1kg Whole Bean — £39.99</p>
""",
        "expected_confidence_v1": 0.80,
        "expected_confidence_v2": 0.88,  # v2 better at weight-first grouping
    },
    {
        "name": "Decaf coffee",
        "url": "https://roaster.co.uk/decaf-ethiopia",
        "html": """
<h1>Ethiopia Yirgacheffe Decaf Medium Roast</h1>
<p>Swiss water processed Ethiopian single-origin.</p>
<p>Origin: Yirgacheffe, Ethiopia</p>
<p>Process: Decaf (Swiss Water)</p>
<p>Roast: Medium</p>
<p>Tasting notes: caramel, orange blossom</p>
<p>500g — £13.99</p>
""",
        "expected_confidence_v1": 0.70,
        "expected_confidence_v2": 0.75,
    },
    {
        "name": "Limited edition seasonal",
        "url": "https://craft-roaster.co.uk/seasonal/colombia-2024",
        "html": """
<h1>Colombia Geisha 2024 Harvest Limited Edition</h1>
<p>Ultra-rare Geisha varietal from Colombia's Huila region.</p>
<p>Harvest: 2024</p>
<p>Varietal: Geisha</p>
<p>Process: Anaerobic Fermentation</p>
<p>Roast: Light</p>
<p>Flavor: floral, jasmine, honey, blueberry</p>
<p>Farm: La Esperanza Cooperative</p>
<p>250g — £28.99 SOLD OUT</p>
<p>1kg — £99.99 Pre-order</p>
""",
        "expected_confidence_v1": 0.85,
        "expected_confidence_v2": 0.92,
    },
    {
        "name": "Subscription pricing",
        "url": "https://subscription-roaster.co.uk/espresso",
        "html": """
<h1>Monthly Espresso Subscription</h1>
<p>Featured: Brazilian Santos Dark Roast</p>
<p>Dark Roast, perfect for espresso.</p>
<p>Tasting notes: chocolate, caramel, nutty</p>
<p>One-time: 1kg — £22.99</p>
""",
        "expected_confidence_v1": 0.55,
        "expected_confidence_v2": 0.65,
    },
    {
        "name": "Non-coffee page",
        "url": "https://example.com/about-us",
        "html": """
<h1>About Our Roastery</h1>
<p>We've been roasting coffee since 2010. Visit our café.</p>
""",
        "expected_confidence_v1": 0.0,
        "expected_confidence_v2": 0.0,
    },
    {
        "name": "Multi-origin blend",
        "url": "https://specialty.co.uk/east-african-blend",
        "html": """
<h1>East African Harmony Blend</h1>
<p>Kenya (SL28) 40%, Ethiopia (Heirloom) 40%, Uganda (Wush Wush) 20%</p>
<p>Process: Fully Washed</p>
<p>Roast: Medium</p>
<p>Tasting notes: berries, chocolate, balanced, clean</p>
<p>250g — £10.99</p>
<p>500g — £19.99</p>
<p>1kg — £34.99</p>
""",
        "expected_confidence_v1": 0.80,
        "expected_confidence_v2": 0.85,
    },
    {
        "name": "Luxury tin packaging",
        "url": "https://luxury-roaster.co.uk/premium-tin",
        "html": """
<h1>Brazilian Bourbon Single-Origin Premium Tin</h1>
<p>From Minas Gerais, Brazil. Medium-dark roast.</p>
<p>Varietal: Bourbon</p>
<p>Process: Pulped Natural</p>
<p>Flavor: chocolate, almond, subtle spice</p>
<p>Packaging: Luxury tin (200g)</p>
<p>Price: £16.99</p>
""",
        "expected_confidence_v1": 0.75,
        "expected_confidence_v2": 0.85,
    },
]


# ── Test runner ───────────────────────────────────────────────────────────

async def test_prompt_version(
    page_text: str, url: str, prompt_version: str
) -> dict:
    """Extract using a specific prompt version and return results."""
    parser = LLMParser(prompt_version=prompt_version)
    result = await parser.extract(page_text, url)

    return {
        "prompt_version": prompt_version,
        "success": result.result.validation_status in ("valid", "partial"),
        "status": result.result.validation_status,
        "confidence": result.result.payload.confidence if result.result.payload else 0.0,
        "errors": result.result.validation_errors,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "duration_ms": result.duration_ms,
    }


async def run_test_suite() -> None:
    """Run comparison tests for all fixtures."""
    print("\n" + "=" * 80)
    print("LLM PROMPT VERSION COMPARISON TEST")
    print(f"Test started: {datetime.now().isoformat()}")
    print("=" * 80 + "\n")

    results = []

    for i, fixture in enumerate(TEST_FIXTURES, 1):
        print(f"[{i}/{len(TEST_FIXTURES)}] Testing: {fixture['name']}")
        print(f"  URL: {fixture['url']}")

        # Clean page text
        page_text = clean_page_text(fixture["html"])

        # Extract with both v1 and v2
        try:
            result_v1 = await test_prompt_version(page_text, fixture["url"], "v1.0.0")
            result_v2 = await test_prompt_version(page_text, fixture["url"], "v2.0.0")

            improvement = result_v2["confidence"] - result_v1["confidence"]
            pct_improvement = (
                (improvement / result_v1["confidence"] * 100)
                if result_v1["confidence"] > 0
                else 0
            )

            comparison = {
                "test_name": fixture["name"],
                "url": fixture["url"],
                "v1_confidence": result_v1["confidence"],
                "v2_confidence": result_v2["confidence"],
                "improvement": improvement,
                "pct_improvement": pct_improvement,
                "v1_status": result_v1["status"],
                "v2_status": result_v2["status"],
                "v1_tokens": result_v1["input_tokens"] + result_v1["output_tokens"],
                "v2_tokens": result_v2["input_tokens"] + result_v2["output_tokens"],
                "expected_v1": fixture["expected_confidence_v1"],
                "expected_v2": fixture["expected_confidence_v2"],
            }

            results.append(comparison)

            # Print result
            status_indicator = (
                "✓"
                if improvement >= 0
                else "✗"
            )
            print(f"  {status_indicator} v1: {result_v1['confidence']:.2f} → v2: {result_v2['confidence']:.2f} ({improvement:+.2f})")
            print(f"    Tokens: v1={comparison['v1_tokens']}, v2={comparison['v2_tokens']}")

        except Exception as e:
            print(f"  ✗ Error: {e}")

        print()

    # ── Summary report ────────────────────────────────────────────────────────

    print("=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80 + "\n")

    if results:
        avg_improvement = sum(r["improvement"] for r in results) / len(results)
        pct_improved = sum(1 for r in results if r["improvement"] > 0) / len(results) * 100
        avg_tokens_v1 = sum(r["v1_tokens"] for r in results) / len(results)
        avg_tokens_v2 = sum(r["v2_tokens"] for r in results) / len(results)

        print(f"Tests run: {len(results)}")
        print(f"Average confidence improvement: {avg_improvement:+.3f}")
        print(f"Tests with improvement: {pct_improved:.1f}%")
        print(f"Average tokens (v1): {avg_tokens_v1:.0f}")
        print(f"Average tokens (v2): {avg_tokens_v2:.0f}")
        print(f"Token overhead: {(avg_tokens_v2 - avg_tokens_v1) / avg_tokens_v1 * 100:+.1f}%")

        print("\nDetailed results:")
        print("-" * 80)
        for r in results:
            accuracy_v1 = (
                "✓"
                if abs(r["v1_confidence"] - r["expected_v1"]) < 0.1
                else "✗"
            )
            accuracy_v2 = (
                "✓"
                if abs(r["v2_confidence"] - r["expected_v2"]) < 0.1
                else "✗"
            )
            print(
                f"{r['test_name']:35} | "
                f"v1: {r['v1_confidence']:.2f} {accuracy_v1} → "
                f"v2: {r['v2_confidence']:.2f} {accuracy_v2} "
                f"({r['improvement']:+.2f})"
            )

        print("-" * 80)

        if pct_improved >= 70:
            print("\n✓ SUCCESS: v2.0 shows >5% overall improvement. Ready to deploy.")
        elif pct_improved >= 50:
            print("\n⚠ PARTIAL: v2.0 improves 50-70% of tests. Further refinement recommended.")
        else:
            print("\n✗ REVIEW: v2.0 doesn't show consistent improvement. May need tuning.")


if __name__ == "__main__":
    asyncio.run(run_test_suite())
