#!/usr/bin/env python3
"""Test browser extraction on JavaScript-heavy coffee pages."""

import asyncio
import httpx
from app.services.extraction.browser_extractor import BrowserExtractor
from app.services.extraction.payload import ExtractionResult

# Test with a real JavaScript-heavy page
# 17Grams uses omnisend_product JavaScript to inject product data
TEST_URL = "https://www.17grams.co.uk/products/filter-coffee"


async def test_browser_extraction():
    """Test browser extraction on a JavaScript page."""
    print(f"Testing browser extraction on: {TEST_URL}")

    try:
        # Fetch the page content
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(TEST_URL)
            html_bytes = response.content
            print(f"✅ Fetched page ({len(html_bytes)} bytes)")

        # Try browser extraction
        extractor = BrowserExtractor()
        print("🔄 Extracting with browser renderer...")
        result = await extractor._extract_async(html_bytes, TEST_URL)

        if result.validation_status == "valid":
            print(f"✅ Browser extraction succeeded!")
            print(f"   Coffee name: {result.payload.coffee_name}")
            print(f"   Price variants: {len(result.payload.price_variants)}")
            print(f"   Confidence: {result.payload.confidence:.2f}")
            return True
        elif result.validation_status == "partial":
            print(f"⚠️  Partial extraction")
            print(f"   Coffee name: {result.payload.coffee_name}")
            print(f"   Confidence: {result.payload.confidence:.2f}")
            return True
        else:
            print(f"❌ Extraction failed: {result.validation_status}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_browser_extraction())
    exit(0 if success else 1)
