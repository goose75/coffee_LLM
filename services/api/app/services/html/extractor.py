"""
HTML Extractor — wrapper around existing schema.org/html/llm parsers.

This lightweight wrapper orchestrates the extraction chain:
1. Try schema.org microdata extraction
2. If failed or low confidence, try HTML rules-based extraction
3. If still failed or low confidence, try LLM-assisted extraction

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

log = logging.getLogger(__name__)


class HtmlExtractor:
    """
    Orchestrates extraction chain for HTML pages.

    Uses fallback strategy:
      1. Schema.org (if confidence >= 0.4)
      2. HTML rules (if confidence >= 0.4)
      3. LLM (if both failed or confidence < 0.4)
    """

    def __init__(self):
        """Initialize parsers."""
        self.schema_org_parser = SchemaOrgParser()
        self.html_rules_parser = HtmlRulesParser()
        self.llm_parser = LLMParser()

    async def extract_products(
        self, html_bytes: bytes, url: str
    ) -> list[ExtractionResultModel]:
        """
        Extract products from HTML using fallback chain.

        LLMParser.extract is async, so this method is async.

        Returns:
            List of ExtractionResult objects. Could be empty if all parsers
            fail, single extraction if one parser succeeds, or multiple if
            multiple parsers return valid/partial results.
        """
        results = []

        # Try schema.org first (highest precision if present)
        try:
            schema_result = self.schema_org_parser.extract(html_bytes, url)
            if schema_result.validation_status in ("valid", "partial"):
                if schema_result.payload.confidence >= 0.4:
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
            log.warning(f"Schema.org extraction failed for {url}: {exc}")

        # Try HTML rules (best for common platforms like WooCommerce)
        try:
            html_result = self.html_rules_parser.extract(html_bytes, url)
            if html_result.validation_status in ("valid", "partial"):
                if html_result.payload.confidence >= 0.4:
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
            log.warning(f"HTML rules extraction failed for {url}: {exc}")

        # If both deterministic methods failed or low confidence, try LLM
        best_confidence = max(
            [r.payload.confidence for r in results], default=0.0
        )

        if best_confidence < 0.4:
            try:
                # Clean HTML to text for LLM parser
                page_text = clean_page_text(html_bytes)
                llm_result = await self.llm_parser.extract(page_text, url)
                # Unwrap the result (LLMExtractionResult contains an ExtractionResult)
                extraction_result = llm_result.result
                if extraction_result.validation_status in ("valid", "partial"):
                    results.append(extraction_result)
                    log.info(
                        f"LLM extraction fallback for {url} "
                        f"(confidence: {extraction_result.payload.confidence:.2f})"
                    )
            except Exception as exc:
                log.error(f"LLM extraction failed for {url}: {exc}")

        if not results:
            log.warning(
                f"All extraction methods failed for {url} "
                f"(schema.org, html rules, llm)"
            )

        return results
