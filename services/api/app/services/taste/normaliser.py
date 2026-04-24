"""
Rule-based flavour normaliser.

First-pass, zero-cost normaliser. For each raw note string:
  1. Exact lowercase match against synonym lists
  2. Substring match (e.g. "dark chocolate notes" → chocolate.dark)
  3. Returns None if no match found (triggers LLM fallback)

Returns matches at the deepest possible level (prefer depth-2 over depth-1).
Confidence is 1.0 for exact match, 0.85 for substring.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.taste.taxonomy import TAXONOMY


@dataclass
class RuleMatch:
    slug: str
    label: str
    depth: int
    confidence: float
    match_type: str  # "exact" | "substring"


# Pre-build: list of (slug, synonym_lower) pairs sorted deepest first
_SYNONYM_INDEX: list[tuple[str, str, str, int]] = []  # (slug, synonym_lower, label, depth)

for _node in TAXONOMY:
    for _syn in _node["synonyms"]:
        _SYNONYM_INDEX.append((_node["slug"], _syn.lower(), _node["label"], _node["depth"]))

# Sort deepest first so we prefer specific matches (depth 2) over general (depth 0)
_SYNONYM_INDEX.sort(key=lambda x: (-x[3], len(x[1])), reverse=False)
_SYNONYM_INDEX.sort(key=lambda x: -x[3])  # depth desc


def match_note(raw: str) -> RuleMatch | None:
    """
    Attempt to match a single raw tasting note string to a taxonomy node.
    Returns None if no match found.
    """
    cleaned = raw.strip().lower()
    if not cleaned:
        return None

    # Pass 1: exact match
    for slug, syn, label, depth in _SYNONYM_INDEX:
        if cleaned == syn:
            return RuleMatch(slug=slug, label=label, depth=depth, confidence=1.0, match_type="exact")

    # Pass 2: raw note contains the synonym (e.g. "dark chocolate notes")
    for slug, syn, label, depth in _SYNONYM_INDEX:
        if syn in cleaned:
            return RuleMatch(slug=slug, label=label, depth=depth, confidence=0.85, match_type="substring")

    # Pass 3: synonym contains the raw note (e.g. "lemon" matches synonym "lemon zest")
    for slug, syn, label, depth in _SYNONYM_INDEX:
        if cleaned in syn and len(cleaned) >= 4:
            return RuleMatch(slug=slug, label=label, depth=depth, confidence=0.75, match_type="substring")

    return None


def match_notes(raw_notes: list[str]) -> list[tuple[str, RuleMatch | None]]:
    """
    Match a list of raw notes. Returns (raw_note, match_or_None) pairs.
    """
    return [(note, match_note(note)) for note in raw_notes]


def unmatched_notes(raw_notes: list[str]) -> list[str]:
    """Return only the notes that rule-matching failed on (need LLM fallback)."""
    return [note for note, match in match_notes(raw_notes) if match is None]
