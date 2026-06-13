"""
Parser Testing Framework — test all parsers on a sample page.

Tests schema.org, HTML rules, and LLM parsers on a real product page
and scores them based on:
- Extraction status (valid > partial > invalid)
- Confidence score
- Fields extracted
- Overall quality

Returns ranked list of parsers with scores for picking the best one.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.llm_parser import LlmParser

log = logging.getLogger(__name__)


@dataclass
class ParserScore:
    """Score for a single parser."""

    parser_name: str
    status: str  # valid, partial, invalid, error
    confidence: float  # 0.0-1.0
    fields_extracted: int  # count of non-empty fields
    has_coffee_name: bool
    has_price: bool
    has_origin: bool
    has_process: bool
    has_roast_level: bool
    has_varietal: bool
    has_flavour_notes: bool

    @property
    def total_score(self) -> float:
        """Calculate overall score (0-1)."""
        # Status weight: valid=1.0, partial=0.7, invalid=0
        status_score = {"valid": 1.0, "partial": 0.7, "invalid": 0.0, "error": 0.0}.get(
            self.status, 0.0
        )

        # Field completeness: how many of 7 core fields
        field_ratio = self.fields_extracted / 7.0

        # Weighted score: 40% status, 35% confidence, 25% fields
        return (status_score * 0.4) + (self.confidence * 0.35) + (field_ratio * 0.25)

    def __lt__(self, other: ParserScore) -> bool:
        """Sort by total_score descending."""
        return self.total_score > other.total_score


async def test_all_parsers(html_bytes: bytes, url: str) -> list[ParserScore]:
    """
    Test all parsers on a sample page.

    Returns:
        List of ParserScore objects, sorted by total_score (best first)
    """
    scores = []

    # Test schema.org parser
    try:
        log.debug(f"Testing schema.org parser on {url}")
        schema_parser = SchemaOrgParser()
        result = schema_parser.extract(html_bytes, url)

        score = _score_result(result, "schema.org")
        scores.append(score)
        log.debug(f"Schema.org score: {score.total_score:.2f}")

    except Exception as e:
        log.warning(f"Schema.org parser test failed: {e}")
        scores.append(
            ParserScore(
                parser_name="schema.org",
                status="error",
                confidence=0.0,
                fields_extracted=0,
                has_coffee_name=False,
                has_price=False,
                has_origin=False,
                has_process=False,
                has_roast_level=False,
                has_varietal=False,
                has_flavour_notes=False,
            )
        )

    # Test HTML rules parser
    try:
        log.debug(f"Testing HTML rules parser on {url}")
        html_parser = HtmlRulesParser()
        result = html_parser.extract(html_bytes, url)

        score = _score_result(result, "html")
        scores.append(score)
        log.debug(f"HTML rules score: {score.total_score:.2f}")

    except Exception as e:
        log.warning(f"HTML rules parser test failed: {e}")
        scores.append(
            ParserScore(
                parser_name="html",
                status="error",
                confidence=0.0,
                fields_extracted=0,
                has_coffee_name=False,
                has_price=False,
                has_origin=False,
                has_process=False,
                has_roast_level=False,
                has_varietal=False,
                has_flavour_notes=False,
            )
        )

    # Test LLM parser
    try:
        log.debug(f"Testing LLM parser on {url}")
        llm_parser = LlmParser()
        result = await llm_parser.extract(html_bytes, url)

        score = _score_result(result, "llm")
        scores.append(score)
        log.debug(f"LLM score: {score.total_score:.2f}")

    except Exception as e:
        log.warning(f"LLM parser test failed: {e}")
        scores.append(
            ParserScore(
                parser_name="llm",
                status="error",
                confidence=0.0,
                fields_extracted=0,
                has_coffee_name=False,
                has_price=False,
                has_origin=False,
                has_process=False,
                has_roast_level=False,
                has_varietal=False,
                has_flavour_notes=False,
            )
        )

    # Sort by score (best first)
    scores.sort()

    log.info(f"Parser test results: {', '.join(f'{s.parser_name}={s.total_score:.2f}' for s in scores)}")

    return scores


def _score_result(result: any, parser_name: str) -> ParserScore:
    """Score a single extraction result."""
    payload = result.payload
    status = result.validation_status

    # Count extracted fields
    fields_count = 0
    has_coffee_name = bool(payload.coffee_name)
    has_price = bool(payload.price_variants and len(payload.price_variants) > 0)
    has_origin = bool(payload.origin_country)
    has_process = bool(payload.process)
    has_roast_level = bool(payload.roast_level)
    has_varietal = bool(payload.varietal and len(payload.varietal) > 0)
    has_flavour_notes = bool(payload.flavour_notes and len(payload.flavour_notes) > 0)

    if has_coffee_name:
        fields_count += 1
    if has_price:
        fields_count += 1
    if has_origin:
        fields_count += 1
    if has_process:
        fields_count += 1
    if has_roast_level:
        fields_count += 1
    if has_varietal:
        fields_count += 1
    if has_flavour_notes:
        fields_count += 1

    return ParserScore(
        parser_name=parser_name,
        status=status,
        confidence=float(payload.confidence),
        fields_extracted=fields_count,
        has_coffee_name=has_coffee_name,
        has_price=has_price,
        has_origin=has_origin,
        has_process=has_process,
        has_roast_level=has_roast_level,
        has_varietal=has_varietal,
        has_flavour_notes=has_flavour_notes,
    )
