#!/usr/bin/env python3
"""Test extraction on Brady's Coffee which should work."""

import asyncio
from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.extraction.html_parser import HtmlRulesParser
import httpx


async def test_bradys():
    """Test extraction on Brady's WooCommerce site."""
    url = "https://bradyscoffee.ie/products/bold-caramel"

    print(f"Testing: {url}")
    print("=" * 80)

    try:
        # Fetch with httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=20)
            html_bytes = response.content
            print(f"✅ Fetched page: {len(html_bytes)} bytes")

        # Try schema.org
        print("\n1. Schema.org extraction:")
        schema_parser = SchemaOrgParser()
        schema_result = schema_parser.extract(html_bytes, url)
        print(f"   Status: {schema_result.validation_status}")
        if schema_result.validation_status in ("valid", "partial"):
            print(f"   Coffee: {schema_result.payload.coffee_name}")
            print(f"   Roaster: {schema_result.payload.roaster_name}")
            print(f"   Confidence: {schema_result.payload.confidence:.2f}")
            print(f"   Variants: {len(schema_result.payload.price_variants)}")

        # Try HTML rules
        print("\n2. HTML rules extraction:")
        html_parser = HtmlRulesParser()
        html_result = html_parser.extract(html_bytes, url)
        print(f"   Status: {html_result.validation_status}")
        if html_result.validation_status in ("valid", "partial"):
            print(f"   Coffee: {html_result.payload.coffee_name}")
            print(f"   Confidence: {html_result.payload.confidence:.2f}")
            print(f"   Variants: {len(html_result.payload.price_variants)}")

        # Try browser extraction
        print("\n3. Browser extraction (for comparison):")
        from app.services.extraction.browser_extractor import BrowserExtractor
        browser_extractor = BrowserExtractor()
        browser_result = await browser_extractor._extract_async(html_bytes, url)
        print(f"   Status: {browser_result.validation_status}")
        if browser_result.validation_status in ("valid", "partial"):
            print(f"   Coffee: {browser_result.payload.coffee_name}")
            print(f"   Confidence: {browser_result.payload.confidence:.2f}")

        print("\n✅ Extraction pipeline test complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_bradys())
