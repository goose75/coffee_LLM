"""
CanonicalMatchingService — entity resolution orchestrator.

Pipeline for one bean_listing:
  1. Fetch candidate canonical beans (embedding ANN + exact field pre-filter)
  2. Score each candidate: exact fields + fuzzy title + embedding similarity
  3. Sort by combined confidence score, take best candidate
  4. Apply confidence thresholds:
       ≥ 0.92  → auto-accept (link listing to canonical, mark accepted)
       0.75–0.91 → review queue (create pending canonical_match)
       < 0.75  → new canonical (create new canonical_bean from listing fields)
  5. Write canonical_match row with all signal scores in match_signals_json
  6. If auto-accept or review: optionally update bean_listing.canonical_bean_id

Idempotency:
  Calling match_listing() twice for the same listing is safe.
  If a pending or accepted match already exists, it's returned unchanged.
  Re-running is only triggered explicitly (e.g. after new canonicals added).

Harvest year protection:
  A listing for Ethiopia Konga 2024 CANNOT auto-match Ethiopia Konga 2023
  even if all other signals are perfect. The harvest_score penalty ensures
  combined confidence drops below the auto-accept threshold.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.enums import MatchMethod, ReviewStatus
from app.models.resolution import CanonicalMatch
from app.services.matching.embeddings import generate_listing_embedding, build_embedding_text
from app.services.matching.signals import (
    MatchSignals,
    build_signals,
    combine_signals,
)

log = logging.getLogger(__name__)


@dataclass
class MatchDecision:
    """
    The outcome of running the matching pipeline for one listing.

    outcome: "auto_accepted" | "review_queued" | "new_canonical" | "already_matched" | "error"
    """
    outcome: str
    listing_id: uuid.UUID
    canonical_match_id: uuid.UUID | None = None
    canonical_bean_id: uuid.UUID | None = None
    confidence: float = 0.0
    signals: MatchSignals | None = None
    error: str | None = None

    @property
    def is_new_canonical(self) -> bool:
        return self.outcome == "new_canonical"


class CanonicalMatchingService:
    """
    Runs the entity resolution pipeline for bean listings.

    Usage:
        service = CanonicalMatchingService(session)
        decision = await service.match_listing(listing)
    """

    # Candidate pre-filter: fetch this many nearest neighbours by embedding
    _ANN_LIMIT = 20
    # Minimum fuzzy score to even consider a candidate (avoids wasting time)
    _FUZZY_MIN_THRESHOLD = 0.20

    def __init__(
        self,
        session: AsyncSession,
        auto_accept_threshold: float | None = None,
        review_threshold: float | None = None,
    ) -> None:
        self.session = session
        self.auto_accept = auto_accept_threshold if auto_accept_threshold is not None else settings.CONFIDENCE_AUTO_ACCEPT
        self.review_queue = review_threshold if review_threshold is not None else settings.CONFIDENCE_REVIEW_QUEUE

    # ── Public API ────────────────────────────────────────────────────────────

    async def match_listing(self, listing: BeanListing) -> MatchDecision:
        """
        Run the full matching pipeline for a single BeanListing.
        Returns a MatchDecision describing what was done.
        """
        try:
            # Check if already matched
            existing = await self._get_existing_match(listing.id)
            if existing and existing.review_status in (
                ReviewStatus.accepted, ReviewStatus.pending
            ):
                return MatchDecision(
                    outcome="already_matched",
                    listing_id=listing.id,
                    canonical_match_id=existing.id,
                    canonical_bean_id=existing.proposed_canonical_bean_id,
                    confidence=existing.confidence_score,
                )

            # Generate listing embedding for ANN search
            listing_embedding = await self._get_listing_embedding(listing)

            # Fetch candidate canonical beans
            candidates = await self._fetch_candidates(listing, listing_embedding)

            if not candidates:
                return await self._create_new_canonical(listing, listing_embedding)

            # Score all candidates and pick best
            best_candidate, best_signals = self._score_candidates(
                listing, candidates, listing_embedding
            )

            if best_signals is None or best_signals.combined < self._FUZZY_MIN_THRESHOLD:
                return await self._create_new_canonical(listing, listing_embedding)

            confidence = best_signals.combined

            # Write canonical_match record
            match = await self._write_match(
                listing=listing,
                canonical=best_candidate,
                signals=best_signals,
                confidence=confidence,
            )

            # Apply threshold decision
            if confidence >= self.auto_accept:
                await self._auto_accept(listing, match, best_candidate)
                return MatchDecision(
                    outcome="auto_accepted",
                    listing_id=listing.id,
                    canonical_match_id=match.id,
                    canonical_bean_id=best_candidate.id,
                    confidence=confidence,
                    signals=best_signals,
                )
            else:
                return MatchDecision(
                    outcome="review_queued",
                    listing_id=listing.id,
                    canonical_match_id=match.id,
                    canonical_bean_id=best_candidate.id,
                    confidence=confidence,
                    signals=best_signals,
                )

        except Exception as exc:
            log.error(
                "Matching pipeline failed for listing %s: %s",
                listing.id, exc, exc_info=True
            )
            return MatchDecision(
                outcome="error",
                listing_id=listing.id,
                error=str(exc),
            )

    async def match_batch(
        self, listings: list[BeanListing]
    ) -> list[MatchDecision]:
        """Run matching for multiple listings. Commits after each to limit transaction scope."""
        results = []
        for listing in listings:
            decision = await self.match_listing(listing)
            results.append(decision)
            try:
                await self.session.commit()
            except Exception as exc:
                log.error("Commit failed after matching %s: %s", listing.id, exc)
                await self.session.rollback()
        return results

    async def accept_match(
        self,
        match_id: uuid.UUID,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> CanonicalMatch:
        """Human accepts a pending match — links listing to canonical bean."""
        match = await self._get_match(match_id)
        if match is None:
            raise ValueError(f"Match {match_id} not found")

        match.review_status = ReviewStatus.accepted
        match.reviewed_by = user_id
        match.review_notes = notes
        match.reviewed_at = datetime.now(timezone.utc)

        # Link the listing and enrich canonical with extracted data
        listing = await self.session.get(BeanListing, match.bean_listing_id)
        if listing:
            listing.canonical_bean_id = match.proposed_canonical_bean_id
            # Enrich the canonical with extracted fields from this listing
            canonical = await self.session.get(CanonicalBean, match.proposed_canonical_bean_id)
            if canonical:
                await self._enrich_canonical_from_listing(canonical, listing)

        await self.session.commit()
        return match

    async def reject_match(
        self,
        match_id: uuid.UUID,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> CanonicalMatch:
        """Human rejects a pending match — listing remains unlinked."""
        match = await self._get_match(match_id)
        if match is None:
            raise ValueError(f"Match {match_id} not found")

        match.review_status = ReviewStatus.rejected
        match.reviewed_by = user_id
        match.review_notes = notes
        match.reviewed_at = datetime.now(timezone.utc)

        await self.session.commit()
        return match

    # ── Bulk operations ───────────────────────────────────────────────────────

    async def bulk_accept(
        self,
        match_ids: list[uuid.UUID],
        user_id: str | None = None,
        notes: str | None = None,
    ) -> tuple[int, list[str]]:
        """
        Accept many matches in a single transaction.

        Returns (accepted_count, skipped_ids). A match is "skipped" if it
        doesn't exist or isn't currently pending — this is a safe operation
        that won't reverse already-completed reviews.
        """
        from sqlalchemy import select
        if not match_ids:
            return 0, []
        stmt = select(CanonicalMatch).where(CanonicalMatch.id.in_(match_ids))
        rows = (await self.session.execute(stmt)).scalars().all()
        found_ids = {r.id for r in rows}
        skipped = [str(mid) for mid in match_ids if mid not in found_ids]

        accepted = 0
        now = datetime.now(timezone.utc)
        for match in rows:
            current_status = match.review_status
            current_value = current_status.value if hasattr(current_status, "value") else str(current_status)
            if current_value != "pending":
                skipped.append(str(match.id))
                continue
            match.review_status = ReviewStatus.accepted
            match.reviewed_by = user_id
            match.review_notes = notes
            match.reviewed_at = now
            listing = await self.session.get(BeanListing, match.bean_listing_id)
            if listing:
                listing.canonical_bean_id = match.proposed_canonical_bean_id
                # Enrich the canonical with extracted fields from this listing
                canonical = await self.session.get(CanonicalBean, match.proposed_canonical_bean_id)
                if canonical:
                    await self._enrich_canonical_from_listing(canonical, listing)
            accepted += 1

        await self.session.commit()
        return accepted, skipped

    async def bulk_reject(
        self,
        match_ids: list[uuid.UUID],
        user_id: str | None = None,
        notes: str | None = None,
    ) -> tuple[int, list[str]]:
        """Reject many matches in a single transaction. See bulk_accept docstring."""
        from sqlalchemy import select
        if not match_ids:
            return 0, []
        stmt = select(CanonicalMatch).where(CanonicalMatch.id.in_(match_ids))
        rows = (await self.session.execute(stmt)).scalars().all()
        found_ids = {r.id for r in rows}
        skipped = [str(mid) for mid in match_ids if mid not in found_ids]

        rejected = 0
        now = datetime.now(timezone.utc)
        for match in rows:
            current_status = match.review_status
            current_value = current_status.value if hasattr(current_status, "value") else str(current_status)
            if current_value != "pending":
                skipped.append(str(match.id))
                continue
            match.review_status = ReviewStatus.rejected
            match.reviewed_by = user_id
            match.review_notes = notes
            match.reviewed_at = now
            rejected += 1

        await self.session.commit()
        return rejected, skipped

    async def bulk_accept_by_filter(
        self,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        match_method: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
        limit: int = 1000,
    ) -> tuple[int, list[str]]:
        """Accept all pending matches matching the filter, capped at `limit`."""
        from sqlalchemy import select
        stmt = select(CanonicalMatch.id).where(CanonicalMatch.review_status == "pending")
        if min_confidence is not None:
            stmt = stmt.where(CanonicalMatch.confidence_score >= min_confidence)
        if max_confidence is not None:
            stmt = stmt.where(CanonicalMatch.confidence_score <= max_confidence)
        if match_method:
            stmt = stmt.where(CanonicalMatch.match_method == match_method)
        stmt = stmt.limit(limit)
        ids = [row[0] for row in (await self.session.execute(stmt)).all()]
        return await self.bulk_accept(ids, user_id=user_id, notes=notes)

    async def bulk_reject_by_filter(
        self,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        match_method: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
        limit: int = 1000,
    ) -> tuple[int, list[str]]:
        """Reject all pending matches matching the filter, capped at `limit`."""
        from sqlalchemy import select
        stmt = select(CanonicalMatch.id).where(CanonicalMatch.review_status == "pending")
        if min_confidence is not None:
            stmt = stmt.where(CanonicalMatch.confidence_score >= min_confidence)
        if max_confidence is not None:
            stmt = stmt.where(CanonicalMatch.confidence_score <= max_confidence)
        if match_method:
            stmt = stmt.where(CanonicalMatch.match_method == match_method)
        stmt = stmt.limit(limit)
        ids = [row[0] for row in (await self.session.execute(stmt)).all()]
        return await self.bulk_reject(ids, user_id=user_id, notes=notes)

    async def enrich_all_canonicals(self, limit: int = 10000) -> tuple[int, int]:
        """
        One-time enrichment: for all accepted matches, enrich canonical beans
        with extracted fields from their matched listings.

        Returns (enriched_count, skipped_count)
        """
        from sqlalchemy import select
        # Fetch all accepted matches with their listings and canonicals
        stmt = (
            select(CanonicalMatch, BeanListing, CanonicalBean)
            .where(CanonicalMatch.review_status == ReviewStatus.accepted)
            .join(BeanListing, CanonicalMatch.bean_listing_id == BeanListing.id)
            .join(CanonicalBean, CanonicalMatch.proposed_canonical_bean_id == CanonicalBean.id)
            .limit(limit)
        )
        results = (await self.session.execute(stmt)).all()

        enriched = 0
        skipped = 0

        for match, listing, canonical in results:
            try:
                # Try to enrich - will only update if fields are missing
                await self._enrich_canonical_from_listing(canonical, listing)
                enriched += 1
            except Exception as exc:
                log.error(
                    "Failed to enrich canonical %s from listing %s: %s",
                    canonical.id, listing.id, exc
                )
                skipped += 1

        await self.session.commit()
        return enriched, skipped

    # ── Candidate retrieval ───────────────────────────────────────────────────

    async def _fetch_candidates(
        self,
        listing: BeanListing,
        listing_embedding: list[float] | None,
    ) -> list[CanonicalBean]:
        """
        Fetch candidate canonical beans for comparison.

        Strategy:
          1. If embedding available: ANN search for top-N nearest neighbours
          2. If origin_country known: filter candidates to same country (fast path)
          3. Fall back to all canonicals (slow but correct for small datasets)
        """
        if listing_embedding and any(v != 0.0 for v in listing_embedding):
            return await self._ann_candidates(listing_embedding, listing)
        return await self._structured_candidates(listing)

    async def _ann_candidates(
        self,
        embedding: list[float],
        listing: BeanListing,
    ) -> list[CanonicalBean]:
        """pgvector approximate nearest-neighbour search."""
        try:
            from pgvector.sqlalchemy import Vector
            vector_literal = str(embedding)
            stmt = (
                select(CanonicalBean)
                .where(CanonicalBean.embedding_vector.isnot(None))
                .order_by(
                    CanonicalBean.embedding_vector.op("<->")(
                        func.cast(vector_literal, Vector(len(embedding)))
                    )
                )
                .limit(self._ANN_LIMIT)
            )
            result = await self.session.execute(stmt)
            candidates = list(result.scalars().all())
            if candidates:
                return candidates
        except Exception as exc:
            log.warning("ANN search failed, falling back to structured: %s", exc)

        return await self._structured_candidates(listing)

    async def _structured_candidates(self, listing: BeanListing) -> list[CanonicalBean]:
        """
        Structured pre-filter: filter by origin_country if available,
        otherwise return all canonicals (for small datasets this is fine).
        """
        stmt = select(CanonicalBean)

        origin = listing.origin_label_raw or ""
        if origin:
            # Try exact country match first
            stmt = stmt.where(
                CanonicalBean.origin_country.ilike(f"%{origin.split(',')[0].strip()}%")
            )

        stmt = stmt.limit(100)  # reasonable upper bound
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_candidates(
        self,
        listing: BeanListing,
        candidates: list[CanonicalBean],
        listing_embedding: list[float] | None,
    ) -> tuple[CanonicalBean | None, MatchSignals | None]:
        """Score all candidates and return the best match."""
        best: tuple[CanonicalBean, MatchSignals] | None = None
        best_score = -1.0

        for candidate in candidates:
            cand_embedding = None
            if candidate.embedding_vector is not None:
                cand_embedding = list(candidate.embedding_vector)

            signals = build_signals(
                listing=listing,
                canonical=candidate,
                listing_embedding=listing_embedding,
                canonical_embedding=cand_embedding,
            )

            if signals.combined > best_score:
                best_score = signals.combined
                best = (candidate, signals)

        if best is None:
            return None, None
        return best[0], best[1]

    # ── DB operations ─────────────────────────────────────────────────────────

    async def _get_listing_embedding(self, listing: BeanListing) -> list[float] | None:
        """
        Generate an embedding for a listing.

        Uses OpenAI's text-embedding-3-small when OPENAI_API_KEY is set,
        otherwise falls back to the deterministic local hash-based embedding
        in embeddings.py — that fallback produces non-zero, reproducible
        1536-dim vectors and lets the ANN candidate search keep working in
        development without any external API key.
        """
        try:
            openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""
            return await generate_listing_embedding(
                listing,
                api_key=openai_key,
                model=getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small"),
            )
        except Exception as exc:
            log.debug("Could not generate listing embedding: %s", exc)
            return None

    async def _write_match(
        self,
        listing: BeanListing,
        canonical: CanonicalBean,
        signals: MatchSignals,
        confidence: float,
    ) -> CanonicalMatch:
        """Create and persist a canonical_match record."""
        method = self._determine_method(signals)

        match = CanonicalMatch(
            bean_listing_id=listing.id,
            proposed_canonical_bean_id=canonical.id,
            match_method=method,
            confidence_score=confidence,
            review_status=ReviewStatus.pending,
        )
        # Store signal breakdown as JSONB
        match.match_signals_json = signals.to_dict()

        self.session.add(match)
        await self.session.flush()
        return match

    async def _auto_accept(
        self,
        listing: BeanListing,
        match: CanonicalMatch,
        canonical: CanonicalBean,
    ) -> None:
        """Mark match as system-accepted, link listing to canonical, and enrich canonical with extracted data."""
        match.review_status = ReviewStatus.accepted
        match.reviewed_at = datetime.now(timezone.utc)
        listing.canonical_bean_id = canonical.id
        # Enrich canonical with extracted fields from this listing
        await self._enrich_canonical_from_listing(canonical, listing)

    async def _create_new_canonical(
        self,
        listing: BeanListing,
        embedding: list[float] | None = None,
    ) -> MatchDecision:
        """Create a new canonical bean from this listing's normalised fields."""
        canonical = CanonicalBean(
            canonical_name=listing.raw_title,
            origin_country=self._extract_country(listing),
            process=self._extract_process(listing),
            roast_level=self._extract_roast(listing),
        )
        if embedding:
            canonical.embedding_vector = embedding

        self.session.add(canonical)
        await self.session.flush()

        # Create a self-referential match at confidence 0.0 (new entity)
        match = CanonicalMatch(
            bean_listing_id=listing.id,
            proposed_canonical_bean_id=canonical.id,
            match_method=MatchMethod.manual,
            confidence_score=0.0,
            review_status=ReviewStatus.accepted,  # Auto-accept: it IS this bean
        )
        match.match_signals_json = {"reason": "new_canonical", "combined": 0.0}
        self.session.add(match)
        listing.canonical_bean_id = canonical.id
        await self.session.flush()

        return MatchDecision(
            outcome="new_canonical",
            listing_id=listing.id,
            canonical_match_id=match.id,
            canonical_bean_id=canonical.id,
            confidence=0.0,
        )

    async def _get_existing_match(self, listing_id: uuid.UUID) -> CanonicalMatch | None:
        result = await self.session.execute(
            select(CanonicalMatch)
            .where(CanonicalMatch.bean_listing_id == listing_id)
            .order_by(CanonicalMatch.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_match(self, match_id: uuid.UUID) -> CanonicalMatch | None:
        result = await self.session.execute(
            select(CanonicalMatch).where(CanonicalMatch.id == match_id)
        )
        return result.scalar_one_or_none()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _determine_method(self, signals: MatchSignals) -> MatchMethod:
        """Determine which method label to record based on which signals fired."""
        if signals.exact_score > 0.8 and signals.fuzzy_score > 0.8:
            return MatchMethod.combined
        if signals.exact_score > 0.8:
            return MatchMethod.exact
        if signals.embedding_score > 0.85:
            return MatchMethod.embedding
        if signals.fuzzy_score > 0.6:
            return MatchMethod.fuzzy
        return MatchMethod.combined

    def _extract_country(self, listing: BeanListing) -> str | None:
        raw = listing.origin_label_raw or ""
        if raw:
            parts = raw.split(",")
            return parts[0].strip() or None
        return None

    def _extract_process(self, listing: BeanListing):
        raw = listing.process_label_raw or ""
        if not raw:
            return None
        from app.models.enums import Process
        raw_lower = raw.lower().strip()
        for p in Process:
            if p.value in raw_lower or raw_lower in p.value:
                return p
        return None

    def _extract_roast(self, listing: BeanListing):
        raw = listing.roast_label_raw or ""
        if not raw:
            return None
        from app.models.enums import RoastLevel
        raw_lower = raw.lower().strip()
        for r in RoastLevel:
            if r.value in raw_lower or raw_lower in r.value:
                return r
        return None

    async def _enrich_canonical_from_listing(
        self,
        canonical: CanonicalBean,
        listing: BeanListing,
    ) -> None:
        """
        Update canonical_bean fields with extracted data from a listing.

        Called whenever a listing is matched to a canonical (auto-accept or after review).
        Updates origin_country, process, and roast_level with values from the listing.
        Overwrites existing values to ensure canonicals have the best available data.
        """
        # Extract and update origin_country
        if listing.origin_label_raw:
            extracted = self._extract_country(listing)
            if extracted:
                canonical.origin_country = extracted

        # Extract and update process
        if listing.process_label_raw:
            extracted = self._extract_process(listing)
            if extracted:
                canonical.process = extracted

        # Extract and update roast_level
        if listing.roast_label_raw:
            extracted = self._extract_roast(listing)
            if extracted:
                canonical.roast_level = extracted
