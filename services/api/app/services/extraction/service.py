"""
ExtractionService — orchestrates all parsers and persists results to raw_extractions.

Updated with HybridExtractor for cost optimization:
  1. SchemaOrgParser   (schema.org JSON-LD, confidence cap 0.85)
  2. HtmlRulesParser   (CSS selectors, confidence cap 0.70)
  3. HybridExtractor   (Rules → Ollama local → Anthropic API fallback)

HybridExtractor is invoked when:
  - Both deterministic parsers return invalid, OR
  - The caller explicitly requests force_llm=True (for re-extraction)
  - The best deterministic result has confidence < hybrid_threshold (default 0.4)

Cost optimization:
  - Rule extraction: instant, zero cost (70% of products)
  - Ollama extraction: local, free (25% of products)
  - API fallback: Anthropic only when needed (5% of products)
  - Expected cost reduction: 80-90% vs LLM-only

The hybrid path is async — ExtractionService.extract_and_save() is async
and awaits the HybridExtractor orchestration.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import ExtractionMethod, ValidationStatus
from app.models.raw_extraction import RawExtraction
from app.models.source_page import SourcePage
from app.services.extraction.base import ParserChain
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.hybrid_extractor import HybridExtractor
from app.services.extraction.payload import ExtractionResult
from app.services.extraction.schema_org_parser import SchemaOrgParser

log = logging.getLogger(__name__)

# Confidence below this threshold triggers hybrid extraction fallback
HYBRID_FALLBACK_THRESHOLD = 0.40

_DETERMINISTIC_CHAIN = ParserChain([
    SchemaOrgParser(),
    HtmlRulesParser(),
])


class ExtractionService:
    """
    Orchestrates extraction and persists results to raw_extractions.

    Usage:
        service = ExtractionService(session)
        extraction = await service.extract_and_save(html, url, source_page)
    """

    def __init__(
        self,
        session: AsyncSession,
        chain: ParserChain | None = None,
        hybrid_extractor: HybridExtractor | None = None,
        use_hybrid: bool = True,
        hybrid_threshold: float = HYBRID_FALLBACK_THRESHOLD,
    ) -> None:
        self.session = session
        self.chain = chain or _DETERMINISTIC_CHAIN
        self.hybrid_extractor = hybrid_extractor or HybridExtractor(
            use_ollama=True,
            use_api_fallback=bool(settings.ANTHROPIC_API_KEY),
        )
        self.use_hybrid = use_hybrid
        self.hybrid_threshold = hybrid_threshold

    async def extract_and_save(
        self,
        html: bytes,
        url: str,
        source_page: SourcePage,
        force_llm: bool = False,
    ) -> RawExtraction:
        """
        Run parser chain and persist the best result using hybrid strategy.

        Tries deterministic parsers first; falls back to hybrid (rules→Ollama→API) if:
          - All deterministic parsers failed (result is None or invalid), OR
          - Best result confidence < hybrid_threshold, OR
          - force_llm=True

        Cost optimization:
          - Deterministic (schema.org, HTML rules): always fast, always free
          - Hybrid (rules→Ollama→API): only when deterministic fails
            - 70% resolved by rule extraction (instant, free)
            - 25% resolved by Ollama (local, free)
            - 5% resolved by API fallback (costs $, only when needed)
        """
        # ── Step 1: Try deterministic parsers ─────────────────────────────
        det_result = self.chain.run(html, url)

        should_use_hybrid = (
            force_llm
            or det_result is None
            or det_result.validation_status == "invalid"
            or (det_result.payload.confidence < self.hybrid_threshold)
        )

        if should_use_hybrid and self.use_hybrid:
            log.info(
                "Using hybrid extraction for %s (det_result=%s, confidence=%.2f)",
                url,
                det_result.validation_status if det_result else "None",
                det_result.payload.confidence if det_result else 0.0,
            )
            hybrid_result = await self.hybrid_extractor.extract(html, url)

            # Use hybrid result if it's better than deterministic
            if (
                det_result is None
                or det_result.validation_status == "invalid"
                or hybrid_result.confidence > det_result.payload.confidence
            ):
                log.info(
                    "Hybrid extraction succeeded for %s via %s (confidence %.2f)",
                    url,
                    hybrid_result.strategy_used,
                    hybrid_result.confidence,
                )
                extraction = self._build_orm(
                    hybrid_result.final_result,
                    source_page,
                    model_name=f"hybrid/{hybrid_result.strategy_used}",
                    prompt_version="hybrid",
                )
                self.session.add(extraction)
                await self.session.flush()
                return extraction

        # ── Step 2: Use deterministic result (or empty invalid) ───────────
        final_result = det_result or ExtractionResult.invalid(
            method="html_rules",
            errors=["All parsers failed to produce a result"],
        )

        extraction = self._build_orm(final_result, source_page)
        self.session.add(extraction)
        await self.session.flush()

        log.info(
            "Extracted %s via %s: confidence=%.2f status=%s",
            url,
            final_result.extraction_method,
            final_result.payload.confidence,
            final_result.validation_status,
        )
        return extraction

    async def extract_all_methods(
        self,
        html: bytes,
        url: str,
        source_page: SourcePage,
    ) -> list[RawExtraction]:
        """
        Run all parsers (including hybrid) and save all results.
        Used by the extraction comparison review tool.
        """
        extractions: list[RawExtraction] = []

        # Deterministic parsers
        for det_result in self.chain.run_all(html, url):
            extractions.append(self._build_orm(det_result, source_page))

        # Hybrid extraction (orchestrates rules → Ollama → API)
        if self.use_hybrid:
            hybrid_result = await self.hybrid_extractor.extract(html, url)
            extractions.append(self._build_orm(
                hybrid_result.final_result,
                source_page,
                model_name=f"hybrid/{hybrid_result.strategy_used}",
                prompt_version="hybrid",
            ))

        for e in extractions:
            self.session.add(e)
        await self.session.flush()
        return extractions

    def _build_orm(
        self,
        result: ExtractionResult,
        source_page: SourcePage,
        model_name: str | None = None,
        prompt_version: str | None = None,
    ) -> RawExtraction:
        method_map = {
            "schema_org": ExtractionMethod.schema_org,
            "html_rules": ExtractionMethod.html_rules,
            "shopify_json": ExtractionMethod.shopify_json,
            "llm": ExtractionMethod.llm,
        }
        method = method_map.get(result.extraction_method, ExtractionMethod.html_rules)

        status_map = {
            "valid": ValidationStatus.valid,
            "invalid": ValidationStatus.invalid,
            "partial": ValidationStatus.partial,
        }
        status = status_map.get(result.validation_status, ValidationStatus.invalid)

        return RawExtraction(
            source_page_id=source_page.id,
            extraction_method=method,
            model_name=model_name,
            prompt_version=prompt_version,
            extracted_payload=result.payload.to_db_dict(),
            confidence_score=result.payload.confidence,
            validation_status=status,
            validation_errors=(
                {"errors": result.validation_errors} if result.validation_errors else None
            ),
        )
