"""
Error Recovery & Learning Service

Analyzes ingestion run failures and automatically corrects parser_strategy misclassifications.
This service enables the system to learn from failures and self-correct.

Patterns recognized:
- 404 on /products.json → Shopify misdetection, should be html
- Timeout on products.json → API disabled, should be html
- Connection refused → Platform error, should be html
- 403/401 on Shopify API → Shopify auth disabled, should be html

Future enhancements:
- LLM-assisted error categorization
- Webhook notifications for manual review
- A/B testing parser strategies
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TypedDict

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ParserStrategy, RunStatus
from app.models.ingestion_run import IngestionRun
from app.models.store import Store

logger = logging.getLogger(__name__)


class ErrorPattern(TypedDict):
    """Pattern recognized in an error message."""
    pattern: str
    suggested_strategy: str
    confidence: float
    reason: str


ERROR_PATTERNS: list[ErrorPattern] = [
    {
        "pattern": "404",
        "suggested_strategy": "html",
        "confidence": 0.95,
        "reason": "Shopify API endpoint not found - likely not Shopify",
    },
    {
        "pattern": "products.json",
        "suggested_strategy": "html",
        "confidence": 0.90,
        "reason": "Shopify products endpoint failed",
    },
    {
        "pattern": "myshopify.com",
        "suggested_strategy": "html",
        "confidence": 0.99,
        "reason": "Redirect to myshopify but no products API",
    },
    {
        "pattern": "403",
        "suggested_strategy": "html",
        "confidence": 0.85,
        "reason": "Access forbidden - API disabled or authentication required",
    },
    {
        "pattern": "401",
        "suggested_strategy": "html",
        "confidence": 0.80,
        "reason": "Unauthorized - authentication issue",
    },
    {
        "pattern": "Connection refused",
        "suggested_strategy": "html",
        "confidence": 0.90,
        "reason": "Platform API not reachable",
    },
    {
        "pattern": "timeout",
        "suggested_strategy": "html",
        "confidence": 0.75,
        "reason": "API timeout - likely platform issue",
    },
]


class ErrorRecoveryService:
    """
    Analyzes ingestion failures and suggests/applies corrections.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze_failures(self, hours: int = 24) -> dict:
        """
        Analyze recent failures and return suggested corrections.

        Args:
            hours: Look back this many hours for failures

        Returns:
            {
                'analyzed': N,
                'corrections': [
                    {
                        'domain': 'example.com',
                        'store_id': 'uuid',
                        'current_strategy': 'shopify',
                        'suggested_strategy': 'html',
                        'confidence': 0.95,
                        'reason': 'Shopify API endpoint not found',
                        'error_messages': ['...'],
                        'auto_applied': False
                    },
                    ...
                ]
            }
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Find recent failed runs
        stmt = (
            select(IngestionRun)
            .where(
                and_(
                    IngestionRun.status == RunStatus.failed,
                    IngestionRun.started_at >= cutoff,
                )
            )
            .order_by(desc(IngestionRun.started_at))
        )
        failed_runs = (await self.session.execute(stmt)).scalars().all()

        # Analyze each failure
        corrections = []
        for run in failed_runs:
            if not run.store_id or not run.errors:
                continue

            store_stmt = select(Store).where(Store.id == run.store_id)
            store = (await self.session.execute(store_stmt)).scalar_one_or_none()
            if not store:
                continue

            # Extract error messages
            error_messages = [
                (e.get("message", "") if isinstance(e, dict) else str(e))
                for e in (run.errors or [])
            ]
            combined_errors = " ".join(error_messages).lower()

            # Match against patterns
            for pattern_info in ERROR_PATTERNS:
                if pattern_info["pattern"].lower() in combined_errors:
                    suggested_strategy = pattern_info["suggested_strategy"]

                    # Only suggest if current strategy is shopify
                    if store.parser_strategy.value != suggested_strategy:
                        corrections.append(
                            {
                                "domain": store.domain,
                                "store_id": str(store.id),
                                "current_strategy": store.parser_strategy.value,
                                "suggested_strategy": suggested_strategy,
                                "confidence": pattern_info["confidence"],
                                "reason": pattern_info["reason"],
                                "error_messages": error_messages[:3],
                                "auto_applied": False,
                            }
                        )
                        break  # Use first matching pattern

        return {
            "analyzed": len(failed_runs),
            "corrections": corrections,
        }

    async def auto_correct(self, min_confidence: float = 0.95) -> dict:
        """
        Automatically apply corrections to misclassified stores.

        IMPORTANT: Only applies corrections with VERY HIGH confidence (default 0.95+).
        Only corrects from shopify → html if:
        1. Confidence >= min_confidence (default 0.95 = 95%)
        2. AND the store is already marked as shopify
        3. AND there's clear evidence it's not Shopify (404 or specific API errors)

        Does NOT auto-correct:
        - To strategies without extraction pipelines (currently only shopify has one)
        - If confidence is below threshold (too risky)

        Args:
            min_confidence: Only auto-correct if confidence >= this threshold (default 0.95)

        Returns:
            {
                'applied': N,
                'flagged_for_review': N,
                'changes': [...],
                'skipped': [...]
            }
        """
        analysis = await self.analyze_failures(hours=24)
        changes = []
        flagged = []
        skipped = []

        # Available extraction pipelines
        # shopify: ShopifyIngestionPipeline (product_catalog.json)
        # html: HtmlIngestionPipeline (schema.org → html rules → browser → llm)
        # schema_org: SchemaOrgIngestionPipeline (JSON-LD extraction)
        # llm: LLMParser fallback (via ExtractionService)
        available_strategies = ["shopify", "html", "schema_org", "llm"]

        for correction in analysis["corrections"]:
            domain = correction["domain"]
            suggested = correction["suggested_strategy"]
            confidence = correction["confidence"]

            # Skip if confidence below threshold
            if confidence < min_confidence:
                skipped.append(
                    {
                        "domain": domain,
                        "reason": f"Confidence {confidence} below threshold {min_confidence}",
                    }
                )
                continue

            # SAFETY CHECK: Only downgrade Shopify if EXTREMELY confident (404 = 95%)
            # This prevents downgrading working stores to broken ones
            if suggested not in available_strategies:
                flagged.append(
                    {
                        "domain": domain,
                        "current": correction["current_strategy"],
                        "suggested": suggested,
                        "reason": f"Target strategy '{suggested}' has no extraction pipeline yet",
                        "action": "Flagged for manual review",
                    }
                )
                continue

            store_id_str = correction["store_id"]

            # Update the store
            stmt = select(Store).where(Store.id == store_id_str)
            store = (await self.session.execute(stmt)).scalar_one_or_none()

            if store:
                old_strategy = store.parser_strategy.value
                store.parser_strategy = ParserStrategy(suggested)
                store.source_type = suggested
                store.updated_at = datetime.utcnow()

                changes.append(
                    {
                        "domain": store.domain,
                        "from": old_strategy,
                        "to": suggested,
                        "reason": correction["reason"],
                        "confidence": correction["confidence"],
                    }
                )

                logger.info(
                    f"Auto-corrected {store.domain}: {old_strategy} → {suggested} "
                    f"(confidence: {correction['confidence']}, reason: {correction['reason']})"
                )

        # Commit changes
        if changes:
            await self.session.commit()

        return {
            "applied": len(changes),
            "flagged_for_review": len(flagged),
            "skipped": len(skipped),
            "changes": changes,
            "flagged": flagged,
        }

    async def get_correction_summary(self) -> dict:
        """
        Get a summary of recent corrections and error patterns.

        Returns:
            {
                'total_failures_24h': N,
                'top_error_patterns': [
                    {
                        'pattern': '404',
                        'count': 10,
                        'affected_stores': ['domain1', 'domain2', ...]
                    },
                    ...
                ],
                'affected_parser_strategies': {
                    'shopify': 10,
                    'html': 2,
                    ...
                }
            }
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)

        # Find recent failures
        stmt = (
            select(IngestionRun)
            .where(
                and_(
                    IngestionRun.status == RunStatus.failed,
                    IngestionRun.started_at >= cutoff,
                )
            )
            .order_by(desc(IngestionRun.started_at))
        )
        failed_runs = (await self.session.execute(stmt)).scalars().all()

        # Count patterns
        pattern_counts = {}
        affected_stores = {}
        strategy_counts = {}

        for run in failed_runs:
            if not run.store_id or not run.errors:
                continue

            store_stmt = select(Store).where(Store.id == run.store_id)
            store = (await self.session.execute(store_stmt)).scalar_one_or_none()
            if not store:
                continue

            error_messages = [
                (e.get("message", "") if isinstance(e, dict) else str(e))
                for e in (run.errors or [])
            ]
            combined_errors = " ".join(error_messages).lower()

            # Update strategy counts
            strategy = store.parser_strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

            # Match patterns
            for pattern_info in ERROR_PATTERNS:
                if pattern_info["pattern"].lower() in combined_errors:
                    pattern = pattern_info["pattern"]
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

                    if pattern not in affected_stores:
                        affected_stores[pattern] = []
                    affected_stores[pattern].append(store.domain)
                    break

        return {
            "total_failures_24h": len(failed_runs),
            "top_error_patterns": [
                {
                    "pattern": pattern,
                    "count": count,
                    "affected_stores": list(set(affected_stores.get(pattern, [])))[:5],
                }
                for pattern, count in sorted(
                    pattern_counts.items(), key=lambda x: -x[1]
                )[:10]
            ],
            "affected_parser_strategies": strategy_counts,
        }
