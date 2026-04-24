"""
BaseParser — the interface all extraction strategies implement.

Every parser:
  1. Accepts raw HTML bytes and a URL string.
  2. Returns an ExtractionResult with a validated ExtractionPayload.
  3. Sets payload.confidence based on how much of the schema it was able to fill.
  4. Never raises — errors are captured in ExtractionResult.validation_errors.

The extraction pipeline calls parsers in priority order:
  schema_org → html_rules → llm (Phase 6)

Parsers are stateless. Instantiate once, call extract() many times.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass

from app.services.extraction.payload import ExtractionPayload, ExtractionResult

log = logging.getLogger(__name__)


class BaseParser(abc.ABC):
    """
    Abstract base for all extraction strategies.

    Subclasses must implement:
      - extraction_method: str  (matches ExtractionMethod enum value)
      - extract(html: bytes, url: str) -> ExtractionResult
    """

    extraction_method: str  # must be set on subclass

    @abc.abstractmethod
    def extract(self, html: bytes, url: str) -> ExtractionResult:
        """
        Extract structured coffee data from raw HTML.

        Args:
            html:  Raw page bytes (UTF-8 or latin-1 encoded HTML).
            url:   Canonical URL of the page (used for source_url field and logging).

        Returns:
            ExtractionResult — never raises.
        """

    def _safe_extract(self, html: bytes, url: str) -> ExtractionResult:
        """
        Wrapper that catches any unhandled exception from extract()
        and returns an invalid ExtractionResult instead of propagating.
        """
        try:
            return self.extract(html, url)
        except Exception as exc:
            log.error(
                "%s.extract() raised unexpectedly for %s: %s",
                self.__class__.__name__, url, exc, exc_info=True,
            )
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=[f"Unhandled exception: {exc}"],
            )

    def _decode_html(self, html: bytes) -> str:
        """Decode bytes to str, trying UTF-8 then latin-1."""
        for encoding in ("utf-8", "latin-1"):
            try:
                return html.decode(encoding)
            except UnicodeDecodeError:
                continue
        return html.decode("utf-8", errors="replace")


@dataclass
class ParserChain:
    """
    Runs parsers in order, returning the first successful (valid/partial) result.

    Usage:
        chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
        result = chain.run(html, url)
    """

    parsers: list[BaseParser]

    def run(self, html: bytes, url: str) -> ExtractionResult | None:
        """
        Try each parser in sequence. Returns the first non-invalid result,
        or None if all parsers fail.
        """
        for parser in self.parsers:
            result = parser._safe_extract(html, url)
            if result.validation_status != "invalid":
                return result
            log.debug(
                "%s returned invalid for %s: %s",
                parser.__class__.__name__, url, result.validation_errors,
            )
        return None

    def run_all(self, html: bytes, url: str) -> list[ExtractionResult]:
        """Run all parsers and return all results (for comparison / ensemble)."""
        return [p._safe_extract(html, url) for p in self.parsers]
