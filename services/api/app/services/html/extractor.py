"""
HTML Extractor — wrapper around existing schema.org/html/llm parsers.

This extractor handles both single-product and multi-product (listing) pages:

Single-product page flow:
1. Try schema.org microdata extraction
2. If failed or low confidence, try HTML rules-based extraction
3. If still failed or low confidence, try LLM-assisted extraction

Multi-product (listing) page flow:
1. Detect product containers (WooCommerce .product, Shopify .product-item, etc.)
2. For each container, extract as single product
3. Return all extracted products

Returns ExtractionResult objects (not RawExtraction records) for direct
consumption by HtmlIngestionPipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.llm_parser import LLMParser, clean_page_text
from app.services.extraction.payload import ExtractionPayload, ExtractionResult as ExtractionResultModel
from .product_listing_extractor import ProductListingExtractor

log = logging.getLogger(__name__)


class HtmlExtractor:
    """
    Orchestrates extraction chain for HTML pages.

    Automatically detects listing pages with multiple products and handles them
    differently from single-product pages.

    Fallback strategy (per product):
      1. Schema.org (if confidence >= 0.4)
      2. HTML rules (if confidence >= 0.4)
      3. LLM (if both failed or confidence < 0.4)
    """

    def __init__(self):
        """Initialize parsers."""
        self.schema_org_parser = SchemaOrgParser()
        self.html_rules_parser = HtmlRulesParser()
        self.llm_parser = LLMParser()
        self.listing_extractor = ProductListingExtractor()

    async def extract_products(
        self, html_bytes: bytes, url: str
    ) -> list[ExtractionResultModel]:
        """
        Extract products from HTML, handling both single and multi-product pages.

        For listing pages (multiple products detected):
          - Extract each product container separately
          - Return list of all extracted products

        For single-product pages:
          - Try schema.org → HTML rules → LLM fallback chain
          - Return single result if successful

        Returns:
            List of ExtractionResult objects. Could be empty if all methods fail.
        """
        html_str = html_bytes.decode("utf-8", errors="ignore")
        results = []

        # Step 1: Detect if this is a listing page
        try:
            is_listing = self.listing_extractor.is_listing_page(html_str)
            if is_listing:
                log.info(f"Detected listing page with multiple products: {url}")
                product_containers = self.listing_extractor.extract_product_containers(html_str)
                log.info(f"Extracted {len(product_containers)} product containers from {url}")

                # Extract each product container separately
                for i, container_html in enumerate(product_containers):
                    try:
                        container_bytes = container_html.encode("utf-8")
                        container_results = await self._extract_single_product(
                            container_bytes, f"{url}#product-{i}"
                        )
                        results.extend(container_results)
                    except Exception as exc:
                        log.warning(
                            f"Failed to extract product {i} from {url}: {exc}"
                        )

                if results:
                    log.info(
                        f"Successfully extracted {len(results)} products from listing page {url}"
                    )
                    return results
                # If listing detection found containers but extraction failed,
                # fall through to single-product extraction as fallback
                log.warning(
                    f"Listing page extraction failed for {url}, "
                    f"falling back to single-product extraction"
                )

        except Exception as exc:
            log.debug(f"Listing page detection failed for {url}: {exc}")

        # Step 2: Fall back to single-product extraction
        results = await self._extract_single_product(html_bytes, url)
        return results

    async def _extract_single_product(
        self, html_bytes: bytes, url: str
    ) -> list[ExtractionResultModel]:
        """
        Extract a single product using the fallback chain.

        Try: schema.org → HTML rules → LLM (when available)

        Returns:
            List with 0-1 ExtractionResult objects
        """
        results = []

        # Try schema.org first (highest precision if present)
        try:
            schema_result = self.schema_org_parser.extract(html_bytes, url)
            if schema_result.validation_status in ("valid", "partial"):
                if schema_result.payload.confidence >= 0.3:  # Lowered threshold to 0.3 since LLM unavailable
                    results.append(schema_result)
                    log.debug(
                        f"Schema.org extraction succeeded for {url} "
                        f"(confidence: {schema_result.payload.confidence:.2f})"
                    )
                else:
                    log.debug(
                        f"Schema.org confidence too low for {url} "
                        f"({schema_result.payload.confidence:.2f})"
                    )
        except Exception as exc:
            log.debug(f"Schema.org extraction failed for {url}: {exc}")

        # Try HTML rules (best for common platforms like WooCommerce)
        try:
            html_result = self.html_rules_parser.extract(html_bytes, url)
            if html_result.validation_status in ("valid", "partial"):
                if html_result.payload.confidence >= 0.3:  # Lowered threshold to 0.3 since LLM unavailable
                    results.append(html_result)
                    log.debug(
                        f"HTML rules extraction succeeded for {url} "
                        f"(confidence: {html_result.payload.confidence:.2f})"
                    )
                else:
                    log.debug(
                        f"HTML rules confidence too low for {url} "
                        f"({html_result.payload.confidence:.2f})"
                    )
        except Exception as exc:
            log.debug(f"HTML rules extraction failed for {url}: {exc}")

        # Skip LLM extraction for now due to Anthropic API credit issues
        # When API is fixed, re-enable LLM as fallback for low-confidence results
        #
        # If both deterministic methods failed or low confidence, would try LLM
        # best_confidence = max([r.payload.confidence for r in results], default=0.0)
        # if best_confidence < 0.3:
        #     try:
        #         page_text = clean_page_text(html_bytes)
        #         llm_result = await self.llm_parser.extract(page_text, url)
        #         extraction_result = llm_result.result
        #         if extraction_result.validation_status in ("valid", "partial"):
        #             results.append(extraction_result)
        #             log.info(f"LLM extraction fallback for {url}")
        #     except Exception as exc:
        #         log.debug(f"LLM extraction skipped for {url}: {exc}")

        if not results:
            log.debug(
                f"All extraction methods failed for {url} "
                f"(schema.org, html rules, llm)"
            )

        return results
