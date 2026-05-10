"""
Schema.org JSON-LD extraction parser.

Uses extruct to pull all JSON-LD blocks from a page, then walks the
schema.org Product graph to build an ExtractionPayload.

Supported schema.org types:
  - Product (primary target)
  - Offer / AggregateOffer (price extraction)
  - BreadcrumbList (origin/category hints)
  - WebSite / Organization (roaster name)

Field mapping strategy:
  Schema.org field         → ExtractionPayload field
  ─────────────────────────────────────────────────
  Product.name             → coffee_name, raw_title
  Product.description      → raw_description (also mined for origin/process signals)
  Product.offers.price     → price_variants[].price_gbp
  Product.offers.availability → price_variants[].availability
  Product.brand.name       → roaster_name
  Product.additionalProperty → mined for origin, varietal, process, roast, flavour
  Product.category         → origin/roast hints

Confidence scoring:
  Base confidence = number of core fields populated / total core fields.
  Bonus for offers with valid price, varietal, flavour notes.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.services.extraction.base import BaseParser
from app.services.extraction.payload import ExtractionPayload, ExtractionResult, PriceVariantPayload
from app.services.extraction.text_utils import (
    clean_html,
    extract_flavour_notes,
    extract_origin_country,
    extract_process,
    extract_roast_level,
    extract_varietal,
    extract_weight_g,
)

log = logging.getLogger(__name__)

# ── extruct import (optional dep — graceful failure) ──────────────────────────
try:
    import extruct
    _EXTRUCT_AVAILABLE = True
except ImportError:
    _EXTRUCT_AVAILABLE = False
    log.warning("extruct not installed — SchemaOrgParser will not function")


class SchemaOrgParser(BaseParser):
    """
    Extracts coffee data from schema.org JSON-LD embedded in HTML pages.

    Most modern coffee ecommerce sites (WooCommerce, Squarespace, custom)
    emit Product markup. This parser is the first fallback after Shopify.
    """

    extraction_method = "schema_org"

    def extract(self, html: bytes, url: str) -> ExtractionResult:
        if not _EXTRUCT_AVAILABLE:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["extruct library not installed"],
            )

        html_text = self._decode_html(html)

        try:
            data = extruct.extract(
                html_text,
                base_url=url,
                syntaxes=["json-ld"],
                uniform=True,
            )
        except Exception as exc:
            log.warning("extruct failed for %s: %s", url, exc)
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=[f"extruct error: {exc}"],
            )

        json_ld_items = data.get("json-ld", [])
        if not json_ld_items:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["No JSON-LD found in page"],
            )

        # Flatten @graph arrays and find Product nodes
        all_nodes = _flatten_nodes(json_ld_items)
        product_nodes = [n for n in all_nodes if _is_type(n, "Product")]

        if not product_nodes:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["No schema.org Product found in JSON-LD"],
            )

        # Use the first product node (most pages have exactly one)
        product = product_nodes[0]

        # Extract organisation/brand for roaster name
        org_nodes = [n for n in all_nodes if _is_type(n, ("Organization", "LocalBusiness"))]
        website_nodes = [n for n in all_nodes if _is_type(n, "WebSite")]

        errors: list[str] = []
        payload = self._map_product(product, org_nodes, website_nodes, url, errors)

        if len(product_nodes) > 1:
            errors.append(
                f"Multiple Product nodes found ({len(product_nodes)}); used first only"
            )

        # Determine validation status
        if not payload.coffee_name and not payload.price_variants:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["Product node found but yielded no usable fields"] + errors,
            )

        status = "partial" if errors else "valid"
        return ExtractionResult(
            payload=payload,
            validation_status=status,
            validation_errors=errors,
            extraction_method=self.extraction_method,
        )

    # ── Core mapping ──────────────────────────────────────────────────────────

    def _map_product(
        self,
        product: dict,
        org_nodes: list[dict],
        website_nodes: list[dict],
        url: str,
        errors: list[str],
    ) -> ExtractionPayload:
        """Map a schema.org Product node to ExtractionPayload."""

        name = _str(product.get("name", ""))
        description = clean_html(_str(product.get("description", "")))
        combined_text = f"{name} {description}"

        # ── Roaster name ───────────────────────────────────────────────────
        roaster_name = ""
        brand = product.get("brand") or {}
        if isinstance(brand, dict):
            roaster_name = _str(brand.get("name", ""))
        if not roaster_name:
            # Try organization nodes from the page
            for org in org_nodes:
                roaster_name = _str(org.get("name", ""))
                if roaster_name:
                    break
        if not roaster_name and website_nodes:
            roaster_name = _str(website_nodes[0].get("name", ""))
        if not roaster_name:
            # Last resort: extract from URL
            roaster_name = _roaster_from_url(url)

        # ── Price variants from offers ─────────────────────────────────────
        # Schema.org allows two shapes:
        #   product.offers = Offer
        #   product.offers = AggregateOffer { offers: [Offer, Offer, …] }
        # Flatten both into a list of leaf Offer dicts before mapping.
        price_variants: list[PriceVariantPayload] = []
        for offer in _flatten_offers(product.get("offers")):
            pv = _map_offer(offer, name)
            if pv is not None:
                price_variants.append(pv)

        # ── Additional properties (structured attribute pairs) ─────────────
        # schema.org additionalProperty: [{"name": "Origin", "value": "Ethiopia"}]
        additional: dict[str, str] = {}
        for prop in product.get("additionalProperty") or []:
            if not isinstance(prop, dict):
                continue
            k = _str(prop.get("name", "")).lower()
            v = _str(prop.get("value", ""))
            if k and v:
                additional[k] = v

        # ── Mine combined text for coffee-specific signals ─────────────────
        origin_country = (
            additional.get("origin") or
            additional.get("country") or
            additional.get("origin country") or
            extract_origin_country(combined_text)
        )
        origin_region = (
            additional.get("region") or
            additional.get("origin region") or
            ""
        )
        farm_or_estate = (
            additional.get("farm") or
            additional.get("estate") or
            additional.get("farm / estate") or
            ""
        )
        producer = (
            additional.get("producer") or
            additional.get("farmer") or
            ""
        )
        process = (
            additional.get("process") or
            additional.get("processing") or
            additional.get("processing method") or
            extract_process(combined_text)
        )
        roast_level = (
            additional.get("roast") or
            additional.get("roast level") or
            extract_roast_level(combined_text)
        )
        varietal_raw = (
            additional.get("varietal") or
            additional.get("variety") or
            additional.get("cultivar") or
            ""
        )
        varietal = extract_varietal(varietal_raw) if varietal_raw else extract_varietal(combined_text)
        flavour_notes = extract_flavour_notes(combined_text)
        decaf_flag = bool(re.search(r"\bdecaf\b", combined_text, re.I))

        # ── Brew suitability ───────────────────────────────────────────────
        brew_suitability = []
        if re.search(r"\bespresso\b", combined_text, re.I):
            brew_suitability.append("espresso")
        if re.search(r"\bfilter\b|\bpour.over\b|\bcafeti[eè]re\b|\baeropress\b", combined_text, re.I):
            brew_suitability.append("filter")

        # ── Grind options from offer names / product description ───────────
        from app.services.shopify.parser import parse_grind
        grind_options: list[str] = []
        for pv in price_variants:
            if pv.grind_type and pv.grind_type not in grind_options:
                grind_options.append(pv.grind_type)

        # ── Build weights list from variants ───────────────────────────────
        weights = sorted(set(
            pv.weight_g for pv in price_variants if pv.weight_g is not None
        ))

        # ── Assemble payload ───────────────────────────────────────────────
        payload = ExtractionPayload(
            coffee_name=name,
            roaster_name=roaster_name,
            origin_country=origin_country,
            origin_region=origin_region,
            farm_or_estate=farm_or_estate,
            producer=producer,
            varietal=varietal,
            process=process,
            roast_level=roast_level,
            brew_suitability=brew_suitability,
            grind_options=grind_options,
            flavour_notes=flavour_notes,
            weights=weights,
            price_variants=price_variants,
            decaf_flag=decaf_flag,
            source_url=url,
            raw_title=name,
            raw_description=description[:3000],
            reasoning_summary=(
                f"Extracted via schema.org Product JSON-LD. "
                f"{'Offers found: ' + str(len(price_variants)) + '. ' if price_variants else 'No offers found. '}"
                f"{'AdditionalProperty fields: ' + ', '.join(additional.keys()) + '.' if additional else ''}"
            ),
        )

        # ── Confidence ─────────────────────────────────────────────────────
        payload.confidence = _compute_confidence(payload)
        return payload


# ── Offer mapping ─────────────────────────────────────────────────────────────

def _map_offer(offer: dict, product_name: str) -> PriceVariantPayload | None:
    """Map a schema.org Offer node to PriceVariantPayload."""
    price_str = _str(offer.get("price", ""))
    if not price_str:
        # Try priceSpecification
        price_spec = offer.get("priceSpecification") or {}
        if isinstance(price_spec, dict):
            price_str = _str(price_spec.get("price", ""))

    try:
        price_gbp = float(price_str.replace(",", "").strip())
    except (ValueError, TypeError):
        return None  # Skip offers with no parseable price

    currency = _str(offer.get("priceCurrency", "GBP")).upper()

    # Availability mapping
    avail_url = _str(offer.get("availability", ""))
    if "InStock" in avail_url or avail_url == "in_stock":
        availability = "in_stock"
    elif "OutOfStock" in avail_url or "SoldOut" in avail_url:
        availability = "out_of_stock"
    elif "PreOrder" in avail_url or "PreSale" in avail_url:
        availability = "preorder"
    else:
        availability = "unknown"

    # Try to get weight/grind from offer name or sku
    offer_name = _str(offer.get("name", "")) or product_name
    from app.services.shopify.parser import parse_grind
    grind = parse_grind(offer_name)
    weight_g = extract_weight_g(offer_name)

    return PriceVariantPayload(
        weight_g=weight_g,
        grind_type=grind.value if hasattr(grind, "value") else str(grind),
        price_gbp=price_gbp,
        currency_code=currency if currency else "GBP",
        availability=availability,
    )


# ── Offer flattening ──────────────────────────────────────────────────────────

def _flatten_offers(raw: Any) -> list[dict]:
    """
    Walk an offers tree (Offer | AggregateOffer | list of either) and return
    only leaf Offer dicts that have a price. Recursive so nested
    AggregateOffer.offers structures are handled.
    """
    out: list[dict] = []
    if raw is None:
        return out
    if isinstance(raw, list):
        for item in raw:
            out.extend(_flatten_offers(item))
        return out
    if not isinstance(raw, dict):
        return out

    nested = raw.get("offers")
    if nested:
        out.extend(_flatten_offers(nested))

    # Treat the node itself as an offer if it has a price (covers plain Offer
    # and AggregateOffer nodes whose nested array is missing).
    if raw.get("price") or (raw.get("priceSpecification") or {}).get("price"):
        out.append(raw)
    return out


# ── Graph utilities ───────────────────────────────────────────────────────────

def _flatten_nodes(items: list[dict]) -> list[dict]:
    """Flatten @graph arrays into a flat list of typed nodes."""
    nodes: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "@graph" in item:
            for node in item["@graph"]:
                if isinstance(node, dict):
                    nodes.append(node)
        else:
            nodes.append(item)
    return nodes


def _is_type(node: dict, type_names: str | tuple[str, ...]) -> bool:
    """Check if a schema.org node matches one or more type names."""
    raw_type = node.get("@type", "")
    types = raw_type if isinstance(raw_type, list) else [raw_type]
    type_names_set = {type_names} if isinstance(type_names, str) else set(type_names)
    return bool(types and any(
        any(tn in t for tn in type_names_set) for t in types
    ))


def _str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return _str(v.get("@value", v.get("name", "")))
    return str(v).strip()


def _roaster_from_url(url: str) -> str:
    """Extract a best-guess roaster name from the domain."""
    try:
        netloc = urlparse(url).netloc.lower()
        netloc = re.sub(r"^www\.", "", netloc)
        netloc = netloc.split(".")[0]
        # Convert hyphens/underscores to spaces and title-case
        return netloc.replace("-", " ").replace("_", " ").title()
    except Exception:
        return ""


def _compute_confidence(payload: ExtractionPayload) -> float:
    """
    Confidence for schema.org extraction.

    Schema.org is semi-structured — we trust it more than HTML rules
    but less than Shopify JSON. Base is completeness, capped at 0.85
    since the markup quality varies widely.
    """
    base = payload.completeness_score()
    bonus = 0.0
    if payload.price_variants:
        bonus += 0.05
    if payload.origin_country:
        bonus += 0.03
    if payload.flavour_notes:
        bonus += 0.02
    return round(min(0.85, base + bonus), 2)
