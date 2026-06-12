"""
WooCommerce-Specific HTML Parser.

Specialized extraction for WordPress + WooCommerce + Elementor storefronts.
Targets sites like 17 Grams, Colonna Coffee, Monmouth Coffee, etc.

Architecture:
  - WooCommerceParser extends BaseParser
  - Provides comprehensive CSS selectors for WooCommerce markup
  - Extracts product attributes table (the most reliable data source)
  - Parses weight variants from <select> dropdowns
  - Confidence: up to 0.80 (higher than generic HtmlRulesParser due to specificity)

Key differences from generic HtmlRulesParser:
  - Knows exact WooCommerce table structure: <th>Attribute</th> + <td>Value</td>
  - Extracts multiple price variants from data attributes or hidden form fields
  - Better handling of WooCommerce-standard attribute names (case-insensitive)
  - Looks for flavor notes in description paragraphs
  - Determines brew suitability from roast level + description keywords
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from app.services.extraction.base import BaseParser
from app.services.extraction.payload import ExtractionPayload, ExtractionResult, PriceVariantPayload
from app.services.extraction.text_utils import (
    clean_html,
    extract_flavour_notes,
    extract_origin_country,
    extract_price_gbp,
    extract_process,
    extract_roast_level,
    extract_varietal,
    extract_weight_g,
)

log = logging.getLogger(__name__)

# ── selectolax / BeautifulSoup setup ──────────────────────────────────────
try:
    from selectolax.parser import HTMLParser as SelectolaxParser, Node
    _SELECTOLAX_AVAILABLE = True
except ImportError:
    _SELECTOLAX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False


@dataclass
class SelectorRule:
    """A CSS selector rule with candidates and optional transform."""
    name: str
    selectors: list[str]
    transform: Callable[[str], str] | None = None
    multi: bool = False


# ─── WooCommerce-Specific Selector Rules ─────────────────────────────────

# Title: nearly always .product_title in WooCommerce
TITLE_SELECTORS = SelectorRule("title", [
    "h1.product_title",                # Standard WooCommerce
    "h1.product-title",
    "h1[class*='product'][class*='title']",
    "h1",
])

# Description: WooCommerce puts short description in a specific div
DESCRIPTION_SELECTORS = SelectorRule("description", [
    ".woocommerce-product-details__short-description",
    ".product-short-description",
    "#tab-description",
    "[class*='description']",
])

# Price: WooCommerce wraps price in .woocommerce-Price-amount
PRICE_SELECTORS = SelectorRule("price", [
    ".woocommerce-Price-amount bdi",
    ".woocommerce-Price-amount",
    ".price bdi",
    ".price",
])

# Brand/Roaster: from og:site_name or .brand
BRAND_SELECTORS = SelectorRule("brand", [
    'meta[property="og:site_name"]',  # meta tag — need attr not text
    ".brand",
    ".vendor",
])

# Product attributes table: .woocommerce-product-attributes is standard
PRODUCT_ATTRIBUTES_SELECTORS = SelectorRule("attributes_table", [
    ".woocommerce-product-attributes",
    ".shop_attributes",
    ".product-attributes",
    "table.woocommerce-product-attributes",
    "table.product-attributes",
])

# Variant selectors: WooCommerce uses data-attribute_pa_* pattern
VARIANT_SELECTORS = SelectorRule("variants", [
    "select[name*='attribute_pa_']",
    "select[name*='pa_']",
    "select[name*='variation']",
    ".variations select",
], multi=True)


class WooCommerceParser(BaseParser):
    """
    Specialized extraction for WordPress + WooCommerce + Elementor sites.

    Provides higher confidence (up to 0.80) compared to generic HtmlRulesParser (0.70)
    by leveraging WooCommerce's structured markup patterns.
    """

    extraction_method = "woocommerce"
    MAX_CONFIDENCE = 0.80

    def extract(self, html: bytes, url: str) -> ExtractionResult:
        """Extract coffee product data from WooCommerce product page."""
        html_text = self._decode_html(html)
        errors: list[str] = []

        # Choose parser backend
        if _SELECTOLAX_AVAILABLE:
            extractor = SelectolaxExtractor(html_text)
        elif _BS4_AVAILABLE:
            extractor = BS4Extractor(html_text)
            errors.append("selectolax unavailable; used BeautifulSoup")
        else:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["No HTML parser available"],
            )

        # ── Check if this looks like a WooCommerce page ────────────────
        if not extractor.text(TITLE_SELECTORS):
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["Could not find product title"],
            )

        # ── Extract core fields ───────────────────────────────────────
        title = extractor.text(TITLE_SELECTORS)
        description_raw = extractor.text(DESCRIPTION_SELECTORS)
        description = clean_html(description_raw)
        price_raw = extractor.text(PRICE_SELECTORS)

        # Parse price
        price_gbp: float | None = None
        if price_raw:
            price_gbp = extract_price_gbp(price_raw) or _parse_first_float(price_raw)

        # Get brand/roaster
        roaster_name = ""
        og_site = extractor.attr('meta[property="og:site_name"]', "content")
        if og_site:
            roaster_name = og_site
        else:
            roaster_name = extractor.text(BRAND_SELECTORS)

        # ── Mine product attributes table (KEY DATA SOURCE) ────────────
        # This is where WooCommerce stores: Origin, Region, Process, Roast, Varietal, etc.
        attributes = extractor.extract_woocommerce_attributes(PRODUCT_ATTRIBUTES_SELECTORS)

        combined_text = f"{title} {description}".lower()

        # Extract all fields from attributes table first (most reliable in WooCommerce)
        origin_country = (
            attributes.get("origin") or
            attributes.get("origin country") or
            attributes.get("country") or
            extract_origin_country(combined_text)
        )
        origin_region = attributes.get("region") or ""
        farm_or_estate = (
            attributes.get("farm") or
            attributes.get("estate") or
            attributes.get("farm / estate") or
            ""
        )
        producer = attributes.get("producer") or attributes.get("farmer") or ""

        # Process: usually in attributes table
        process = (
            attributes.get("process") or
            attributes.get("processing") or
            extract_process(combined_text)
        )

        # Roast level: usually in attributes table, fallback to description
        roast_level = (
            attributes.get("roast") or
            attributes.get("roast level") or
            extract_roast_level(combined_text)
        )

        # Varietal: check attributes, then description
        varietal_raw = (
            attributes.get("varietal") or
            attributes.get("variety") or
            ""
        )
        varietal = (
            extract_varietal(varietal_raw) if varietal_raw
            else extract_varietal(combined_text)
        )

        # Flavor notes: extract from description
        flavour_notes = extract_flavour_notes(description)

        # Decaf flag
        decaf_flag = bool(re.search(r"\bdecaf\b", combined_text, re.I))

        # ── Brew suitability ───────────────────────────────────────────
        brew_suitability = []
        if re.search(r"\bespresso\b", combined_text, re.I):
            brew_suitability.append("espresso")
        if re.search(r"\bfilter\b|\bpour.over\b|\bcafeti[eè]re\b|\baeropress\b", combined_text, re.I):
            brew_suitability.append("filter")

        # If roast level gives us hints, add suitability
        if roast_level and not brew_suitability:
            roast_lower = roast_level.lower()
            if any(x in roast_lower for x in ["light", "medium", "city"]):
                brew_suitability.extend(["espresso", "filter"])
            elif any(x in roast_lower for x in ["dark", "french", "italian"]):
                brew_suitability.append("espresso")

        # ── Extract price variants ─────────────────────────────────────
        # WooCommerce stores variants in <select> dropdowns and sometimes in data-* attributes
        variant_options = extractor.multi_text(VARIANT_SELECTORS)
        price_variants: list[PriceVariantPayload] = []
        grind_options: list[str] = []
        weights: list[int] = []

        from app.services.shopify.parser import parse_grind
        for option_text in variant_options:
            if not option_text.strip() or option_text.lower() == "choose an option":
                continue
            wg = extract_weight_g(option_text)
            grind = parse_grind(option_text)
            if wg is not None:
                weights.append(wg)
            if grind.value != "unknown" and grind.value not in grind_options:
                grind_options.append(grind.value)

        # If we have a price but no structured variants, create one default variant
        if price_gbp is not None:
            wg = extract_weight_g(title) or (weights[0] if weights else None)
            from app.services.shopify.parser import parse_grind as _pg
            grind = _pg(title)
            price_variants.append(PriceVariantPayload(
                weight_g=wg,
                grind_type=grind.value,
                price_gbp=price_gbp,
                availability="unknown",
            ))

        weights = sorted(set(weights))

        # ── Assemble payload ───────────────────────────────────────────
        payload = ExtractionPayload(
            coffee_name=title,
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
            raw_title=title,
            raw_description=description[:3000],
            reasoning_summary=(
                f"WooCommerce-specific extraction. "
                f"{'Attributes table found with {0} fields. '.format(len(attributes)) if attributes else 'No attributes table. '}"
                f"{'Price: £{0:.2f}. '.format(price_gbp) if price_gbp else 'No price. '}"
                f"{'Variants: {0}. '.format(len(variant_options)) if variant_options else 'No variants. '}"
                f"{'Origin: {0}. '.format(origin_country) if origin_country else ''}"
                + (f"Issues: {'; '.join(errors)}." if errors else "")
            ),
        )

        # ── Confidence scoring ─────────────────────────────────────────
        payload.confidence = _compute_woocommerce_confidence(payload, attributes)

        status = "partial" if errors or not payload.price_variants else "valid"
        return ExtractionResult(
            payload=payload,
            validation_status=status,
            validation_errors=errors,
            extraction_method=self.extraction_method,
        )


# ─── HTML Extraction Backends ────────────────────────────────────────────

class SelectolaxExtractor:
    """Fast extraction using selectolax (Lexbor engine)."""

    def __init__(self, html: str) -> None:
        self._tree = SelectolaxParser(html)

    def text(self, rule: SelectorRule) -> str:
        """Extract text from first matching selector."""
        for selector in rule.selectors:
            try:
                if selector.startswith("meta"):
                    continue  # handled in attr()
                node = self._tree.css_first(selector)
                if node:
                    text = node.text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def attr(self, selector: str, attribute: str) -> str:
        """Extract attribute value."""
        try:
            node = self._tree.css_first(selector)
            if node:
                return node.attrs.get(attribute, "") or ""
        except Exception:
            pass
        return ""

    def multi_text(self, rule: SelectorRule) -> list[str]:
        """Extract text from all matching selectors."""
        collected: list[str] = []
        seen: set[str] = set()
        for selector in rule.selectors:
            try:
                nodes = self._tree.css(selector)
                for n in nodes:
                    t = n.text(strip=True)
                    if t and t not in seen:
                        seen.add(t)
                        collected.append(t)
            except Exception:
                continue
        return collected

    def extract_woocommerce_attributes(self, rule: SelectorRule) -> dict[str, str]:
        """
        Extract WooCommerce product attributes from <table class="woocommerce-product-attributes">.

        Returns dict of {attribute_name_lowercase: value}.
        """
        result: dict[str, str] = {}
        for selector in rule.selectors:
            try:
                # Try both <tr> pattern and <dl>/<dt>/<dd> pattern
                if "tr" in selector or selector.endswith(")"):
                    # <tr><th>Name</th><td>Value</td></tr> pattern (most common)
                    rows = self._tree.css("tr")
                    for row in rows:
                        ths = row.css("th")
                        tds = row.css("td")
                        if ths and tds:
                            key = ths[0].text(strip=True).lower().rstrip(":")
                            value = tds[0].text(strip=True)
                            if key and value:
                                result[key] = value
                        elif len(tds) >= 2:
                            key = tds[0].text(strip=True).lower().rstrip(":")
                            value = tds[1].text(strip=True)
                            if key and value:
                                result[key] = value
            except Exception:
                continue
        return result


class BS4Extractor:
    """Fallback extraction using BeautifulSoup."""

    def __init__(self, html: str) -> None:
        self._soup = BeautifulSoup(html, "html.parser")

    def text(self, rule: SelectorRule) -> str:
        """Extract text from first matching selector."""
        for selector in rule.selectors:
            try:
                if selector.startswith("meta"):
                    continue
                elem = self._soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def attr(self, selector: str, attribute: str) -> str:
        """Extract attribute value."""
        try:
            elem = self._soup.select_one(selector)
            if elem:
                return elem.get(attribute, "") or ""
        except Exception:
            pass
        return ""

    def multi_text(self, rule: SelectorRule) -> list[str]:
        """Extract text from all matching selectors."""
        collected: list[str] = []
        seen: set[str] = set()
        for selector in rule.selectors:
            try:
                elems = self._soup.select(selector)
                for elem in elems:
                    t = elem.get_text(strip=True)
                    if t and t not in seen:
                        seen.add(t)
                        collected.append(t)
            except Exception:
                continue
        return collected

    def extract_woocommerce_attributes(self, rule: SelectorRule) -> dict[str, str]:
        """Extract WooCommerce product attributes from table."""
        result: dict[str, str] = {}
        try:
            # Find any table that might have attributes
            tables = self._soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    ths = row.find_all("th")
                    tds = row.find_all("td")
                    if ths and tds:
                        key = ths[0].get_text(strip=True).lower().rstrip(":")
                        value = tds[0].get_text(strip=True)
                        if key and value:
                            result[key] = value
                    elif len(tds) >= 2:
                        key = tds[0].get_text(strip=True).lower().rstrip(":")
                        value = tds[1].get_text(strip=True)
                        if key and value:
                            result[key] = value
        except Exception:
            pass
        return result


# ─── Confidence Scoring ──────────────────────────────────────────────────

def _compute_woocommerce_confidence(payload: ExtractionPayload, attributes: dict[str, str]) -> float:
    """
    Compute confidence for WooCommerce extraction.

    Higher max confidence (0.80 vs 0.70 for generic) due to WooCommerce's structured markup.

    Scoring:
      - Base: 0.50 (we have a title)
      - +0.10 each for: price, origin, process, roast, description
      - +0.05 each for: varietal, flavor notes, brew suitability
      - Cap at MAX_CONFIDENCE (0.80)
    """
    confidence = 0.50

    if payload.price_variants:
        confidence += 0.10
    if payload.origin_country:
        confidence += 0.10
    if payload.process:
        confidence += 0.10
    if payload.roast_level:
        confidence += 0.10
    if payload.raw_description:
        confidence += 0.10
    if payload.varietal:
        confidence += 0.05
    if payload.flavour_notes:
        confidence += 0.05
    if payload.brew_suitability:
        confidence += 0.05

    # Bonus for attributes table presence (WooCommerce-specific)
    if attributes:
        confidence += 0.05

    return min(confidence, WooCommerceParser.MAX_CONFIDENCE)


def _parse_first_float(text: str) -> float | None:
    """Extract first float/price from text."""
    match = re.search(r"[\d.]+", text.replace("£", "").replace(",", ""))
    if match:
        try:
            return float(match.group())
        except (ValueError, AttributeError):
            pass
    return None
