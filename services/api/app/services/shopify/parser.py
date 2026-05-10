"""
Shopify variant option parser.

Converts raw Shopify product/variant data into structured field values.
All parsing is regex-based and deterministic — no LLM involved at this stage.

Shopify variants expose options as:
  option1: "250g"         → weight_g = 250
  option2: "Whole Bean"   → grind_type = GrindType.whole_bean
  option3: "1"            → pack_count = 1 (sometimes used for subscription)

The variant title is a concatenation of all option values, e.g.:
  "250g / Whole Bean" or "1kg / Espresso / Decaf"

This module intentionally stays close to the raw data. Normalisation of
freetext labels (e.g. "Cafetière" → cafetiere) happens via the
NormalisationMapping table in a later pass. Here we only do confident,
regex-backed conversions that are virtually certain to be correct.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from app.models.enums import AvailabilityStatus, GrindType

# ── Weight parsing ────────────────────────────────────────────────────────────
# Matches: "250g", "250 g", "1kg", "1 kg", "0.5kg", "500G"
_WEIGHT_G_RE = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.IGNORECASE)

# ── Grind type keyword mapping ────────────────────────────────────────────────
# Ordered from most specific to least specific to avoid false matches.
_GRIND_KEYWORDS: list[tuple[re.Pattern, GrindType]] = [
    (re.compile(r"\bwhole[\s\-]?bean\b", re.I), GrindType.whole_bean),
    (re.compile(r"\bbeans?\b", re.I), GrindType.whole_bean),
    (re.compile(r"\bunground\b", re.I), GrindType.whole_bean),
    (re.compile(r"\bpour[\s\-]?over\b", re.I), GrindType.pour_over),
    (re.compile(r"\bv60\b", re.I), GrindType.pour_over),
    (re.compile(r"\baeropress\b", re.I), GrindType.aeropress),
    (re.compile(r"\bcafeti[eè]re\b", re.I), GrindType.cafetiere),
    (re.compile(r"\bfrench[\s\-]?press\b", re.I), GrindType.cafetiere),
    (re.compile(r"\bplunger\b", re.I), GrindType.cafetiere),
    (re.compile(r"\bmoka[\s\-]?pot\b", re.I), GrindType.moka),
    (re.compile(r"\bstovetop\b", re.I), GrindType.moka),
    (re.compile(r"\bomni[\s\-]?grind\b", re.I), GrindType.omni),
    (re.compile(r"\bomni\b", re.I), GrindType.omni),
    (re.compile(r"\bfilter\b", re.I), GrindType.filter),
    (re.compile(r"\bdrip\b", re.I), GrindType.filter),
    (re.compile(r"\bespresso\b", re.I), GrindType.espresso),
    (re.compile(r"\bfine[\s\-]?grind\b", re.I), GrindType.espresso),
]

# ── Pack count parsing ────────────────────────────────────────────────────────
_PACK_RE = re.compile(r"\b(\d+)\s*(?:pack|bag|x\s*\d+)\b", re.I)


class ParsedVariant(NamedTuple):
    """Structured result of parsing one Shopify variant."""
    weight_g: int | None
    grind_type: GrindType
    pack_count: int | None
    price_gbp: Decimal
    price_per_100g_gbp: Decimal | None
    availability_status: AvailabilityStatus
    seller_variant_id: str
    sku: str | None
    variant_title_raw: str
    currency_code: str


def parse_weight(text: str) -> int | None:
    """
    Extract weight in grams from a text string.
    Returns None if no weight pattern is found.

    Examples:
      "250g"        → 250
      "1kg"         → 1000
      "0.5 kg"      → 500
      "Whole Bean"  → None
    """
    # Try grams first (more specific)
    m = _WEIGHT_G_RE.search(text)
    if m:
        return int(float(m.group(1)))

    # Try kilograms
    m = _WEIGHT_KG_RE.search(text)
    if m:
        return int(float(m.group(1)) * 1000)

    return None


def parse_grind(text: str) -> GrindType:
    """
    Map a text string to a GrindType enum value.
    Returns GrindType.unknown if no pattern matches.
    """
    for pattern, grind in _GRIND_KEYWORDS:
        if pattern.search(text):
            return grind
    return GrindType.unknown


def parse_pack_count(text: str) -> int | None:
    """Extract pack count if present. Returns None if not found."""
    m = _PACK_RE.search(text)
    return int(m.group(1)) if m else None


def parse_price(price_str: str | None) -> Decimal:
    """
    Parse a Shopify price string to Decimal.
    Shopify stores prices as strings like "12.50".
    Returns Decimal("0.00") on parse failure.
    """
    if not price_str:
        return Decimal("0.00")
    try:
        return Decimal(str(price_str)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def compute_price_per_100g(price_gbp: Decimal, weight_g: int | None) -> Decimal | None:
    """Compute normalised price per 100g. Returns None if weight is unknown."""
    if weight_g is None or weight_g <= 0:
        return None
    try:
        return (price_gbp / Decimal(weight_g) * 100).quantize(Decimal("0.0001"))
    except Exception:
        return None


def parse_availability(variant: dict) -> AvailabilityStatus:
    """
    Map Shopify availability fields to AvailabilityStatus.

    Shopify fields used:
      available:            bool (True if any inventory available)
      inventory_quantity:   int (may be None if not tracked)
      inventory_policy:     "deny" | "continue" (continue = allow oversell)
    """
    available = variant.get("available", True)
    inventory_policy = variant.get("inventory_policy", "deny")

    if available:
        return AvailabilityStatus.in_stock
    # "continue" policy means the store allows orders even when sold out
    if inventory_policy == "continue":
        return AvailabilityStatus.preorder
    return AvailabilityStatus.out_of_stock


def parse_variant(variant: dict, product_title: str = "") -> ParsedVariant:
    """
    Parse a single Shopify variant dict into a ParsedVariant.

    Strategy: search all option values and the variant title for
    weight and grind signals. The variant title is the concatenation
    of all options and is the most reliable single source of truth.
    """
    # Build a combined search text from all option values + title
    options = [
        variant.get("option1") or "",
        variant.get("option2") or "",
        variant.get("option3") or "",
    ]
    variant_title_raw = variant.get("title", " / ".join(o for o in options if o))
    combined = f"{variant_title_raw} {' '.join(options)}"

    weight_g = None
    for text in [*options, variant_title_raw, product_title]:
        if text:
            weight_g = parse_weight(text)
            if weight_g is not None:
                break

    grind_type = GrindType.unknown
    for text in [*options, variant_title_raw]:
        if text:
            grind_type = parse_grind(text)
            if grind_type != GrindType.unknown:
                break
    # Fallback: if weight found but no grind, check if product title implies whole bean
    if grind_type == GrindType.unknown and weight_g is not None:
        if parse_grind(product_title) != GrindType.unknown:
            grind_type = parse_grind(product_title)

    pack_count = parse_pack_count(combined)
    price_gbp = parse_price(variant.get("price"))
    price_per_100g = compute_price_per_100g(price_gbp, weight_g)
    availability = parse_availability(variant)

    return ParsedVariant(
        weight_g=weight_g,
        grind_type=grind_type,
        pack_count=pack_count,
        price_gbp=price_gbp,
        price_per_100g_gbp=price_per_100g,
        availability_status=availability,
        seller_variant_id=str(variant.get("id", "")),
        sku=variant.get("sku") or None,
        variant_title_raw=variant_title_raw,
        currency_code="GBP",
    )


# ── Title-based field extraction ─────────────────────────────────────────────
# Extracts structured fields from the product title when tags don't have them.

_TITLE_ORIGINS = {
    "costa rica": "Costa Rica", "el salvador": "El Salvador",
    "papua new guinea": "Papua New Guinea",
    "ethiopian": "Ethiopia", "ethiopia": "Ethiopia",
    "kenyan": "Kenya", "kenya": "Kenya",
    "colombian": "Colombia", "colombia": "Colombia",
    "brazilian": "Brazil", "brazil": "Brazil",
    "guatemalan": "Guatemala", "guatemala": "Guatemala",
    "rwandan": "Rwanda", "rwanda": "Rwanda",
    "panamanian": "Panama", "panama": "Panama",
    "honduran": "Honduras", "honduras": "Honduras",
    "peruvian": "Peru", "peru": "Peru",
    "burundian": "Burundi", "burundi": "Burundi",
    "ugandan": "Uganda", "uganda": "Uganda",
    "indonesian": "Indonesia", "indonesia": "Indonesia",
    "yemeni": "Yemen", "yemen": "Yemen",
    "indian": "India", "india": "India",
    "mexican": "Mexico", "mexico": "Mexico",
    "nicaraguan": "Nicaragua", "nicaragua": "Nicaragua",
    "tanzanian": "Tanzania", "tanzania": "Tanzania",
    "bolivian": "Bolivia", "bolivia": "Bolivia",
    "ecuadorian": "Ecuador", "ecuador": "Ecuador",
    "thailand": "Thailand", "thai": "Thailand",
}

_TITLE_PROCESSES = {
    "pulped natural": "natural",
    "wet process": "washed", "wet-process": "washed",
    "dry process": "natural", "dry-process": "natural",
    "carbonic maceration": "anaerobic",
    "anaerobic": "anaerobic",
    "washed": "washed",
    "natural": "natural",
    "honey": "honey",
}

_TITLE_ROASTS = {
    "lightly roasted": "light", "light roast": "light",
    "medium roast": "medium", "medium-roast": "medium",
    "dark roast": "dark", "darkly roasted": "dark",
    "espresso roast": "dark",
}

_TITLE_VARIETALS = [
    "pink bourbon", "sl28", "sl34", "pacamara", "geisha", "gesha",
    "typica", "bourbon", "caturra", "catuai", "sidra", "mejorado",
    "tabi", "java", "s795", "heirloom", "arabica", "robusta",
]


def _extract_fields_from_title(title: str) -> dict:
    """Extract origin, process, roast and varietal from product title."""
    t = title.lower()
    origin = next(
        (v for k, v in sorted(_TITLE_ORIGINS.items(), key=lambda x: -len(x[0])) if k in t),
        None
    )
    process = next(
        (v for k, v in sorted(_TITLE_PROCESSES.items(), key=lambda x: -len(x[0])) if k in t),
        None
    )
    roast = next(
        (v for k, v in sorted(_TITLE_ROASTS.items(), key=lambda x: -len(x[0])) if k in t),
        None
    )
    varietal = next(
        (v for v in sorted(_TITLE_VARIETALS, key=len, reverse=True) if v in t),
        None
    )
    return {"origin": origin, "process": process, "roast": roast, "varietal": varietal}


def parse_product_fields(product: dict) -> dict:
    """
    Extract listing-level fields from a Shopify product dict.

    Returns a flat dict of raw label values for storage in bean_listings.
    These are always raw text — normalisation happens later.

    Two-pass extraction:
      1. Tags — most reliable when roasters tag consistently
      2. Title — extracts origin/process/varietal from product name
    """
    title = product.get("title", "") or ""

    # Handle tags as list or comma-separated string
    raw_tags = product.get("tags", "")
    if isinstance(raw_tags, list):
        tags = [t.strip() for t in raw_tags if t.strip()]
    else:
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    # Pass 1: extract from tags
    roast_label = None
    process_label = None
    origin_label = None
    varietal_label = None

    for tag in tags:
        tag_lower = tag.lower()
        if not roast_label and any(k in tag_lower for k in ["light", "medium", "dark", "roast"]):
            roast_label = tag
        if not process_label and any(k in tag_lower for k in [
            "washed", "natural", "honey", "anaerobic", "process", "pulped"
        ]):
            process_label = tag
        if not origin_label and any(k in tag_lower for k in _TITLE_ORIGINS) and ":" not in tag and len(tag.split()) <= 3:
            import re
            origin_label = re.sub(r"^(swatch_|origin_|country_|tag_|caption:.*?-\s*)", "", tag, flags=re.I).strip()
            origin_label = re.sub(r"\s+coffee$", "", origin_label, flags=re.I).strip().title() or tag
        if not varietal_label and any(v in tag_lower for v in _TITLE_VARIETALS):
            varietal_label = tag

    # Pass 2: extract from title where tags didn't provide a value
    title_fields = _extract_fields_from_title(title)
    if not origin_label and title_fields["origin"]:
        origin_label = title_fields["origin"]
    if not process_label and title_fields["process"]:
        process_label = title_fields["process"]
    if not roast_label and title_fields["roast"]:
        roast_label = title_fields["roast"]
    if not varietal_label and title_fields["varietal"]:
        varietal_label = title_fields["varietal"]

    body_html = product.get("body_html", "") or ""

    # Pass 3: mine body_html for anything tags + title didn't give us.
    # This is the biggest unlock — most roasters write full descriptions
    # ("Single origin Yirgacheffe, washed, Heirloom varietal…") and never
    # tag products structurally. Without this pass, those fields are blank
    # in the DB and the matcher has nothing to compare on.
    if body_html and (not origin_label or not process_label or not varietal_label):
        try:
            from app.services.extraction.text_utils import (
                clean_html, extract_origin_country, extract_process, extract_varietal,
            )
            description = clean_html(body_html)
            if not origin_label:
                v = extract_origin_country(description)
                if v:
                    origin_label = v
            if not process_label:
                v = extract_process(description)
                if v:
                    process_label = v
            if not varietal_label:
                varietals = extract_varietal(description)
                if varietals:
                    # Store the first detected varietal as the raw label;
                    # the canonical merge step picks up additional ones.
                    varietal_label = ", ".join(varietals[:3])
        except Exception:
            # Defensive: never fail ingestion because the description couldn't be parsed.
            pass

    return {
        "raw_title": title[:500],
        "raw_subtitle": None,
        "raw_description": body_html[:5000] if body_html else None,
        "roast_label_raw": roast_label,
        "process_label_raw": process_label,
        "origin_label_raw": origin_label,
        "varietal_label_raw": varietal_label,
        "seller_product_id": str(product.get("id", "")),
        "product_url": product.get("url"),
        "product_handle": product.get("handle", ""),
        "tags": tags,
    }
