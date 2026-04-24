"""
HTML Rules Parser — deterministic CSS selector-based extraction.

Used when schema.org markup is absent or too sparse. Applies a priority-ordered
set of CSS selectors to extract product fields from raw HTML.

Architecture:
  - SelectorRule: a named rule with multiple CSS selector candidates
  - HtmlRulesParser: orchestrates rules against parsed HTML

Selector strategy:
  Each field has an ordered list of selectors from most-specific to
  least-specific. The parser tries each in order and uses the first match.
  This makes the parser robust to markup variation across WooCommerce themes,
  Squarespace, Cargo, and bespoke sites.

Confidence scoring:
  HTML rules extraction is inherently less reliable than schema.org.
  Maximum confidence is 0.70. Score is computed from field coverage.

Limitations (handled by LLM fallback in Phase 6):
  - Sites with JavaScript-rendered content
  - Sites that put all information in images
  - Highly bespoke markup with non-standard patterns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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

# ── selectolax import ─────────────────────────────────────────────────────────
try:
    from selectolax.parser import HTMLParser as SelectolaxParser, Node
    _SELECTOLAX_AVAILABLE = True
except ImportError:
    _SELECTOLAX_AVAILABLE = False
    log.warning("selectolax not installed — HtmlRulesParser will use fallback")

# ── BeautifulSoup fallback ────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False


@dataclass
class SelectorRule:
    """
    A named CSS selector rule with multiple candidate selectors.
    Tries each selector in order, returns the first match's text.
    """

    name: str
    selectors: list[str]
    # Optional post-processor (e.g. strip £, parse list from commas)
    transform: Callable[[str], str] | None = None
    multi: bool = False  # If True, return all matches not just first


# ─── Selector definitions ─────────────────────────────────────────────────────
#
# Ordered from most semantically precise (microdata / data attributes)
# to broadest (class names, text patterns).
#
# Coverage targets:
#   - WooCommerce (most common UK indie shop CMS)
#   - Squarespace product pages
#   - Shopify without products.json (rare edge case)
#   - Big Cartel
#   - Custom hand-coded sites

TITLE_SELECTORS = SelectorRule("title", [
    "h1.product_title",                    # WooCommerce
    "h1.product-title",
    '[itemprop="name"]',
    "h1.product__title",                   # Shopify theme
    "h1.ProductMeta__Title",
    "#product-title",
    "h1[class*='product']",
    "h1[class*='coffee']",
    ".product-name h1",
    ".entry-title",
    "h1",                                  # Last resort
])

DESCRIPTION_SELECTORS = SelectorRule("description", [
    '[itemprop="description"]',
    ".woocommerce-product-details__short-description",
    ".product-short-description",
    "#tab-description .product-description",
    ".product__description",
    ".product-description",
    ".ProductMeta__Description",
    "[class*='product-desc']",
    ".entry-content",
    "[class*='description']",
])

PRICE_SELECTORS = SelectorRule("price", [
    '[itemprop="price"]',
    ".woocommerce-Price-amount bdi",
    ".price ins .amount",
    ".price .amount",
    ".product__price",
    ".ProductMeta__Price",
    "[class*='price']:not([class*='was']):not([class*='old'])",
    ".price",
])

BRAND_SELECTORS = SelectorRule("brand", [
    '[itemprop="brand"] [itemprop="name"]',
    '[itemprop="brand"]',
    ".brand",
    ".vendor",
    ".product__vendor",
    'meta[property="og:site_name"]',  # meta tag — need attr not text
])

# ─── Table / meta selectors for structured attribute extraction ────────────────

PRODUCT_TABLE_SELECTORS = SelectorRule("product_table", [
    ".product-attributes tr",
    ".woocommerce-product-attributes tr",
    ".product-meta tr",
    ".product_meta tr",
    ".additional_information tr",
    "table.variations tr",
    ".product-details tr",
    ".product-specs tr",
    "dl.product-attributes dt",
    "ul.product-meta li",
])

VARIANT_SELECTORS = SelectorRule("variants", [
    "select[name='attribute_pa_size'] option",
    "select[name='attribute_pa_weight'] option",
    "select[name='attribute_pa_grind'] option",
    ".variations select option",
    "[data-option-name] option",
], multi=True)


class HtmlRulesParser(BaseParser):
    """
    Deterministic CSS-selector based extraction for non-schema.org sites.

    Tries selectolax first (fast Lexbor-based parser), falls back to
    BeautifulSoup if unavailable.
    """

    extraction_method = "html_rules"
    MAX_CONFIDENCE = 0.70

    def extract(self, html: bytes, url: str) -> ExtractionResult:
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
                errors=["No HTML parser available (install selectolax or beautifulsoup4)"],
            )

        # ── Extract fields ────────────────────────────────────────────────
        title = extractor.text(TITLE_SELECTORS)
        if not title:
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=["Could not find product title with any selector"],
            )

        description_raw = extractor.text(DESCRIPTION_SELECTORS)
        description = clean_html(description_raw)

        # Price
        price_raw = extractor.text(PRICE_SELECTORS)
        price_gbp: float | None = None
        if price_raw:
            price_gbp = extract_price_gbp(price_raw) or _parse_first_float(price_raw)

        # Brand / roaster
        roaster_name = extractor.text(BRAND_SELECTORS)
        if not roaster_name:
            og_site = extractor.attr('meta[property="og:site_name"]', "content")
            roaster_name = og_site or ""

        # ── Mine product attributes table ─────────────────────────────────
        attributes = extractor.extract_attributes(PRODUCT_TABLE_SELECTORS)

        combined_text = f"{title} {description}"

        origin_country = (
            attributes.get("origin") or attributes.get("country") or
            attributes.get("origin country") or extract_origin_country(combined_text)
        )
        origin_region = (
            attributes.get("region") or attributes.get("origin region") or ""
        )
        farm_or_estate = (
            attributes.get("farm") or attributes.get("estate") or
            attributes.get("farm / estate") or ""
        )
        producer = attributes.get("producer") or attributes.get("farmer") or ""
        process = (
            attributes.get("process") or attributes.get("processing") or
            extract_process(combined_text)
        )
        roast_level = (
            attributes.get("roast") or attributes.get("roast level") or
            extract_roast_level(combined_text)
        )
        varietal_raw = attributes.get("varietal") or attributes.get("variety") or ""
        varietal = extract_varietal(varietal_raw) if varietal_raw else extract_varietal(combined_text)
        flavour_notes = extract_flavour_notes(combined_text)
        decaf_flag = bool(re.search(r"\bdecaf\b", combined_text, re.I))

        # ── Brew suitability ───────────────────────────────────────────────
        brew_suitability = []
        if re.search(r"\bespresso\b", combined_text, re.I):
            brew_suitability.append("espresso")
        if re.search(r"\bfilter\b|\bpour.over\b|\bcafeti[eè]re\b|\baeropress\b", combined_text, re.I):
            brew_suitability.append("filter")

        # ── Variant options ────────────────────────────────────────────────
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

        # If we have a price but no structured variants, create one variant
        if price_gbp is not None and not price_variants:
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

        # ── Assemble payload ───────────────────────────────────────────────
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
                f"Extracted via HTML rules selectors. "
                f"{'Product attributes table found with keys: ' + ', '.join(attributes.keys()) + '. ' if attributes else ''}"
                f"{'Price found: £' + str(price_gbp) + '. ' if price_gbp else 'No price found. '}"
                f"{'Variants: ' + str(len(variant_options)) + '. ' if variant_options else ''}"
                + (f"Issues: {'; '.join(errors)}." if errors else "")
            ),
        )

        # ── Confidence ─────────────────────────────────────────────────────
        payload.confidence = _compute_html_confidence(payload)

        status = "partial" if errors or not payload.price_variants else "valid"
        return ExtractionResult(
            payload=payload,
            validation_status=status,
            validation_errors=errors,
            extraction_method=self.extraction_method,
        )


# ─── HTML extraction backends ─────────────────────────────────────────────────

class SelectolaxExtractor:
    """Fast HTML extraction using selectolax (Lexbor engine)."""

    def __init__(self, html: str) -> None:
        self._tree = SelectolaxParser(html)

    def text(self, rule: SelectorRule) -> str:
        for selector in rule.selectors:
            try:
                # Handle meta tags (need content attr, not text)
                if selector.startswith("meta"):
                    return ""  # handled in attr() method
                node = self._tree.css_first(selector)
                if node:
                    text = node.text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def attr(self, selector: str, attribute: str) -> str:
        try:
            node = self._tree.css_first(selector)
            if node:
                return node.attrs.get(attribute, "") or ""
        except Exception:
            pass
        return ""

    def multi_text(self, rule: SelectorRule) -> list[str]:
        for selector in rule.selectors:
            try:
                nodes = self._tree.css(selector)
                texts = [n.text(strip=True) for n in nodes if n.text(strip=True)]
                if texts:
                    return texts
            except Exception:
                continue
        return []

    def extract_attributes(self, rule: SelectorRule) -> dict[str, str]:
        """Extract key-value pairs from a product attributes table."""
        result: dict[str, str] = {}
        for selector in rule.selectors:
            try:
                # Handle <tr> rows
                if selector.endswith("tr"):
                    rows = self._tree.css(selector)
                    for row in rows:
                        cells = row.css("td, th")
                        if len(cells) >= 2:
                            key = cells[0].text(strip=True).lower().rstrip(":")
                            value = cells[1].text(strip=True)
                            if key and value:
                                result[key] = value
                # Handle <dt>/<dd> pairs
                elif selector.endswith("dt"):
                    dts = self._tree.css(selector)
                    for dt in dts:
                        dd = dt.css_first("~ dd")
                        if dd:
                            key = dt.text(strip=True).lower().rstrip(":")
                            value = dd.text(strip=True)
                            if key and value:
                                result[key] = value
                # Handle <li> items with "Key: Value" format
                elif selector.endswith("li"):
                    items = self._tree.css(selector)
                    for li in items:
                        text = li.text(strip=True)
                        if ":" in text:
                            k, _, v = text.partition(":")
                            result[k.lower().strip()] = v.strip()
                if result:
                    break
            except Exception:
                continue
        return result


class BS4Extractor:
    """BeautifulSoup extraction fallback."""

    def __init__(self, html: str) -> None:
        self._soup = BeautifulSoup(html, "html.parser")

    def text(self, rule: SelectorRule) -> str:
        for selector in rule.selectors:
            try:
                el = self._soup.select_one(selector)
                if el:
                    text = el.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def attr(self, selector: str, attribute: str) -> str:
        try:
            el = self._soup.select_one(selector)
            if el:
                return el.get(attribute, "") or ""
        except Exception:
            pass
        return ""

    def multi_text(self, rule: SelectorRule) -> list[str]:
        for selector in rule.selectors:
            try:
                els = self._soup.select(selector)
                texts = [e.get_text(strip=True) for e in els]
                texts = [t for t in texts if t]
                if texts:
                    return texts
            except Exception:
                continue
        return []

    def extract_attributes(self, rule: SelectorRule) -> dict[str, str]:
        result: dict[str, str] = {}
        for selector in rule.selectors:
            try:
                if "tr" in selector:
                    rows = self._soup.select(selector)
                    for row in rows:
                        cells = row.select("td, th")
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True).lower().rstrip(":")
                            value = cells[1].get_text(strip=True)
                            if key and value:
                                result[key] = value
                if result:
                    break
            except Exception:
                continue
        return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_first_float(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def _compute_html_confidence(payload: ExtractionPayload) -> float:
    """
    HTML rules confidence — capped lower than schema.org because selector
    matches can be fragile across different site designs.
    """
    base = payload.completeness_score()
    bonus = 0.0
    if payload.price_variants:
        bonus += 0.05
    if payload.origin_country:
        bonus += 0.02
    return round(min(HtmlRulesParser.MAX_CONFIDENCE, base + bonus), 2)
