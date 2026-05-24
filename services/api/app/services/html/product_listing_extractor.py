"""
Product Listing Extractor — multi-product extraction from listing pages.

Many coffee shops host multiple products on a single "shop" or "catalog" page.
This extractor detects product containers and extracts each product separately.

Strategy:
  1. Detect product containers using CSS selector patterns
  2. For each container, extract the product using single-product extraction
  3. Return list of all extracted products
  4. Fallback: if no containers found, treat entire page as single product

Common selectors:
  - WooCommerce: .product, .product-item, .woocommerce-loop-product
  - Shopify: .product-item, [data-product-id]
  - Custom: .coffee-product, .item, .listing-product
"""

from __future__ import annotations

import logging
from typing import Optional

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

from app.services.extraction.payload import ExtractionResult

log = logging.getLogger(__name__)


# Common CSS selectors for product containers across different platforms
PRODUCT_CONTAINER_SELECTORS = [
    # Elementor page builder (Elementor loop items)
    "[data-elementor-type='loop-item']",
    ".e-loop-item",
    "[data-elementor-post-type='product']",

    # WooCommerce (very common for UK indie coffee shops)
    ".product.type-product",
    ".product",
    ".product-item",
    ".woocommerce-loop-product",
    ".woocommerce-product-item",
    "[data-product-id]",

    # Shopify
    ".product__wrapper",
    "[data-product]",
    ".product-item",

    # Big Cartel, Squarespace, other platforms
    ".item",
    ".listing-item",
    ".gallery-item",
    ".catalog-item",
    ".coffee-item",
    ".coffee-product",

    # Generic patterns (low specificity, last resort)
    "[class*='product'][class*='item']",
    "[class*='product-card']",
]


class ProductListingExtractor:
    """
    Detects and extracts multiple products from a listing page.
    """

    def __init__(self):
        """Initialize parser backend."""
        if _SELECTOLAX_AVAILABLE:
            self.use_selectolax = True
        elif _BS4_AVAILABLE:
            self.use_selectolax = False
        else:
            raise ImportError(
                "No HTML parser available (install selectolax or beautifulsoup4)"
            )

    def extract_product_containers(self, html: str) -> list[str]:
        """
        Detect product containers on page and return their HTML.

        Returns:
            List of HTML strings, each containing one product container.
            Returns empty list if no containers found (treat page as single product).
        """
        containers: list[str] = []

        if self.use_selectolax:
            containers = self._extract_selectolax(html)
        else:
            containers = self._extract_bs4(html)

        log.debug(
            f"Found {len(containers)} product containers on page "
            f"(tried {len(PRODUCT_CONTAINER_SELECTORS)} selectors)"
        )

        return containers

    def _extract_selectolax(self, html: str) -> list[str]:
        """Extract product containers using selectolax."""
        tree = SelectolaxParser(html)
        containers: list[str] = []

        for selector in PRODUCT_CONTAINER_SELECTORS:
            try:
                nodes = tree.css(selector)
                if nodes and len(nodes) > 1:  # Only if multiple found
                    # Convert nodes back to HTML strings
                    for node in nodes:
                        html_str = node.html
                        if html_str and len(html_str) > 50:  # Skip tiny elements
                            containers.append(html_str)

                    if containers:
                        log.debug(
                            f"selectolax: Found {len(containers)} containers "
                            f"using selector '{selector}'"
                        )
                        return containers
            except Exception as exc:
                log.debug(f"selectolax selector '{selector}' failed: {exc}")
                continue

        return containers

    def _extract_bs4(self, html: str) -> list[str]:
        """Extract product containers using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        containers: list[str] = []

        for selector in PRODUCT_CONTAINER_SELECTORS:
            try:
                elements = soup.select(selector)
                if elements and len(elements) > 1:  # Only if multiple found
                    for elem in elements:
                        html_str = str(elem)
                        if html_str and len(html_str) > 50:  # Skip tiny elements
                            containers.append(html_str)

                    if containers:
                        log.debug(
                            f"BeautifulSoup: Found {len(containers)} containers "
                            f"using selector '{selector}'"
                        )
                        return containers
            except Exception as exc:
                log.debug(f"BeautifulSoup selector '{selector}' failed: {exc}")
                continue

        return containers

    def is_listing_page(self, html: str) -> bool:
        """
        Heuristic: Does this page contain multiple products?
        Returns True if multiple containers found.
        """
        containers = self.extract_product_containers(html)
        return len(containers) > 1
