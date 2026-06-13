#!/usr/bin/env python3
"""Test extraction pipeline with browser support for JavaScript pages."""

import asyncio
import sys
from app.services.extraction.woocommerce_json_extractor import extract_woocommerce_coffee_data
from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.browser_extractor import BrowserExtractor


async def test_extraction_chain():
    """Test full extraction chain: JSON → schema.org → HTML rules → Browser."""

    # Test URLs that should work with different methods
    test_cases = [
        {
            "url": "https://bradyscoffee.ie/products/bold-caramel",
            "name": "Brady's WooCommerce (HTML rules)",
            "expected_method": "html_rules",
        },
        {
            "url": "https://www.17grams.co.uk/products/filter-coffee",
            "name": "17Grams (Browser rendering needed)",
            "expected_method": "browser",
        },
    ]

    print("=" * 80)
    print("EXTRACTION PIPELINE TEST")
    print("=" * 80)

    for test_case in test_cases:
        print(f"\n📋 Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")

        try:
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(test_case["url"])
                html_bytes = response.content
                print(f"   ✅ Fetched page ({len(html_bytes)} bytes)")

            # Try JSON extraction first (WooCommerce)
            json_result = extract_woocommerce_coffee_data(html_bytes, test_case["url"])
            if json_result:
                print(f"   ✅ JSON extraction: {json_result.coffee_name} (confidence: {json_result.confidence:.2f})")
                continue

            # Try schema.org
            parser = SchemaOrgParser()
            schema_result = parser.extract(html_bytes, test_case["url"])
            if schema_result.validation_status in ("valid", "partial"):
                print(f"   ✅ Schema.org extraction: {schema_result.payload.coffee_name} (confidence: {schema_result.payload.confidence:.2f})")
                continue

            # Try HTML rules
            html_parser = HtmlRulesParser()
            html_result = html_parser.extract(html_bytes, test_case["url"])
            if html_result.validation_status in ("valid", "partial"):
                print(f"   ✅ HTML rules extraction: {html_result.payload.coffee_name} (confidence: {html_result.payload.confidence:.2f})")
                continue

            # Try browser extraction
            if "browser" in test_case["expected_method"].lower():
                print(f"   🔄 Attempting browser extraction...")
                browser_extractor = BrowserExtractor()
                browser_result = await browser_extractor._extract_async(html_bytes, test_case["url"])
                if browser_result.validation_status in ("valid", "partial"):
                    print(f"   ✅ Browser extraction: {browser_result.payload.coffee_name} (confidence: {browser_result.payload.confidence:.2f})")
                    continue
                else:
                    print(f"   ❌ Browser extraction failed: {browser_result.validation_status}")

            print(f"   ❌ No extraction method succeeded")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_extraction_chain())
