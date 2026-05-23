"""
Feedback loop services for continuous LLM prompt improvement.

Collects quality signals from:
1. Price validation — detects extraction errors through price anomalies
2. Duplicate detection — validates extraction by comparing similar products
3. Manual feedback — admin spot-checks and ratings
4. Pattern learning — tracks typical fields per domain
5. A/B testing — compares prompt versions on real extractions

These signals drive prompt iteration and confidence calibration.
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_feedback import ExtractionFeedback
from app.models.raw_extraction import RawExtraction
from app.models.bean_listing import BeanListing
from app.models.pricing import PriceHistory
from app.models.store import Store

log = logging.getLogger(__name__)


class FeedbackLoopService:
    """
    Collects and aggregates feedback signals on extraction quality.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Price validation feedback ─────────────────────────────────────────

    async def check_price_anomalies(
        self,
        listing_id: UUID,
        new_price_gbp: float,
        tolerance: float = 0.5,
    ) -> Optional[ExtractionFeedback]:
        """
        Detect suspicious price changes that indicate extraction errors.

        Args:
            listing_id: BeanListing ID to check
            new_price_gbp: New price from extraction
            tolerance: Flag if price change > 50% (jump_factor > 1.5 or < 0.67)

        Returns:
            ExtractionFeedback if anomaly detected, else None
        """
        # Get previous price from history
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.bean_listing_id == listing_id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(1)
        )
        prev_history = (await self.session.execute(stmt)).scalar_one_or_none()

        if not prev_history or not prev_history.price_gbp:
            return None

        prev_price = prev_history.price_gbp
        jump_factor = new_price_gbp / prev_price if prev_price > 0 else 1.0

        # Detect anomaly: >50% change
        if jump_factor > (1 + tolerance) or jump_factor < (1 - tolerance):
            feedback = ExtractionFeedback(
                feedback_type="price_anomaly",
                price_previous_gbp=prev_price,
                price_current_gbp=new_price_gbp,
                price_jump_factor=jump_factor,
                signal_strength=min(abs(jump_factor - 1.0), 1.0),  # Strength = magnitude of jump
                created_at=datetime.utcnow(),
            )
            self.session.add(feedback)
            log.warning(
                f"Price anomaly detected: {listing_id} jumped {jump_factor:.2f}x "
                f"(£{prev_price:.2f} → £{new_price_gbp:.2f})"
            )
            return feedback

        return None

    # ── Duplicate detection feedback ──────────────────────────────────────

    async def check_duplicate_extractions(
        self,
        listing_id: UUID,
        extraction_id: UUID,
        similarity_threshold: float = 0.90,
    ) -> Optional[ExtractionFeedback]:
        """
        Find similar products across domains and compare extraction quality.

        Args:
            listing_id: Current BeanListing ID
            extraction_id: Current RawExtraction ID
            similarity_threshold: Match if cosine similarity > 0.90

        Returns:
            ExtractionFeedback if mismatched duplicate found, else None

        Note:
            This is a simplified implementation. Full implementation would:
            - Use vector similarity on embeddings
            - Compare extraction completeness across duplicates
            - Flag if this extraction is lower quality than similar ones
        """
        # For now, this is a placeholder for vector similarity matching
        # In production, would use:
        #   1. Embed current extraction summary
        #   2. Search for similar embeddings across all extractions
        #   3. Compare field completeness across matches
        #   4. Flag if this one is lower quality

        log.debug(f"Duplicate check on {listing_id}: vector similarity matching not yet implemented")
        return None

    # ── Manual feedback ───────────────────────────────────────────────────

    async def record_manual_rating(
        self,
        extraction_id: UUID,
        rating: str,  # "correct" | "partial" | "wrong"
        reviewer_id: str,
        notes: str = "",
    ) -> ExtractionFeedback:
        """
        Record a manual review rating from admin UI.

        Args:
            extraction_id: RawExtraction ID being rated
            rating: "correct", "partial", or "wrong"
            reviewer_id: User ID who did the review
            notes: Optional reviewer notes

        Returns:
            Created ExtractionFeedback record
        """
        if rating not in ("correct", "partial", "wrong"):
            raise ValueError(f"Invalid rating: {rating}")

        feedback = ExtractionFeedback(
            raw_extraction_id=extraction_id,
            feedback_type="manual_review",
            rating=rating,
            reviewed_by_user_id=reviewer_id,
            reviewer_notes=notes,
            signal_strength=1.0,  # Manual reviews are highly reliable
            created_at=datetime.utcnow(),
        )
        self.session.add(feedback)
        log.info(f"Manual rating recorded: {extraction_id} → {rating}")
        return feedback

    # ── Pattern learning ──────────────────────────────────────────────────

    async def get_domain_extraction_patterns(
        self,
        store_id: UUID,
        lookback_days: int = 30,
        min_samples: int = 5,
    ) -> dict:
        """
        Learn typical extraction patterns for a domain.

        Analyzes last N successful extractions from a store to determine:
        - Which fields are typically present
        - Average confidence score
        - Common errors/gaps

        Args:
            store_id: Store ID to analyze
            lookback_days: How far back to look
            min_samples: Minimum extractions needed

        Returns:
            Pattern dict: {
                "typical_fields": ["origin", "process", "roast", ...],
                "typical_confidence": 0.75,
                "common_gaps": ["varietal", "producer"],
                "error_count": 3,
                "sample_count": 12,
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Get recent successful extractions
        stmt = (
            select(RawExtraction)
            .where(
                and_(
                    RawExtraction.store_id == store_id,
                    RawExtraction.validation_status.in_(("valid", "partial")),
                    RawExtraction.created_at >= cutoff_date,
                )
            )
            .order_by(RawExtraction.created_at.desc())
        )
        extractions = (await self.session.execute(stmt)).scalars().all()

        if len(extractions) < min_samples:
            return {
                "typical_fields": [],
                "typical_confidence": 0.0,
                "common_gaps": [],
                "error_count": 0,
                "sample_count": len(extractions),
            }

        # Analyze patterns
        field_presence = {
            "coffee_name": 0,
            "origin_country": 0,
            "origin_region": 0,
            "process": 0,
            "roast_level": 0,
            "varietal": 0,
            "flavour_notes": 0,
            "price_variants": 0,
            "farm_or_estate": 0,
        }

        total_confidence = 0.0
        error_count = 0

        for extraction in extractions:
            if not extraction.extracted_payload:
                continue

            payload = extraction.extracted_payload
            total_confidence += payload.get("confidence", 0.0)

            # Track which fields are present
            if payload.get("coffee_name"):
                field_presence["coffee_name"] += 1
            if payload.get("origin_country"):
                field_presence["origin_country"] += 1
            if payload.get("origin_region"):
                field_presence["origin_region"] += 1
            if payload.get("process"):
                field_presence["process"] += 1
            if payload.get("roast_level"):
                field_presence["roast_level"] += 1
            if payload.get("varietal"):
                field_presence["varietal"] += 1
            if payload.get("flavour_notes"):
                field_presence["flavour_notes"] += 1
            if payload.get("price_variants"):
                field_presence["price_variants"] += 1
            if payload.get("farm_or_estate"):
                field_presence["farm_or_estate"] += 1

            if extraction.validation_status == "partial":
                error_count += 1

        n = len(extractions)
        avg_confidence = total_confidence / n if n > 0 else 0.0

        # Determine "typical" fields (present in >60% of extractions)
        typical_fields = [
            field for field, count in field_presence.items()
            if (count / n) > 0.6
        ]

        # Determine common gaps (present in <30% of extractions)
        common_gaps = [
            field for field, count in field_presence.items()
            if (count / n) < 0.3
        ]

        return {
            "typical_fields": typical_fields,
            "typical_confidence": round(avg_confidence, 2),
            "common_gaps": common_gaps,
            "error_count": error_count,
            "sample_count": n,
        }

    # ── Confidence calibration ────────────────────────────────────────────

    async def measure_confidence_calibration(
        self,
        prompt_version: str,
        lookback_days: int = 30,
        confidence_bucket_width: float = 0.05,
    ) -> list[dict]:
        """
        Measure how well claimed confidence matches actual quality.

        For each confidence bucket (e.g., 0.80–0.85), calculates:
        - Average claimed confidence
        - Fraction of extractions rated as "correct"
        - Well-calibrated if actual ≈ claimed

        Args:
            prompt_version: e.g., "v1.0.0" or "v2.0.0"
            lookback_days: How far back to look
            confidence_bucket_width: Width of each bucket (default 5%)

        Returns:
            List of calibration results:
            [
                {
                    "claimed_confidence": 0.85,
                    "actual_accuracy": 0.78,
                    "sample_count": 15,
                    "is_calibrated": False,  # if |claimed - actual| > 0.10
                }
            ]
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Get extractions with manual feedback
        stmt = (
            select(RawExtraction, ExtractionFeedback)
            .join(
                ExtractionFeedback,
                RawExtraction.id == ExtractionFeedback.raw_extraction_id,
            )
            .where(
                and_(
                    RawExtraction.prompt_version == prompt_version,
                    RawExtraction.created_at >= cutoff_date,
                    ExtractionFeedback.feedback_type == "manual_review",
                )
            )
        )
        results = (await self.session.execute(stmt)).all()

        if not results:
            return []

        # Bucket by claimed confidence
        buckets: dict[float, dict] = {}
        for extraction, feedback in results:
            payload = extraction.extracted_payload or {}
            claimed = payload.get("confidence", 0.0)

            # Round to nearest bucket
            bucket = round(claimed / confidence_bucket_width) * confidence_bucket_width
            bucket = round(bucket, 2)

            if bucket not in buckets:
                buckets[bucket] = {"correct": 0, "total": 0}

            buckets[bucket]["total"] += 1
            if feedback.rating == "correct":
                buckets[bucket]["correct"] += 1

        # Calculate accuracy per bucket
        calibration = []
        for claimed_confidence in sorted(buckets.keys()):
            bucket = buckets[claimed_confidence]
            actual_accuracy = bucket["correct"] / bucket["total"] if bucket["total"] > 0 else 0.0
            is_calibrated = abs(claimed_confidence - actual_accuracy) <= 0.10

            calibration.append({
                "claimed_confidence": claimed_confidence,
                "actual_accuracy": round(actual_accuracy, 2),
                "sample_count": bucket["total"],
                "is_calibrated": is_calibrated,
            })

        return calibration

    # ── A/B testing ───────────────────────────────────────────────────────

    async def record_ab_test(
        self,
        extraction_id_a: UUID,
        extraction_id_b: UUID,
        prompt_version_a: str,
        prompt_version_b: str,
        page_url: str,
    ) -> Optional[ExtractionFeedback]:
        """
        Record A/B test result comparing two prompt versions on same page.

        Args:
            extraction_id_a: Extraction using prompt version A
            extraction_id_b: Extraction using prompt version B
            prompt_version_a: e.g., "v1.0.0"
            prompt_version_b: e.g., "v2.0.0"
            page_url: URL being tested

        Returns:
            ExtractionFeedback with test result
        """
        # Get both extractions
        stmt_a = select(RawExtraction).where(RawExtraction.id == extraction_id_a)
        stmt_b = select(RawExtraction).where(RawExtraction.id == extraction_id_b)

        extraction_a = (await self.session.execute(stmt_a)).scalar_one_or_none()
        extraction_b = (await self.session.execute(stmt_b)).scalar_one_or_none()

        if not extraction_a or not extraction_b:
            return None

        payload_a = extraction_a.extracted_payload or {}
        payload_b = extraction_b.extracted_payload or {}

        confidence_a = payload_a.get("confidence", 0.0)
        confidence_b = payload_b.get("confidence", 0.0)

        # Determine winner (higher confidence = better for now)
        if confidence_a > confidence_b:
            winner = "a"
        elif confidence_b > confidence_a:
            winner = "b"
        else:
            winner = "tie"

        feedback = ExtractionFeedback(
            raw_extraction_id=extraction_id_a,  # Link to first extraction
            feedback_type="ab_test",
            prompt_version_a=prompt_version_a,
            prompt_version_b=prompt_version_b,
            confidence_a=confidence_a,
            confidence_b=confidence_b,
            winner=winner,
            signal_strength=0.8,  # A/B tests are fairly reliable
            created_at=datetime.utcnow(),
        )
        self.session.add(feedback)

        log.info(
            f"A/B test recorded: {prompt_version_a} ({confidence_a:.2f}) vs "
            f"{prompt_version_b} ({confidence_b:.2f}) → {winner} wins"
        )

        return feedback

    # ── Commit all feedback ───────────────────────────────────────────────

    async def commit(self) -> None:
        """Flush all accumulated feedback to database."""
        await self.session.flush()
