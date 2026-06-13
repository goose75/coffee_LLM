#!/usr/bin/env python3
"""Direct test of Playwright extraction on 17Grams product page."""

import asyncio
from playwright.async_api import async_playwright


async def test_17grams_extraction():
    """Test Playwright can render 17Grams page and extract omnisend_product."""
    url = "https://www.17grams.co.uk/products/filter-coffee"

    print(f"Testing Playwright on: {url}")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        print(f"✅ Browser launched")

        context = await browser.new_context(
            # Add headers to look more like a real browser
            extra_http_headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
        page = await context.new_page()
        print(f"✅ Page created")

        try:
            # Navigate to page with timeout
            response = await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            print(f"✅ Page loaded (status: {response.status if response else 'unknown'})")

            # Get page content
            content = await page.content()
            print(f"✅ Got page content ({len(content)} bytes)")

            # Check if omnisend_product is in the page
            if "omnisend_product" in content:
                print(f"✅ Found omnisend_product in rendered page!")

                # Extract just the omnisend_product object
                import re
                match = re.search(r'omnisend_product\s*=\s*(\{[^}]+\})', content)
                if match:
                    print(f"   Raw omnisend_product: {match.group(1)[:200]}...")
            else:
                print(f"⚠️  omnisend_product NOT found in rendered page")

            # Check for product titles
            if "Filter" in content or "Coffee" in content.upper():
                print(f"✅ Found product-related keywords in page")

            # Test extraction with BrowserExtractor
            print("\nTesting with BrowserExtractor...")
            from app.services.extraction.browser_extractor import BrowserExtractor

            # Pass the rendered content as HTML bytes
            html_bytes = content.encode('utf-8')
            extractor = BrowserExtractor()
            result = await extractor._extract_async(html_bytes, url)

            if result.validation_status == "valid":
                print(f"✅ Browser extraction succeeded!")
                print(f"   Coffee name: {result.payload.coffee_name}")
                print(f"   Variants: {len(result.payload.price_variants)}")
                print(f"   Confidence: {result.payload.confidence:.2f}")
            else:
                print(f"⚠️  Extraction result: {result.validation_status}")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await context.close()
            await browser.close()
            print(f"✅ Browser closed")


if __name__ == "__main__":
    asyncio.run(test_17grams_extraction())
