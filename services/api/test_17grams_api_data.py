#!/usr/bin/env python3
"""
Test 17grams product data loading - investigate API calls and JS execution.

17grams uses a SPA that loads product data via:
1. Initial page load (just shell/framework)
2. API calls for product data (likely via fetch/XHR)
3. JavaScript execution to render DOM

We need to capture the API response or wait for the DOM to be populated.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def test_17grams_data_loading():
    """Investigate how 17grams loads product data."""

    url = "https://www.17grams.co.uk/products/filter-coffee"

    print("=" * 90)
    print("17GRAMS PRODUCT DATA INVESTIGATION")
    print("=" * 90)
    print(f"\nURL: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            extra_http_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        page = await context.new_page()

        # Track network requests
        api_requests = []
        api_responses = []

        def handle_response(response):
            """Capture API responses."""
            if "api" in response.url or "product" in response.url.lower():
                api_responses.append({
                    "url": response.url,
                    "status": response.status,
                    "type": response.request.resource_type,
                })
                print(f"  📡 API Response: {response.url[:80]} ({response.status})")

        page.on("response", handle_response)

        try:
            print("1️⃣  Loading page with Playwright...")
            response = await page.goto(url, timeout=30000, wait_until="networkidle")
            print(f"✅ Page loaded: {response.status if response else 'unknown'}")

            # Get initial content
            content1 = await page.content()
            print(f"✅ Initial HTML: {len(content1)} bytes")

            # Wait for potential data loading
            print("\n2️⃣  Waiting for product data to load...")
            await asyncio.sleep(2)

            # Check if product title appeared
            try:
                title = await page.evaluate("() => document.title")
                print(f"  Page title: {title}")
            except:
                pass

            # Try to find product name in DOM
            print("\n3️⃣  Searching for product content in DOM...")
            try:
                # Look for common product name patterns
                selectors = [
                    "h1",
                    "[class*=product]",
                    "[class*=title]",
                    ".ProductTitle",
                    "[data-test*=title]",
                ]

                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            text = await elements[0].text_content()
                            if text and len(text.strip()) > 2:
                                print(f"  ✅ Found via '{selector}': {text[:60]}")
                                break
                    except:
                        pass

            except Exception as e:
                print(f"  Error searching DOM: {e}")

            # Try to access JavaScript window object for product data
            print("\n4️⃣  Checking JavaScript variables...")
            try:
                # Check common data stores
                window_data = await page.evaluate("""
                    () => {
                        const checks = {};
                        if (typeof window.__data !== 'undefined') checks.window__data = true;
                        if (typeof window.__INITIAL_STATE__ !== 'undefined') checks.initialState = true;
                        if (typeof window.shopData !== 'undefined') checks.shopData = true;
                        if (typeof window.productData !== 'undefined') checks.productData = true;
                        return checks;
                    }
                """)

                if any(window_data.values()):
                    print(f"  ✅ Found data in: {[k for k,v in window_data.items() if v]}")
                else:
                    print("  ❌ No standard data objects found")

            except Exception as e:
                print(f"  Error checking variables: {e}")

            # Get final content
            content_final = await page.content()
            print(f"\n5️⃣  Final HTML content: {len(content_final)} bytes")

            # Check for product-related content
            indicators = {
                "Filter": "filter" in content_final.lower(),
                "Coffee": "coffee" in content_final.lower(),
                "Price": "£" in content_final or "$" in content_final,
                "Product": "product" in content_final.lower(),
                "omnisend": "omnisend" in content_final.lower(),
            }

            print(f"\n  Content indicators:")
            for indicator, found in indicators.items():
                status = "✅" if found else "❌"
                print(f"    {status} {indicator}: {found}")

            # Check network requests
            print(f"\n6️⃣  Network activity:")
            print(f"  API responses captured: {len(api_responses)}")
            if api_responses:
                for resp in api_responses[:5]:
                    print(f"    - {resp['url'][:70]} ({resp['status']})")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await page.close()
            await context.close()
            await browser.close()

    print("\n" + "=" * 90)
    print("ANALYSIS & RECOMMENDATIONS")
    print("=" * 90)
    print("""
The 17grams website uses a sophisticated SPA that:
1. Loads minimal HTML shell initially (6083 bytes)
2. Uses JavaScript to populate product data via API calls
3. Renders product content dynamically in the DOM

Current issues:
- Initial HTML has no product content
- Static httpx requests get blocked (0 bytes)
- Browser rendering works but data still loads asynchronously

Possible solutions:
1. Wait for specific DOM elements to appear (e.g., wait for h1 with product name)
2. Intercept network responses and extract JSON from API
3. Use Playwright's waitForSelector with longer timeout
4. Enable JavaScript evaluation to access internal state

Recommendation: Implement wait-for-element strategy before extracting.
""")


if __name__ == "__main__":
    asyncio.run(test_17grams_data_loading())
