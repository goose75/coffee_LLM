#!/usr/bin/env python3
"""Detailed inspection of 17Grams page with Playwright."""

import asyncio
import json
from playwright.async_api import async_playwright


async def test_detailed():
    """Load page and inspect what's available."""
    url = "https://www.17grams.co.uk/products/filter-coffee"

    print(f"Loading: {url}")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Try different wait conditions
            print("\n1️⃣  Waiting for domcontentloaded...")
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            content1 = await page.content()
            print(f"   Got {len(content1)} bytes")
            print(f"   omnisend_product: {'YES' if 'omnisend_product' in content1 else 'NO'}")

            print("\n2️⃣  Waiting for load...")
            await page.goto(url, timeout=15000, wait_until="load")
            content2 = await page.content()
            print(f"   Got {len(content2)} bytes")
            print(f"   omnisend_product: {'YES' if 'omnisend_product' in content2 else 'NO'}")

            print("\n3️⃣  Waiting for networkidle...")
            await page.goto(url, timeout=15000, wait_until="networkidle")
            content3 = await page.content()
            print(f"   Got {len(content3)} bytes")
            print(f"   omnisend_product: {'YES' if 'omnisend_product' in content3 else 'NO'}")

            # Try to access JavaScript variables
            print("\n4️⃣  Checking JavaScript variables...")
            try:
                omnisend_data = await page.evaluate("() => typeof omnisend_product !== 'undefined' ? omnisend_product : null")
                if omnisend_data:
                    print(f"   ✅ omnisend_product found via JS: {json.dumps(omnisend_data)[:200]}...")
                else:
                    print(f"   ❌ omnisend_product is undefined")
            except Exception as e:
                print(f"   Error accessing omnisend_product: {e}")

            # Check for other data
            print("\n5️⃣  Looking for product data patterns...")
            checks = [
                ("window.__data", "window.__data"),
                ("window.__INITIAL_STATE__", "window.__INITIAL_STATE__"),
                ("JSON-LD schema", 'document.querySelector("script[type=\'application/ld+json\']")?.textContent'),
                ("data-price attribute", 'document.querySelector("[data-price]")?.getAttribute("data-price")'),
                ("Product title", 'document.querySelector("[class*=product]")?.innerText'),
            ]

            for name, code in checks:
                try:
                    result = await page.evaluate(f"() => {code}")
                    if result:
                        result_str = str(result)[:100] if not isinstance(result, str) else result[:100]
                        print(f"   ✅ {name}: {result_str}")
                except:
                    pass

            # Save page HTML for inspection
            final_content = await page.content()
            with open("/tmp/17grams_page.html", "w") as f:
                f.write(final_content)
            print(f"\n6️⃣  Saved full page HTML to /tmp/17grams_page.html ({len(final_content)} bytes)")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_detailed())
