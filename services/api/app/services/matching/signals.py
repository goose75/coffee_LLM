"""
Match signal scorers.

Each scorer takes a listing and a candidate canonical bean and returns a
float in [0.0, 1.0]. Higher = more similar.

Four independent signals:
  1. ExactFieldScorer     — deterministic equality on structured fields
  2. FuzzyTitleScorer     — rapidfuzz token_set_ratio on titles
  3. EmbeddingScorer      — cosine similarity on pgvector embeddings
  4. HarvestYearScorer    — same/different/missing harvest year modifier

Scorers are pure functions: no DB access, no side effects, no async.
The orchestrator (MatchingService) handles DB queries and combines signals.

Confidence formula (see MatchingService.combine_signals):
  base = 0.45 * exact + 0.30 * fuzzy + 0.20 * embedding + 0.05 * harvest
  penalty applied when harvest years are both present and different.

Weights chosen to:
  - Give exact structured matches the strongest single signal
  - Use fuzzy as the primary fallback for unstructured titles
  - Use embeddings for semantic cross-lingual matching
  - Penalise cross-year same-farm lots (different harvests = different beans)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MatchSignals:
    """
    All per-signal scores for one listing↔canonical pair.
    Stored in canonical_matches.match_signals_json for reviewer context.
    """
    exact_score: float = 0.0
    fuzzy_score: float = 0.0
    embedding_score: float = 0.0
    harvest_score: float = 1.0        # 1.0 = not penalised
    field_matches: dict[str, bool] = field(default_factory=dict)
    combined: float = 0.0

    def to_dict(self) -> dict:
        return {
            "exact_score": round(self.exact_score, 4),
            "fuzzy_score": round(self.fuzzy_score, 4),
            "embedding_score": round(self.embedding_score, 4),
            "harvest_score": round(self.harvest_score, 4),
            "field_matches": self.field_matches,
            "combined": round(self.combined, 4),
        }


# ─── Signal weights ────────────────────────────────────────────────────────────

WEIGHTS = {
    "exact": 0.45,
    "fuzzy": 0.30,
    "embedding": 0.20,
    "harvest": 0.05,
}

# ─── Exact field scorer ───────────────────────────────────────────────────────


def score_exact_fields(listing: Any, canonical: Any) -> tuple[float, dict[str, bool]]:
    """
    Score structured field equality between a listing and a canonical bean.

    Fields checked (with individual weights summing to 1.0):
      origin_country (0.30) — strongest signal; Ethiopia ≠ Kenya always
      process        (0.25) — washed ≠ natural changes the bean identity
      varietal       (0.20) — SL28 ≠ Bourbon is meaningful but less definitive
      farm_or_estate (0.25) — same farm + same country ≈ very likely same bean

    If a field is blank on EITHER side, it doesn't penalise — we only compare
    when both sides have data. A listing with no varietal could be any varietal.

    Returns (score, {field: matched_or_skipped}) where score ∈ [0.0, 1.0].
    """
    field_weights = {
        "origin_country": 0.30,
        "process": 0.25,
        "varietal": 0.20,
        "farm_or_estate": 0.25,
    }
    matches: dict[str, bool] = {}
    total_weight = 0.0
    weighted_score = 0.0

    for fname, weight in field_weights.items():
        listing_val = _get_field(listing, fname)
        canonical_val = _get_field(canonical, fname)

        if not listing_val or not canonical_val:
            # Skip — one side is blank
            matches[fname] = None  # type: ignore[assignment]
            continue

        total_weight += weight

        if fname == "varietal":
            # Varietal is a list — score partial overlap
            lset = _normalise_list(listing_val)
            cset = _normalise_list(canonical_val)
            if lset and cset:
                overlap = len(lset & cset) / max(len(lset), len(cset))
                weighted_score += weight * overlap
                matches[fname] = overlap > 0.5
            else:
                matches[fname] = False
        else:
            match = _normalise_str(listing_val) == _normalise_str(canonical_val)
            weighted_score += weight * (1.0 if match else 0.0)
            matches[fname] = match

    if total_weight == 0.0:
        return 0.0, matches

    score = weighted_score / total_weight
    return round(score, 4), matches


def _get_field(obj: Any, field_name: str) -> Any:
    """Get field from ORM object (attr) or dict."""
    if isinstance(obj, dict):
        return obj.get(field_name)
    return getattr(obj, field_name, None)


def _normalise_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip().lower()


def _normalise_list(v: Any) -> set[str]:
    if isinstance(v, list):
        return {s.strip().lower() for s in v if s}
    if isinstance(v, str):
        return {v.strip().lower()} if v.strip() else set()
    return set()


# ─── Fuzzy title scorer ───────────────────────────────────────────────────────


def score_fuzzy_title(listing_title: str, canonical_name: str) -> float:
    """
    Fuzzy similarity between listing raw_title and canonical_name.

    Uses rapidfuzz token_set_ratio: insensitive to word order and
    partial matches. "Ethiopia Yirgacheffe" matches "Yirgacheffe Ethiopia AA"
    at ~90+.

    Returns float ∈ [0.0, 1.0].
    """
    if not listing_title or not canonical_name:
        return 0.0

    try:
        from rapidfuzz import fuzz
        # token_set_ratio: best for coffee names with variable word order
        score = fuzz.token_set_ratio(listing_title, canonical_name) / 100.0
        # Also try partial_ratio for short names
        partial = fuzz.partial_ratio(listing_title, canonical_name) / 100.0
        return round(max(score, partial * 0.9), 4)
    except ImportError:
        log.warning("rapidfuzz not installed — fuzzy scoring disabled")
        return _fallback_overlap(listing_title, canonical_name)


def _fallback_overlap(a: str, b: str) -> float:
    """Simple word-overlap fallback when rapidfuzz is unavailable."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ─── Embedding scorer ─────────────────────────────────────────────────────────


def score_embeddings(
    listing_embedding: list[float] | None,
    canonical_embedding: list[float] | None,
) -> float:
    """
    Cosine similarity between two embedding vectors.

    Both vectors are expected to be 1536-dimensional (text-embedding-3-small).
    Returns 0.0 if either embedding is missing.

    The result is normalised from [-1, 1] cosine range to [0, 1]:
      normalised = (cosine + 1) / 2
    but in practice coffee description embeddings are never negative-cosine,
    so the effective range is [0.0, 1.0].
    """
    if not listing_embedding or not canonical_embedding:
        return 0.0

    try:
        import numpy as np
        a = np.array(listing_embedding, dtype=np.float32)
        b = np.array(canonical_embedding, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        cosine = float(np.dot(a, b) / (norm_a * norm_b))
        # Clamp to [-1, 1] for floating point safety, then normalise
        cosine = max(-1.0, min(1.0, cosine))
        return round((cosine + 1.0) / 2.0, 4)
    except ImportError:
        log.warning("numpy not installed — embedding scoring disabled")
        return 0.0


# ─── Harvest year scorer ──────────────────────────────────────────────────────


def score_harvest_year(
    listing_harvest_year: int | None,
    canonical_harvest_year: int | None,
) -> float:
    """
    Harvest year agreement score.

    Rules:
      - Both None: 1.0 (no penalty — absence doesn't imply different)
      - Same year: 1.0
      - Different by 1 year: 0.5 (possible re-lot of same crop year)
      - Different by 2+ years: 0.0 (different harvest = different bean)
      - One is None: 0.8 (slight uncertainty discount)

    This is applied as a multiplier, not an additive signal, to ensure
    cross-year same-farm lots never auto-accept regardless of other scores.
    """
    if listing_harvest_year is None and canonical_harvest_year is None:
        return 1.0
    if listing_harvest_year is None or canonical_harvest_year is None:
        return 0.8  # uncertainty discount
    if listing_harvest_year == canonical_harvest_year:
        return 1.0
    diff = abs(listing_harvest_year - canonical_harvest_year)
    if diff == 1:
        return 0.5
    return 0.0


# ─── Signal combiner ──────────────────────────────────────────────────────────


def combine_signals(signals: MatchSignals) -> float:
    """
    Combine individual signals into a final confidence score.

    Formula:
      raw = (exact * 0.45) + (fuzzy * 0.30) + (embedding * 0.20)
      adjusted = raw * harvest_score + (harvest * 0.05)

    Harvest year acts as both an additive term (0.05) and a multiplicative
    penalty on the main score. This ensures cross-year lots can never
    auto-accept even if exact+fuzzy+embedding are all 1.0.

    Returns float clamped to [0.0, 1.0].
    """
    raw = (
        signals.exact_score * WEIGHTS["exact"]
        + signals.fuzzy_score * WEIGHTS["fuzzy"]
        + signals.embedding_score * WEIGHTS["embedding"]
    )
    # Harvest multiplies the raw score (penalises different years)
    adjusted = raw * signals.harvest_score + signals.harvest_score * WEIGHTS["harvest"]
    return round(min(1.0, max(0.0, adjusted)), 4)


def build_signals(
    listing: Any,
    canonical: Any,
    listing_embedding: list[float] | None = None,
    canonical_embedding: list[float] | None = None,
) -> MatchSignals:
    """
    Compute all signals for a listing↔canonical pair.
    Convenience wrapper used by tests and the service.
    """
    exact_score, field_matches = score_exact_fields(listing, canonical)
    fuzzy_score = score_fuzzy_title(
        _get_field(listing, "raw_title") or "",
        _get_field(canonical, "canonical_name") or "",
    )
    embedding_score = score_embeddings(listing_embedding, canonical_embedding)
    harvest_score = score_harvest_year(
        _get_field(listing, "harvest_year"),
        _get_field(canonical, "harvest_year"),
    )

    signals = MatchSignals(
        exact_score=exact_score,
        fuzzy_score=fuzzy_score,
        embedding_score=embedding_score,
        harvest_score=harvest_score,
        field_matches=field_matches,
    )
    signals.combined = combine_signals(signals)
    return signals
