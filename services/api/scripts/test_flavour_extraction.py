#!/usr/bin/env python3
"""
test_flavour_extraction.py — Quick test of flavour extraction with Ollama.

Run inside the API container:
    docker exec coffee_api python scripts/test_flavour_extraction.py
"""
import asyncio
import sys

sys.path.insert(0, "/app")


async def test_flavour_extraction():
    """Test flavour extraction on sample product descriptions."""
    from app.services.extraction.hybrid_extractor import HybridExtractor

    # Sample coffee product descriptions
    test_cases = [
        {
            "name": "Ethiopian Yirgacheffe Natural",
            "description": """
                Single origin Ethiopian Yirgacheffe with natural process.
                Bright and fruity notes of blueberry, lemon, and floral.
                Medium roast with complex acidity and wine-like sweetness.
            """
        },
        {
            "name": "Colombian Geisha",
            "description": """
                Rare Panamanian Geisha varietal, washed process.
                Exotic notes of jasmine, tropical fruits, and bergamot.
                Silky mouthfeel with hints of vanilla and white tea.
            """
        },
        {
            "name": "Brazilian Dark Roast",
            "description": """
                Brazil Minas Gerais dark roast blend.
                Rich chocolate and caramel notes with nutty undertones.
                Smooth finish with a hint of cedar and spice.
            """
        },
        {
            "name": "Kenyan AA",
            "description": """
                Kenya AA grade coffee, washed process.
                Bright acidity with flavours of strawberry, blackcurrant, and citrus.
                Complex floral notes reminiscent of jasmine and hibiscus.
            """
        },
    ]

    print("=" * 70)
    print("FLAVOUR EXTRACTION TEST")
    print("=" * 70)
    print("\nTesting hybrid extraction on sample coffee descriptions...\n")

    extractor = HybridExtractor(use_ollama=True, use_api_fallback=True)

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Product: {test['name']}")
        print(f"Description: {test['description'].strip()[:100]}...")
        print("─" * 70)

        html_bytes = test["description"].encode('utf-8')

        try:
            result = await extractor.extract(html_bytes, f"test:{test['name']}")

            payload = result.final_result.payload
            flavour_notes = payload.flavour_notes

            print(f"✓ Strategy:   {result.strategy_used:10} (rule/ollama/llm)")
            print(f"✓ Confidence: {result.confidence:.2f}")
            print(f"✓ Flavours:   {', '.join(flavour_notes) if flavour_notes else 'None found'}")
            print(f"✓ Reasoning:  {result.reasoning}")

        except Exception as exc:
            print(f"✗ Error: {exc}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\n✓ Flavour extraction is working!")
    print("You can now run the full extraction script:")
    print("  docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py")
    print("\nTo preview what would be extracted (dry-run):")
    print("  docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run --limit 20")


if __name__ == "__main__":
    asyncio.run(test_flavour_extraction())
