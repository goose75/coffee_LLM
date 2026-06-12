#!/usr/bin/env python3
"""
Diagnostic script to test WooCommerce parser on 17 Grams products.

Usage:
    python test_17grams_parser.py

This script:
1. Fetches a sample 17 Grams product page
2. Runs the WooCommerce parser on it
3. Shows extracted fields
4. Compares with other parsers
"""

import urllib.request
import urllib.error
import sys
import json
from pathlib import Path

# Add API services to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "api"))

def test_17grams_parser():
    """Test WooCommerce parser on actual 17 Grams product page."""

    # Sample 17 Grams URLs from the extraction plan
    test_urls = [
        "https://17grams.co.uk/product/hypnos-decaf/",
    ]

    print("=" * 80)
    print("17 GRAMS WOOCOMMERCE PARSER TEST")
    print("=" * 80)

    for url in test_urls:
        print(f"\n📍 Testing: {url}")
        print("-" * 80)

        try:
            # Fetch the page
            print("⏳ Fetching page...")
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html_bytes = response.read()
                print(f"✅ Fetched {len(html_bytes)} bytes")

            # Test each parser
            from app.services.extraction.schema_org_parser import SchemaOrgParser
            from app.services.extraction.woocommerce_parser import WooCommerceParser
            from app.services.extraction.html_parser import HtmlRulesParser

            parsers = [
                ("Schema.org", SchemaOrgParser()),
                ("WooCommerce", WooCommerceParser()),
                ("Generic HTML Rules", HtmlRulesParser()),
            ]

            results = {}
            for parser_name, parser in parsers:
                try:
                    result = parser.extract(html_bytes, url)
                    results[parser_name] = result
                    print(f"\n{parser_name} Parser:")
                    print(f"  Status: {result.validation_status}")
                    print(f"  Confidence: {result.payload.confidence:.2f}")
                    print(f"  Coffee Name: {result.payload.coffee_name}")
                    print(f"  Origin: {result.payload.origin_country} / {result.payload.origin_region}")
                    print(f"  Process: {result.payload.process}")
                    print(f"  Roast: {result.payload.roast_level}")
                    print(f"  Varietal: {result.payload.varietal}")
                    print(f"  Flavour Notes: {result.payload.flavour_notes}")
                    print(f"  Price Variants: {len(result.payload.price_variants)}")
                    if result.payload.price_variants:
                        for pv in result.payload.price_variants[:3]:
                            print(f"    - {pv.weight_g}g {pv.grind_type}: £{pv.price_gbp:.2f}")
                    print(f"  Brew Suitability: {result.payload.brew_suitability}")
                    if result.validation_errors:
                        print(f"  Errors: {result.validation_errors}")
                except Exception as exc:
                    print(f"\n{parser_name} Parser: ❌ ERROR")
                    print(f"  {exc}")

            # Highlight the best result
            print("\n" + "=" * 80)
            best_parser = max(results.items(), key=lambda x: x[1].payload.confidence)
            print(f"🏆 Best parser: {best_parser[0]} ({best_parser[1].payload.confidence:.2f})")
            print("=" * 80)

        except urllib.error.HTTPError as e:
            print(f"❌ HTTP Error: {e.code}")
        except urllib.error.URLError as e:
            print(f"❌ URL Error: {e.reason}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_17grams_parser()
