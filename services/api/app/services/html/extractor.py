"""HTML extractor — runs parser chain (custom → schema.org → html rules → llm)."""
from __future__ import annotations

from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.llm_parser import LLMParser
from app.services.extraction.monmouth_parser import CustomStyleParser
from app.services.extraction.payload import ExtractionResult


class HtmlExtractor:
    """
    Wraps extraction parsers: runs custom site parsers → schema.org → html rules → llm chain.
    Returns ExtractionResult objects (not RawExtraction records).
    """

    def __init__(self):
        self.custom_style_parser = CustomStyleParser()
        self.schema_org_parser = SchemaOrgParser()
        self.html_rules_parser = HtmlRulesParser()
        self.llm_parser = LLMParser()

    async def extract_products(self, html_bytes: bytes, url: str) -> list[ExtractionResult]:
        """
        Run parser chain on HTML page.
        Returns list of ExtractionResult objects (could be empty if all parsers fail).
        """
        results = []

        # Try custom style parser (site-specific, very high precision, can return multiple products)
        try:
            custom_results = await self.custom_style_parser.extract_all(html_bytes, url)
            results.extend(custom_results)
        except Exception:
            pass

        # Try schema.org parser (high precision, low recall)
        try:
            schema_result = await self.schema_org_parser.extract(html_bytes, url)
            if schema_result.validation_status in ("valid", "partial"):
                results.append(schema_result)
        except Exception:
            pass

        # Try HTML rules parser (medium precision/recall)
        try:
            html_result = await self.html_rules_parser.extract(html_bytes, url)
            if html_result.validation_status in ("valid", "partial") and html_result.payload.confidence >= 0.4:
                results.append(html_result)
        except Exception:
            pass

        # Try LLM fallback if low confidence so far
        try:
            best_confidence = max([r.payload.confidence for r in results], default=0)
            if best_confidence < 0.4:
                llm_result = await self.llm_parser.extract(html_bytes, url)
                if llm_result.validation_status in ("valid", "partial"):
                    results.append(llm_result)
        except Exception:
            pass

        return results
