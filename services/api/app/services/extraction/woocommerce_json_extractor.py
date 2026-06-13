"""
WooCommerce JSON Extractor - Extract from embedded omnisend_product JSON.

17 Grams uses omnisend for analytics, embedding product data as JSON in the page.
This extractor extracts from omnisend_product which contains accurate price/variant data,
bypassing JavaScript rendering issues.

Key insight: prices are in embedded JSON (price:1200 = £12.00) before JavaScript renders.
"""

from __future__ import annotations

import json
import logging
import re

from app.services.extraction.payload import ExtractionPayload, ExtractionResult, PriceVariantPayload
from app.services.extraction.text_utils import (
    extract_flavour_notes,
    extract_origin_country,
    extract_process,
    extract_roast_level,
    extract_varietal,
)

log = logging.getLogger(__name__)


def extract_woocommerce_coffee_data(html: bytes, url: str) -> ExtractionPayload | None:
    """
    Extract coffee product data from WooCommerce page with omnisend_product JSON.

    The omnisend_product JS object contains:
    {
      "title": "Coffee Name",
      "variants": {
        "3581": {"price": 1200, "customFields": {"attribute_weight-grind": "250g / Whole Beans"}}
      }
    }
    """
    try:
        html_text = html.decode('utf-8', errors='ignore')
    except Exception:
        return None

    # Find omnisend_product = { and extract using brace matching (handles nested objects)
    omnisend_start = html_text.find('omnisend_product')
    if omnisend_start < 0:
        log.debug("No omnisend_product found in page")
        return None

    # Find opening brace
    brace_start = html_text.find('{', omnisend_start)
    if brace_start < 0:
        log.debug("No opening brace found for omnisend_product")
        return None

    # Count braces to find matching closing brace
    brace_count = 0
    brace_end = brace_start
    for i in range(brace_start, len(html_text)):
        if html_text[i] == '{':
            brace_count += 1
        elif html_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                brace_end = i + 1
                break

    if brace_end <= brace_start:
        log.debug("Could not find matching closing brace for omnisend_product")
        return None

    json_str = html_text[brace_start:brace_end]

    try:
        product_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        log.debug(f"Failed to parse omnisend_product JSON: {e}")
        return None

    # Extract title
    title = product_data.get('title', '')
    if not title:
        return None

    # Clean title
    title = title.replace(' - 17 Grams', '').replace(' - Coffee', '').strip()

    # Extract description (for metadata)
    description = product_data.get('description', '')

    # Extract product attributes from description
    origin_country = extract_origin_country(description) or "United Kingdom"
    process = extract_process(description)
    roast_level = extract_roast_level(description)
    varietal = extract_varietal(description)
    flavour_notes = extract_flavour_notes(description)

    # Extract price variants from variants object
    price_variants = []
    variants = product_data.get('variants', {})

    seen_variants = set()

    for variant_id, variant_data in variants.items():
        price_pence = variant_data.get('price', 0)

        # Skip duplicates and invalid prices
        if price_pence == 0 or price_pence < 100:  # Min £1
            continue

        price_gbp = price_pence / 100.0

        # Extract weight and grind from customFields
        custom_fields = variant_data.get('customFields', {})
        weight_grind = custom_fields.get('attribute_weight-grind', '250g / Whole Beans')

        # Parse weight
        weight_g = 250
        if '1kg' in weight_grind or '1000g' in weight_grind:
            weight_g = 1000
        elif '500g' in weight_grind:
            weight_g = 500
        elif '250g' in weight_grind:
            weight_g = 250

        # Parse grind type
        grind_type = "Whole Beans"
        if "Espresso" in weight_grind:
            grind_type = "Espresso"
        elif "Filter" in weight_grind:
            grind_type = "Filter"
        elif "French Press" in weight_grind:
            grind_type = "French Press"

        # Create unique key to avoid duplicates
        variant_key = f"{weight_g}_{grind_type}"
        if variant_key in seen_variants:
            continue
        seen_variants.add(variant_key)

        price_variants.append(
            PriceVariantPayload(
                weight_g=weight_g,
                grind_type=grind_type,
                price_gbp=price_gbp,
                currency="GBP",
                availability="in_stock"
            )
        )

    # If we found no valid price variants, return None
    if not price_variants:
        log.debug(f"No valid price variants found for {title}")
        return None

    log.info(f"Extracted {len(price_variants)} variants for {title} from omnisend_product JSON")

    # Build payload
    payload = ExtractionPayload(
        coffee_name=title,
        roaster_name="17 Grams",
        origin_country=origin_country,
        process=process,
        roast_level=roast_level,
        varietal=varietal or ["Unknown"],
        flavour_notes=flavour_notes,
        price_variants=price_variants,
        confidence=0.88,  # Very high confidence for JSON-extracted data
        validation_status="valid",
        source_url=url,
    )

    return payload
