"""
Content hashing for change detection.

A content hash is computed from the listing's semantically meaningful fields.
If the hash matches the stored hash, we skip re-extraction and only update
last_seen_at and append price_history.

The hash must be:
  - Stable: same input always produces same hash
  - Sensitive: changes to price, title, description, or availability trigger reprocessing
  - Insensitive to metadata changes (updated_at, Shopify internal IDs we don't use)

Strategy: serialise a sorted tuple of (field_name, str(value)) pairs to JSON,
then SHA-256 the UTF-8 bytes. Sorted keys guarantee dict ordering doesn't affect hash.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal


def _serialise_value(v) -> str:
    """Convert a value to a stable string representation."""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, list):
        return json.dumps(sorted(str(i) for i in v))
    if v is None:
        return ""
    return str(v)


def compute_listing_hash(
    title: str,
    description: str | None,
    variants: list[dict],
) -> str:
    """
    Compute a content hash for a bean_listing.

    The hash covers: title, description, and all variant prices + availability.
    Variant order is normalised by seller_variant_id to ensure stability.
    """
    # Normalise variants: sort by seller_variant_id, extract key fields only
    normalised_variants = sorted(
        [
            {
                "id": str(v.get("seller_variant_id", v.get("id", ""))),
                "price": _serialise_value(v.get("price_gbp", v.get("price", ""))),
                "avail": str(v.get("availability_status", v.get("available", ""))),
                "weight": str(v.get("weight_g", "")),
                "grind": str(v.get("grind_type", "")),
            }
            for v in variants
        ],
        key=lambda x: x["id"],
    )

    payload = {
        "title": (title or "").strip(),
        "description": (description or "")[:2000].strip(),  # Cap to avoid huge hashes
        "variants": normalised_variants,
    }

    serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def compute_product_hash(product: dict) -> str:
    """
    Compute a content hash directly from a raw Shopify product dict.
    Used during the fetch phase before variant parsing.
    """
    variants = [
        {
            "id": str(v.get("id", "")),
            "price": str(v.get("price", "")),
            "available": str(v.get("available", "")),
            "title": str(v.get("title", "")),
        }
        for v in sorted(product.get("variants", []), key=lambda v: str(v.get("id", "")))
    ]

    payload = {
        "title": (product.get("title", "") or "").strip(),
        "body_html": (product.get("body_html", "") or "")[:2000].strip(),
        "variants": variants,
    }

    serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()
