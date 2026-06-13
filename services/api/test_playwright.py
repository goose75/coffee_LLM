#!/usr/bin/env python3
"""Quick test of Playwright browser extraction capability."""

import asyncio
import sys
from playwright.async_api import async_playwright


async def test_playwright():
    """Test if Playwright can launch browser and render a page."""
    try:
        async with async_playwright() as p:
            print("✅ Playwright imported successfully")

            # Try to launch chromium
            try:
                browser = await p.chromium.launch()
                print("✅ Chromium browser launched successfully")

                # Create a page and test rendering
                page = await browser.new_page()
                await page.goto("https://example.com", timeout=10000)
                title = await page.title()
                print(f"✅ Page rendering works (loaded: {title})")

                await browser.close()
                print("✅ Browser closed successfully")

                return True
            except Exception as e:
                print(f"❌ Browser launch failed: {e}")
                return False

    except Exception as e:
        print(f"❌ Playwright test failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_playwright())
    sys.exit(0 if success else 1)
