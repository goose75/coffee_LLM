#!/usr/bin/env python3
"""
Quick test: Can we extract product containers from 17grams listing page?
Direct test without importing the full app.
"""
import urllib.request

# Copy the extractor code inline to avoid dependencies
try:
    from selectolax.parser import HTMLParser as SelectolaxParser
    _SELECTOLAX_AVAILABLE = True
except ImportError:
    _SELECTOLAX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False


PRODUCT_CONTAINER_SELECTORS = [
    ".product",
    ".product-item",
    ".woocommerce-loop-product",
    ".woocommerce-product-item",
    "[data-product-id]",
    ".product__wrapper",
    "[data-product]",
    ".item",
    ".listing-item",
    ".gallery-item",
    ".catalog-item",
    ".coffee-item",
    ".coffee-product",
    "[class*='product']",
]


def test_17grams():
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
        
        # Try to detect product containers
        print("\nTesting product container detection...")
        containers = []
        
        if _SELECTOLAX_AVAILABLE:
            print("  Using selectolax parser...")
            tree = SelectolaxParser(html_str)
            
            for selector in PRODUCT_CONTAINER_SELECTORS:
                try:
                    nodes = tree.css(selector)
                    if nodes and len(nodes) > 1:
                        print(f"  ✓ Found {len(nodes)} containers with selector: {selector}")
                        containers = nodes
                        break
                except Exception as e:
                    pass
        
        elif _BS4_AVAILABLE:
            print("  Using BeautifulSoup parser...")
            soup = BeautifulSoup(html_str, "html.parser")
            
            for selector in PRODUCT_CONTAINER_SELECTORS:
                try:
                    elements = soup.select(selector)
                    if elements and len(elements) > 1:
                        print(f"  ✓ Found {len(elements)} containers with selector: {selector}")
                        containers = elements
                        break
                except Exception as e:
                    pass
        
        else:
            print("  ✗ No HTML parser available")
            return
        
        # Summary
        if containers:
            print(f"\n✓ SUCCESS: Found {len(containers)} product containers!")
            if _SELECTOLAX_AVAILABLE:
                first_size = len(containers[0].html)
            else:
                first_size = len(str(containers[0]))
            print(f"  First container size: {first_size} bytes")
        else:
            print(f"\n✗ FAILED: No product containers detected")
            print("  Selectors tried:", ", ".join(PRODUCT_CONTAINER_SELECTORS[:3]), "...")
            
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    test_17grams()
