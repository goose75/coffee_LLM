#!/usr/bin/env python3
"""
Quick test: Can we extract product containers from 17grams listing page?
"""
import asyncio
import urllib.request
from pathlib import Path

# Add app to path
import sys
app_path = Path(__file__).parent / "services" / "api"
sys.path.insert(0, str(app_path))

from app.services.html.product_listing_extractor import ProductListingExtractor

async def test_17grams():
    """Fetch 17grams shop page and test listing extraction"""
    
    # Fetch the page
    print("Fetching https://17grams.co.uk/shop/...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    req = urllib.request.Request("https://17grams.co.uk/shop/", headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_bytes = response.read()
            html_str = html_bytes.decode('utf-8', errors='ignore')
        
        print(f"✓ Fetched {len(html_bytes)} bytes")
        
        # Test listing extractor
        extractor = ProductListingExtractor()
        
        print("\nTesting ProductListingExtractor...")
        is_listing = extractor.is_listing_page(html_str)
        print(f"  Is listing page: {is_listing}")
        
        if is_listing:
            containers = extractor.extract_product_containers(html_str)
            print(f"  ✓ Found {len(containers)} product containers!")
            
            # Show size of first container
            if containers:
                print(f"\n  First container size: {len(containers[0])} bytes")
                print(f"  First container preview:\n{containers[0][:500]}...")
        else:
            print("  ✗ Not detected as listing page")
            
            # Try manually with WooCommerce selectors
            print("\n  Trying manual selector detection...")
            if "class=\"product" in html_str or "woocommerce-loop-product" in html_str:
                print("  ✓ Found 'product' class in HTML")
            if "[data-product-id]" in html_str:
                print("  ✓ Found [data-product-id] in HTML")
                
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_17grams())
