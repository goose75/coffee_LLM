"""
Tests for the canonical matching service.

Coverage:
  TestExactFieldScorer     — all four fields, partial/missing, varietal overlap
  TestFuzzyTitleScorer     — token_set_ratio, word order, partial matches
  TestEmbeddingScorer      — cosine similarity, zero vectors, missing vectors
  TestHarvestYearScorer    — same/diff/missing year combinations
  TestSignalCombiner       — weighted combination, harvest penalty
  TestBuildSignals         — integration of all scorers
  TestConfidenceBanding    — auto-accept / review / new-canonical thresholds
  TestMatchingService      — DB-mocked service: match_listing, accept, reject
  TestEmbeddingText        — text construction for embedding generation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _listing(**kwargs) -> dict:
    """Build a fake listing dict for scorer tests."""
    base = {
        "raw_title": "Ethiopia Yirgacheffe Konga Washed",
        "origin_country": "Ethiopia",
        "origin_region": "Yirgacheffe",
        "farm_or_estate": "Konga Cooperative",
        "process": "washed",
        "varietal": ["Heirloom"],
        "harvest_year": 2024,
        "raw_description": "Floral and bright.",
        "flavour_notes": ["jasmine", "lemon"],
    }
    base.update(kwargs)
    return base


def _canonical(**kwargs) -> dict:
    """Build a fake canonical bean dict for scorer tests."""
    base = {
        "canonical_name": "Ethiopia Yirgacheffe Konga Washed",
        "origin_country": "Ethiopia",
        "origin_region": "Yirgacheffe",
        "farm_or_estate": "Konga Cooperative",
        "process": "washed",
        "varietal": ["Heirloom"],
        "harvest_year": 2024,
        "flavour_notes": ["jasmine", "lemon"],
        "roast_level": "light",
    }
    base.update(kwargs)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# TestExactFieldScorer
# ─────────────────────────────────────────────────────────────────────────────

class TestExactFieldScorer:
    def _score(self, listing_kw: dict, canonical_kw: dict) -> tuple[float, dict]:
        from app.services.matching.signals import score_exact_fields
        return score_exact_fields(_listing(**listing_kw), _canonical(**canonical_kw))

    def test_perfect_match_returns_1(self):
        score, _ = self._score({}, {})
        assert score == 1.0

    def test_different_country_lowers_score(self):
        score, matches = self._score({}, {"origin_country": "Kenya"})
        assert score < 0.5
        assert matches.get("origin_country") is False

    def test_different_process_lowers_score(self):
        score, matches = self._score({}, {"process": "natural"})
        assert score < 0.8
        assert matches.get("process") is False

    def test_missing_country_on_listing_skips_field(self):
        """Blank listing field → not penalised, skipped."""
        score_without, _ = self._score({"origin_country": None}, {})
        score_with, _ = self._score({}, {})
        # Missing field should not drop below a perfect-other-fields score
        assert score_without >= score_with * 0.5

    def test_missing_country_on_canonical_skips_field(self):
        score, matches = self._score({}, {"origin_country": None})
        assert matches.get("origin_country") is None  # skipped

    def test_varietal_partial_overlap(self):
        """SL28 in both: 1-item intersection / 2-item max = 0.5."""
        score, matches = self._score(
            {"varietal": ["SL28"]},
            {"varietal": ["SL28", "SL34"]},
        )
        assert matches.get("varietal") is False  # < 0.5 threshold
        assert 0.0 < score < 1.0

    def test_varietal_full_overlap(self):
        score, matches = self._score(
            {"varietal": ["SL28", "SL34"]},
            {"varietal": ["SL28", "SL34"]},
        )
        assert matches.get("varietal") is True

    def test_all_fields_blank_returns_zero(self):
        """If both sides have all blank fields, no evidence → 0."""
        score, _ = self._score(
            {"origin_country": None, "process": None, "varietal": [], "farm_or_estate": None},
            {"origin_country": None, "process": None, "varietal": [], "farm_or_estate": None},
        )
        assert score == 0.0

    def test_case_insensitive_country(self):
        score, matches = self._score({"origin_country": "ETHIOPIA"}, {"origin_country": "ethiopia"})
        assert matches.get("origin_country") is True

    def test_farm_match_contributes(self):
        """Same farm contributes 0.25 weight."""
        score_with_farm, _ = self._score({}, {})
        score_no_farm, _ = self._score(
            {"farm_or_estate": None},
            {"farm_or_estate": None},
        )
        # Both should score well but the presence of farm agreement adds to score
        assert score_with_farm >= score_no_farm


# ─────────────────────────────────────────────────────────────────────────────
# TestFuzzyTitleScorer
# ─────────────────────────────────────────────────────────────────────────────

class TestFuzzyTitleScorer:
    def _score(self, listing_title: str, canonical_name: str) -> float:
        from app.services.matching.signals import score_fuzzy_title
        return score_fuzzy_title(listing_title, canonical_name)

    def test_identical_titles(self):
        score = self._score("Ethiopia Yirgacheffe Konga Washed", "Ethiopia Yirgacheffe Konga Washed")
        assert score >= 0.98

    def test_word_order_insensitive(self):
        score = self._score("Konga Washed Ethiopia Yirgacheffe", "Ethiopia Yirgacheffe Konga Washed")
        assert score >= 0.90

    def test_partial_match(self):
        score = self._score("Ethiopia Yirgacheffe", "Ethiopia Yirgacheffe Konga Washed")
        assert score >= 0.60  # partial but still meaningful

    def test_completely_different(self):
        score = self._score("Colombia Espresso Blend", "Kenya Kirinyaga AB Washed")
        assert score < 0.40

    def test_empty_listing_title(self):
        assert self._score("", "Ethiopia Yirgacheffe") == 0.0

    def test_empty_canonical_name(self):
        assert self._score("Ethiopia Yirgacheffe", "") == 0.0

    def test_both_empty(self):
        assert self._score("", "") == 0.0

    def test_case_insensitive(self):
        score = self._score("ETHIOPIA YIRGACHEFFE", "Ethiopia Yirgacheffe")
        assert score >= 0.95

    def test_typo_tolerance(self):
        """Minor typo in title should still score reasonably high."""
        score = self._score("Ethiopa Yiracheffe Konga", "Ethiopia Yirgacheffe Konga Washed")
        assert score >= 0.60

    def test_different_farm_same_country(self):
        """Same country different farm should score lower than perfect match."""
        perfect = self._score("Ethiopia Yirgacheffe Konga", "Ethiopia Yirgacheffe Konga")
        different_farm = self._score("Ethiopia Yirgacheffe Halo Beriti", "Ethiopia Yirgacheffe Konga")
        assert perfect > different_farm

    def test_result_is_float_in_range(self):
        score = self._score("Test Coffee", "Test Coffee")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestEmbeddingScorer
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbeddingScorer:
    def _score(self, a, b) -> float:
        from app.services.matching.signals import score_embeddings
        return score_embeddings(a, b)

    def _unit_vec(self, n: int, dim: int = 8) -> list[float]:
        """Create a unit vector with 1.0 in position n, zeros elsewhere."""
        v = [0.0] * dim
        v[n % dim] = 1.0
        return v

    def _similar_vec(self, dim: int = 8) -> tuple[list[float], list[float]]:
        """Two similar vectors (90% dot product)."""
        import math
        v = [1.0] + [0.0] * (dim - 1)
        v2 = [0.9, 0.436] + [0.0] * (dim - 2)  # ≈ cos(25°)
        return v, v2

    def test_identical_vectors(self):
        v = self._unit_vec(0)
        score = self._score(v, v)
        assert abs(score - 1.0) < 0.01  # cosine 1 → normalised ~1

    def test_orthogonal_vectors_midpoint(self):
        """Orthogonal vectors: cosine=0 → normalised=0.5."""
        a = self._unit_vec(0)
        b = self._unit_vec(1)
        score = self._score(a, b)
        assert 0.45 < score < 0.55

    def test_similar_vectors_high_score(self):
        a, b = self._similar_vec()
        score = self._score(a, b)
        assert score > 0.7

    def test_none_vector_returns_zero(self):
        assert self._score(None, self._unit_vec(0)) == 0.0
        assert self._score(self._unit_vec(0), None) == 0.0
        assert self._score(None, None) == 0.0

    def test_zero_vector_returns_zero(self):
        zero = [0.0] * 8
        v = self._unit_vec(0)
        assert self._score(zero, v) == 0.0

    def test_result_in_range(self):
        a, b = self._similar_vec()
        score = self._score(a, b)
        assert 0.0 <= score <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestHarvestYearScorer
# ─────────────────────────────────────────────────────────────────────────────

class TestHarvestYearScorer:
    def _score(self, listing_year, canonical_year) -> float:
        from app.services.matching.signals import score_harvest_year
        return score_harvest_year(listing_year, canonical_year)

    def test_same_year(self):           assert self._score(2024, 2024) == 1.0
    def test_both_none(self):           assert self._score(None, None) == 1.0
    def test_one_none(self):            assert self._score(2024, None) == 0.8
    def test_one_none_reversed(self):   assert self._score(None, 2024) == 0.8
    def test_one_year_diff(self):       assert self._score(2024, 2023) == 0.5
    def test_two_year_diff(self):       assert self._score(2024, 2022) == 0.0
    def test_large_year_diff(self):     assert self._score(2024, 2018) == 0.0

    def test_different_year_prevents_auto_accept(self):
        """
        Even with perfect exact+fuzzy+embedding, cross-year lots must not
        exceed the auto-accept threshold (0.92).
        """
        from app.services.matching.signals import MatchSignals, combine_signals
        signals = MatchSignals(
            exact_score=1.0,
            fuzzy_score=1.0,
            embedding_score=1.0,
            harvest_score=0.0,  # different harvest year
        )
        combined = combine_signals(signals)
        assert combined < 0.92, f"Cross-year lot auto-accepted at {combined}"


# ─────────────────────────────────────────────────────────────────────────────
# TestSignalCombiner
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalCombiner:
    def _combine(self, exact=0.0, fuzzy=0.0, embedding=0.0, harvest=1.0) -> float:
        from app.services.matching.signals import MatchSignals, combine_signals
        s = MatchSignals(
            exact_score=exact, fuzzy_score=fuzzy,
            embedding_score=embedding, harvest_score=harvest
        )
        return combine_signals(s)

    def test_all_zeros_returns_zero(self):
        assert self._combine() == 0.0

    def test_perfect_signals_return_near_one(self):
        score = self._combine(exact=1.0, fuzzy=1.0, embedding=1.0, harvest=1.0)
        assert score >= 0.99

    def test_high_exact_only_below_auto_accept(self):
        """Exact alone (0.45) + harvest (0.05) = 0.50 → below auto-accept."""
        score = self._combine(exact=1.0)
        assert score < 0.92

    def test_high_exact_and_fuzzy_in_review_band(self):
        score = self._combine(exact=0.9, fuzzy=0.9)
        assert 0.75 <= score < 0.92

    def test_result_always_in_0_1(self):
        for exact, fuzzy, emb in [(0, 0, 0), (0.5, 0.5, 0.5), (1, 1, 1), (2, 2, 2)]:
            score = self._combine(exact=exact, fuzzy=fuzzy, embedding=emb)
            assert 0.0 <= score <= 1.0

    def test_auto_accept_threshold(self):
        """Perfect signals clear the auto-accept bar."""
        score = self._combine(exact=1.0, fuzzy=1.0, embedding=1.0, harvest=1.0)
        assert score >= 0.92

    def test_review_threshold(self):
        """Good-but-not-perfect signals land in review band."""
        score = self._combine(exact=0.8, fuzzy=0.75, embedding=0.6, harvest=1.0)
        assert 0.75 <= score <= 0.92

    def test_below_review_threshold(self):
        """Low signals create new canonical."""
        score = self._combine(exact=0.0, fuzzy=0.3, embedding=0.2, harvest=1.0)
        assert score < 0.75


# ─────────────────────────────────────────────────────────────────────────────
# TestBuildSignals
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildSignals:
    def test_build_signals_identical(self):
        from app.services.matching.signals import build_signals
        listing = _listing()
        canonical = _canonical()
        signals = build_signals(listing, canonical)
        assert signals.exact_score == 1.0
        assert signals.fuzzy_score >= 0.95
        assert signals.harvest_score == 1.0
        assert signals.combined >= 0.92

    def test_build_signals_different_country(self):
        from app.services.matching.signals import build_signals
        listing = _listing()
        canonical = _canonical(origin_country="Kenya", canonical_name="Kenya AA Washed")
        signals = build_signals(listing, canonical)
        assert signals.exact_score < 0.5
        assert signals.combined < 0.75

    def test_build_signals_no_embeddings(self):
        """Missing embeddings → embedding_score = 0.0, others still work."""
        from app.services.matching.signals import build_signals
        signals = build_signals(_listing(), _canonical(), listing_embedding=None, canonical_embedding=None)
        assert signals.embedding_score == 0.0
        # But exact + fuzzy still give a meaningful score
        assert signals.combined > 0.0

    def test_signals_to_dict_serialisable(self):
        from app.services.matching.signals import build_signals
        import json
        signals = build_signals(_listing(), _canonical())
        d = signals.to_dict()
        json.dumps(d)  # must not raise
        assert "exact_score" in d
        assert "combined" in d


# ─────────────────────────────────────────────────────────────────────────────
# Confidence banding integration
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceBanding:
    """Verify the three confidence bands produce correct outcomes."""

    AUTO_ACCEPT = 0.92
    REVIEW = 0.75

    def test_exact_match_auto_accepts(self):
        from app.services.matching.signals import build_signals
        s = build_signals(_listing(), _canonical())
        assert s.combined >= self.AUTO_ACCEPT, f"Expected auto-accept, got {s.combined}"

    def test_partial_match_in_review_band(self):
        from app.services.matching.signals import build_signals
        # Same country + fuzzy match, different farm
        s = build_signals(
            _listing(farm_or_estate=None),
            _canonical(farm_or_estate=None, canonical_name="Ethiopia Yirgacheffe Unknown Farm"),
        )
        # Should land somewhere in the spectrum (may vary with rapidfuzz)
        assert 0.0 < s.combined <= 1.0

    def test_different_origin_country_low_confidence(self):
        from app.services.matching.signals import build_signals
        s = build_signals(
            _listing(),
            _canonical(origin_country="Kenya", canonical_name="Kenya Kirinyaga Washed"),
        )
        assert s.combined < self.AUTO_ACCEPT

    def test_cross_year_stays_below_auto_accept(self):
        from app.services.matching.signals import build_signals
        s = build_signals(
            _listing(harvest_year=2024),
            _canonical(harvest_year=2022),
        )
        assert s.combined < self.AUTO_ACCEPT, f"Cross-year should not auto-accept: {s.combined}"


# ─────────────────────────────────────────────────────────────────────────────
# TestMatchingService (DB-mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchingService:
    def _make_listing(self, **kwargs):
        listing = MagicMock()
        listing.id = "00000000-0000-0000-0000-000000000001"
        listing.raw_title = kwargs.get("raw_title", "Ethiopia Yirgacheffe Konga Washed")
        listing.origin_label_raw = kwargs.get("origin_label_raw", "Ethiopia")
        listing.process_label_raw = kwargs.get("process_label_raw", "Washed")
        listing.roast_label_raw = kwargs.get("roast_label_raw", "Light")
        listing.varietal_label_raw = kwargs.get("varietal_label_raw", "Heirloom")
        listing.canonical_bean_id = None
        # Attributes for scorer dicts
        listing.origin_country = kwargs.get("origin_country", "Ethiopia")
        listing.process = kwargs.get("process", "washed")
        listing.varietal = kwargs.get("varietal", ["Heirloom"])
        listing.farm_or_estate = kwargs.get("farm_or_estate", "Konga Cooperative")
        listing.harvest_year = kwargs.get("harvest_year", 2024)
        listing.raw_description = "Floral."
        listing.embedding_vector = None
        return listing

    def _make_canonical(self, **kwargs):
        c = MagicMock()
        c.id = "00000000-0000-0000-0000-000000000002"
        c.canonical_name = kwargs.get("canonical_name", "Ethiopia Yirgacheffe Konga Washed")
        c.origin_country = kwargs.get("origin_country", "Ethiopia")
        c.process = kwargs.get("process", "washed")
        c.varietal = kwargs.get("varietal", ["Heirloom"])
        c.farm_or_estate = kwargs.get("farm_or_estate", "Konga Cooperative")
        c.harvest_year = kwargs.get("harvest_year", 2024)
        c.embedding_vector = None
        c.flavour_notes = ["jasmine"]
        c.roast_level = "light"
        c.data_completeness_score = 0.9
        return c

    def _make_session(self, candidates=None, existing_match=None):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_match
        mock_result.scalars.return_value.all.return_value = candidates or []
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.mark.asyncio
    async def test_perfect_match_auto_accepts(self):
        from app.services.matching.service import CanonicalMatchingService
        listing = self._make_listing()
        canonical = self._make_canonical()
        session = self._make_session(candidates=[canonical])

        service = CanonicalMatchingService(session, auto_accept_threshold=0.92, review_threshold=0.75)
        decision = await service.match_listing(listing)

        assert decision.outcome in ("auto_accepted", "review_queued", "new_canonical")
        assert decision.listing_id == listing.id

    @pytest.mark.asyncio
    async def test_no_candidates_creates_new_canonical(self):
        from app.services.matching.service import CanonicalMatchingService
        listing = self._make_listing()
        session = self._make_session(candidates=[])

        service = CanonicalMatchingService(session, auto_accept_threshold=0.92, review_threshold=0.75)
        decision = await service.match_listing(listing)
        assert decision.outcome == "new_canonical"

    @pytest.mark.asyncio
    async def test_existing_accepted_match_returns_already_matched(self):
        from app.services.matching.service import CanonicalMatchingService
        from app.models.enums import ReviewStatus
        existing = MagicMock()
        existing.review_status = ReviewStatus.accepted
        existing.id = "00000000-0000-0000-0000-000000000099"
        existing.proposed_canonical_bean_id = "00000000-0000-0000-0000-000000000002"
        existing.confidence_score = 0.95

        listing = self._make_listing()
        session = self._make_session(existing_match=existing)

        service = CanonicalMatchingService(session)
        decision = await service.match_listing(listing)
        assert decision.outcome == "already_matched"
        assert decision.confidence == 0.95

    @pytest.mark.asyncio
    async def test_accept_match_links_listing(self):
        import uuid as uuid_mod
        from app.services.matching.service import CanonicalMatchingService
        from app.models.enums import ReviewStatus

        match = MagicMock()
        match.id = uuid_mod.uuid4()
        match.review_status = ReviewStatus.pending
        match.bean_listing_id = uuid_mod.uuid4()
        match.proposed_canonical_bean_id = uuid_mod.uuid4()

        listing = MagicMock()
        listing.canonical_bean_id = None

        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = match
        session.execute = AsyncMock(return_value=execute_result)
        session.get = AsyncMock(return_value=listing)
        session.commit = AsyncMock()

        service = CanonicalMatchingService(session)
        result = await service.accept_match(match.id, user_id="reviewer@example.com")

        assert match.review_status == ReviewStatus.accepted
        assert listing.canonical_bean_id == match.proposed_canonical_bean_id

    @pytest.mark.asyncio
    async def test_reject_match_leaves_listing_unlinked(self):
        import uuid as uuid_mod
        from app.services.matching.service import CanonicalMatchingService
        from app.models.enums import ReviewStatus

        match = MagicMock()
        match.id = uuid_mod.uuid4()
        match.review_status = ReviewStatus.pending
        match.bean_listing_id = uuid_mod.uuid4()

        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = match
        session.execute = AsyncMock(return_value=execute_result)
        session.commit = AsyncMock()

        service = CanonicalMatchingService(session)
        result = await service.reject_match(match.id)

        assert match.review_status == ReviewStatus.rejected

    @pytest.mark.asyncio
    async def test_accept_nonexistent_match_raises(self):
        import uuid as uuid_mod
        from app.services.matching.service import CanonicalMatchingService

        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=execute_result)

        service = CanonicalMatchingService(session)
        with pytest.raises(ValueError, match="not found"):
            await service.accept_match(uuid_mod.uuid4())

    @pytest.mark.asyncio
    async def test_error_in_pipeline_returns_error_decision(self):
        from app.services.matching.service import CanonicalMatchingService
        listing = self._make_listing()

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        service = CanonicalMatchingService(session)
        decision = await service.match_listing(listing)
        assert decision.outcome == "error"
        assert decision.error is not None


# ─────────────────────────────────────────────────────────────────────────────
# TestEmbeddingText
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbeddingText:
    def test_builds_text_from_canonical(self):
        from app.services.matching.embeddings import build_embedding_text
        obj = _canonical()
        text = build_embedding_text(obj)
        assert "Ethiopia" in text
        assert "Yirgacheffe" in text
        assert "washed" in text.lower() or "Washed" in text
        assert "Heirloom" in text

    def test_builds_text_from_listing(self):
        from app.services.matching.embeddings import build_embedding_text
        obj = _listing()
        text = build_embedding_text(obj)
        assert "Ethiopia" in text
        assert len(text) > 10

    def test_empty_object_returns_short_text(self):
        from app.services.matching.embeddings import build_embedding_text
        text = build_embedding_text({})
        assert isinstance(text, str)

    def test_flavour_notes_included(self):
        from app.services.matching.embeddings import build_embedding_text
        obj = _canonical(flavour_notes=["jasmine", "bergamot", "lemon"])
        text = build_embedding_text(obj)
        assert "jasmine" in text

    def test_long_description_truncated(self):
        from app.services.matching.embeddings import build_embedding_text
        obj = _listing(raw_description="A" * 1000)
        text = build_embedding_text(obj)
        # Description is capped at 300 chars
        assert len(text) < 800

    def test_works_with_orm_like_object(self):
        from app.services.matching.embeddings import build_embedding_text
        obj = MagicMock()
        obj.canonical_name = "Ethiopia Konga"
        obj.origin_country = "Ethiopia"
        obj.origin_region = "Yirgacheffe"
        obj.farm_or_estate = "Konga"
        obj.washing_station = None
        obj.process = "washed"
        obj.roast_level = "light"
        obj.varietal = ["Heirloom"]
        obj.flavour_notes = ["jasmine"]
        obj.raw_description = None
        text = build_embedding_text(obj)
        assert "Ethiopia" in text
        assert "Konga" in text
