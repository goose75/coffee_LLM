#!/usr/bin/env python3
"""Wait for 17Grams page to fully load with product content."""

import asyncio
from playwright.async_api import async_playwright


async def test_wait_for_content():
    """Load page and wait for actual product content to appear."""
    url = "https://www.17grams.co.uk/products/filter-coffee"

    print(f"Loading: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navigate with networkidle to wait for all network activity
            print("Navigating to page...")
            await page.goto(url, timeout=30000, wait_until="networkidle")

            # Now wait for product content to appear
            # Look for common product page elements
            selectors_to_try = [
                "h1",  # Product title
                "[class*=product]",  # Product container
                "[class*=title]",  # Product title
                ".product-title",
                ".ProductTitle",
                "price",  # Price element
                "[class*=price]",
                "[data-testid*=product]",
            ]

            for selector in selectors_to_try:
                try:
                    print(f"Looking for: {selector}")
                    await page.wait_for_selector(selector, timeout=5000)
                    text = await page.locator(selector).first.text_content()
                    if text and len(text.strip()) > 0:
                        print(f"  ✅ Found: {text[:100]}")
                        break
                except:
                    pass

            # Wait for page to be interactive
            print("Waiting for page to be interactive...")
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Get final content
            content = await page.content()
            print(f"Got {len(content)} bytes of HTML")

            # Check for product-related content
            if "Filter" in content or "filter" in content.lower():
                print("✅ Found 'filter' in content")
            if "Coffee" in content or "coffee" in content.lower():
                print("✅ Found 'coffee' in content")
            if "price" in content.lower():
                print("✅ Found 'price' in content")
            if "£" in content:
                print("✅ Found '£' currency in content")

            # Check for omnisend
            if "omnisend" in content.lower():
                print("✅ Found omnisend in content")
            else:
                print("❌ omnisend NOT in content")

            # Try to get the title using JavaScript
            print("\nGetting page title via JavaScript...")
            try:
                title = await page.evaluate("() => document.title")
                print(f"  Page title: {title}")

                # Try to find product name in page
                product_name = await page.evaluate("""
                    () => {
                        // Try various selectors for product name
                        const h1 = document.querySelector('h1');
                        if (h1) return h1.textContent;
                        const title = document.querySelector('[class*=title]');
                        if (title) return title.textContent;
                        return null;
                    }
                """)
                if product_name:
                    print(f"  Product name: {product_name[:100]}")
            except Exception as e:
                print(f"  Error getting title: {e}")

            # Save content
            with open("/tmp/17grams_full.html", "w") as f:
                f.write(content)
            print(f"\nSaved full page to /tmp/17grams_full.html")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_wait_for_content())
