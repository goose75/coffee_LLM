"""
ExtractionService — orchestrates all parsers and persists results to raw_extractions.

Updated to include the LLM fallback after HTML rules. The full chain is:
  1. SchemaOrgParser   (schema.org JSON-LD, confidence cap 0.85)
  2. HtmlRulesParser   (CSS selectors, confidence cap 0.70)
  3. LLMParser         (Anthropic API, last resort, highest cost)

LLM is only invoked when:
  - Both deterministic parsers return invalid, OR
  - The caller explicitly requests force_llm=True (for re-extraction)
  - The best deterministic result has confidence < llm_threshold (default 0.4)

The LLM parser path is async — ExtractionService.extract_and_save() is now
also async (it was already so, but now awaits the LLM call directly).
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
from app.services.extraction.llm_parser import LLMParser, clean_page_text
from app.services.extraction.payload import ExtractionResult
from app.services.extraction.schema_org_parser import SchemaOrgParser

log = logging.getLogger(__name__)

# Confidence below this threshold triggers LLM fallback even if a result exists
LLM_FALLBACK_THRESHOLD = 0.40

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
        llm_parser: LLMParser | None = None,
        use_llm: bool = True,
        llm_threshold: float = LLM_FALLBACK_THRESHOLD,
    ) -> None:
        self.session = session
        self.chain = chain or _DETERMINISTIC_CHAIN
        self.llm_parser = llm_parser or LLMParser()
        self.use_llm = use_llm and bool(settings.ANTHROPIC_API_KEY)
        self.llm_threshold = llm_threshold

    async def extract_and_save(
        self,
        html: bytes,
        url: str,
        source_page: SourcePage,
        force_llm: bool = False,
    ) -> RawExtraction:
        """
        Run parser chain and persist the best result.

        Tries deterministic parsers first; falls back to LLM if:
          - All deterministic parsers failed (result is None or invalid), OR
          - Best result confidence < llm_threshold, OR
          - force_llm=True
        """
        # ── Step 1: Try deterministic parsers ─────────────────────────────
        det_result = self.chain.run(html, url)

        should_use_llm = (
            force_llm
            or det_result is None
            or det_result.validation_status == "invalid"
            or (det_result.payload.confidence < self.llm_threshold)
        )

        if should_use_llm and self.use_llm:
            log.info(
                "Falling back to LLM for %s (det_result=%s, confidence=%.2f)",
                url,
                det_result.validation_status if det_result else "None",
                det_result.payload.confidence if det_result else 0.0,
            )
            page_text = clean_page_text(html)
            llm_result = await self.llm_parser.extract(page_text, url)

            # Use LLM result if it's better than deterministic
            llm_extraction_result = llm_result.result
            if (
                det_result is None
                or det_result.validation_status == "invalid"
                or llm_extraction_result.payload.confidence > det_result.payload.confidence
            ):
                extraction = self._build_orm(
                    llm_extraction_result,
                    source_page,
                    model_name=llm_result.model_name,
                    prompt_version=llm_result.prompt_version,
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
        Run all parsers (including LLM) and save all results.
        Used by the extraction comparison review tool.
        """
        extractions: list[RawExtraction] = []

        # Deterministic parsers
        for det_result in self.chain.run_all(html, url):
            extractions.append(self._build_orm(det_result, source_page))

        # LLM parser
        if self.use_llm:
            page_text = clean_page_text(html)
            llm_result = await self.llm_parser.extract(page_text, url)
            extractions.append(self._build_orm(
                llm_result.result,
                source_page,
                model_name=llm_result.model_name,
                prompt_version=llm_result.prompt_version,
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
