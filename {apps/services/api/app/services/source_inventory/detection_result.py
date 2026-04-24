"""
Detection result types.

These are the structured outputs of each domain probe. They are intermediate
data structures — not persisted directly, but used to populate the stores
and source_pages tables after detection completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DetectionSignal(str, Enum):
    """Which signal determined the parser strategy."""
    shopify_products_json = "shopify_products_json"
    shopify_meta_tag = "shopify_meta_tag"
    schema_org_product = "schema_org_product"
    sitemap_found = "sitemap_found"
    html_fallback = "html_fallback"
    unreachable = "unreachable"
    timeout = "timeout"


@dataclass
class ShopifyProbeResult:
    """Result of probing /products.json on a domain."""
    reachable: bool
    status_code: int | None = None
    product_count: int | None = None
    feed_url: str | None = None
    error: str | None = None


@dataclass
class SitemapProbeResult:
    """Result of checking sitemap.xml availability."""
    found: bool
    url: str | None = None
    status_code: int | None = None
    url_count: int | None = None  # None if parsing was skipped
    error: str | None = None


@dataclass
class SchemaOrgProbeResult:
    """Result of scanning homepage HTML for schema.org Product JSON-LD."""
    found: bool
    product_count: int = 0
    has_offer: bool = False
    error: str | None = None


@dataclass
class HomepageProbeResult:
    """Result of fetching the homepage for meta-signal detection."""
    reachable: bool
    status_code: int | None = None
    is_shopify_meta: bool = False  # Shopify.theme in <script> or x-shopify-* headers
    final_url: str | None = None  # after redirects
    error: str | None = None


@dataclass
class DomainDetectionResult:
    """
    Aggregated result of all probes against a single domain.
    
    parser_strategy is the final assigned value written to the store.
    signals is the ordered list of evidence that drove the decision.
    """
    domain: str
    homepage_url: str
    reachable: bool

    # Per-probe results
    homepage: HomepageProbeResult | None = None
    shopify: ShopifyProbeResult | None = None
    sitemap: SitemapProbeResult | None = None
    schema_org: SchemaOrgProbeResult | None = None

    # Final decision
    parser_strategy: str = "unknown"
    source_type: str = "html"
    signals: list[DetectionSignal] = field(default_factory=list)

    # Discovered URLs to seed into source_pages
    discovered_urls: list[dict] = field(default_factory=list)

    error: str | None = None

    def assign_strategy(self) -> None:
        """
        Determine parser_strategy from probe results.

        Priority:
          1. Shopify products.json reachable           → shopify
          2. Shopify meta tag in HTML                  → shopify
          3. schema.org Product found in homepage      → schema_org
          4. Domain is reachable but nothing detected  → html
          5. Domain unreachable                        → unknown
        """
        if self.shopify and self.shopify.reachable:
            self.parser_strategy = "shopify"
            self.source_type = "shopify"
            self.signals.append(DetectionSignal.shopify_products_json)
            if self.shopify.feed_url:
                self.discovered_urls.append({
                    "url": self.shopify.feed_url,
                    "page_type": "feed",
                    "parser_strategy": "shopify",
                })
            return

        if self.homepage and self.homepage.is_shopify_meta:
            self.parser_strategy = "shopify"
            self.source_type = "shopify"
            self.signals.append(DetectionSignal.shopify_meta_tag)
            # Shopify products.json wasn't directly reachable (password-protected?)
            return

        if self.schema_org and self.schema_org.found:
            self.parser_strategy = "schema_org"
            self.source_type = "schema_org"
            self.signals.append(DetectionSignal.schema_org_product)
            if self.homepage and self.homepage.final_url:
                self.discovered_urls.append({
                    "url": self.homepage.final_url,
                    "page_type": "homepage",
                    "parser_strategy": "schema_org",
                })
            return

        if self.reachable:
            self.parser_strategy = "html"
            self.source_type = "html"
            self.signals.append(DetectionSignal.html_fallback)
            return

        self.parser_strategy = "unknown"
        self.source_type = "html"
        self.signals.append(DetectionSignal.unreachable)
