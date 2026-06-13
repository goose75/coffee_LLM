"""
Multi-Stage Fallback Chain — try multiple parsers until one works.

When a store has product pages but extraction with best parser returns 0 records,
try other parsers in ranked order. Keep the first parser that actually produces
extraction results.

This handles edge cases where the "best" parser per scoring doesn't work in practice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    """Result of multi-stage fallback attempt."""

    success: bool
    parser_used: str  # Which parser finally worked
    records_created: int  # Products extracted
    parsers_tried: list[str]  # All parsers attempted in order
    reason: str  # Explanation of outcome


async def run_multi_stage_fallback(
    store_id: str,
    parser_scores: list[dict],
    re_ingest_func,
    get_store_func,
) -> FallbackResult:
    """
    Run multi-stage fallback chain on a store.

    Args:
        store_id: Store UUID
        parser_scores: List of {"parser": "name", "score": 0.9} dicts, sorted by score desc
        re_ingest_func: async function(store_id, parser) -> None
        get_store_func: async function(store_id) -> store with last_run

    Returns:
        FallbackResult with outcome and which parser succeeded
    """
    parsers_to_try = [p["parser"] for p in parser_scores]
    parsers_tried = []

    log.info(f"Starting multi-stage fallback for store {store_id}")
    log.info(f"Parser order: {' → '.join(parsers_to_try)}")

    for i, parser_name in enumerate(parsers_to_try):
        parsers_tried.append(parser_name)
        attempt_num = i + 1

        try:
            log.info(f"Fallback attempt {attempt_num}/{len(parsers_to_try)}: trying {parser_name}")

            # Switch parser and re-ingest
            await re_ingest_func(store_id, parser_name)

            # Wait for ingestion to complete
            import asyncio
            for attempt in range(60):
                await asyncio.sleep(1)
                store = await get_store_func(store_id)
                last_run = store.last_run

                if last_run and last_run.status in ("completed", "partial"):
                    records_created = last_run.records_created or 0
                    records_updated = last_run.records_updated or 0
                    total_records = records_created + records_updated

                    log.info(
                        f"Attempt {attempt_num}: {parser_name} completed. "
                        f"Created: {records_created}, Updated: {records_updated}"
                    )

                    # Check if this parser worked
                    if records_created > 0 or records_updated > 0:
                        log.info(
                            f"✅ SUCCESS: {parser_name} produced {total_records} records "
                            f"on attempt {attempt_num}"
                        )
                        return FallbackResult(
                            success=True,
                            parser_used=parser_name,
                            records_created=records_created,
                            parsers_tried=parsers_tried,
                            reason=f"Parser {parser_name} succeeded with {total_records} records "
                            f"on attempt {attempt_num}/{len(parsers_to_try)}",
                        )

                    # This parser didn't work, try next
                    log.debug(f"Attempt {attempt_num}: {parser_name} returned 0 records, trying next")
                    break

        except Exception as e:
            log.error(f"Fallback attempt {attempt_num} failed: {e}")
            continue

    # All parsers failed
    log.warning(
        f"❌ All {len(parsers_to_try)} parsers failed to extract products "
        f"(tried: {' → '.join(parsers_tried)})"
    )

    return FallbackResult(
        success=False,
        parser_used="",
        records_created=0,
        parsers_tried=parsers_tried,
        reason=f"All {len(parsers_to_try)} parsers returned 0 records. "
        f"Tried in order: {' → '.join(parsers_tried)}. "
        f"Store may have incompatible content or no products.",
    )
