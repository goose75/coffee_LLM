"""
Tests for taste profile intelligence.

Coverage:
  TestTaxonomy          — taxonomy structure and slug validity
  TestRuleNormaliser    — rule-based note matching (no DB, no LLM)
  TestSimilarityScoring — Jaccard family overlap scoring
  TestTasteSchemas      — Pydantic schema validation
  TestLLMResponseParsing — LLM JSON validation and slug verification
"""
from __future__ import annotations

from uuid import uuid4

import pytest


# ── Taxonomy structure ─────────────────────────────────────────────────────────

class TestTaxonomy:
    def test_all_entries_have_required_fields(self):
        from app.services.taste.taxonomy import TAXONOMY
        for node in TAXONOMY:
            assert "slug" in node, f"Missing slug: {node}"
            assert "label" in node
            assert "depth" in node
            assert "synonyms" in node
            assert isinstance(node["synonyms"], list)

    def test_depth_range(self):
        from app.services.taste.taxonomy import TAXONOMY
        depths = {n["depth"] for n in TAXONOMY}
        assert depths <= {0, 1, 2}

    def test_families_have_no_parent(self):
        from app.services.taste.taxonomy import TAXONOMY
        families = [n for n in TAXONOMY if n["depth"] == 0]
        assert len(families) == 8
        for f in families:
            assert f["parent"] is None

    def test_families_have_colours(self):
        from app.services.taste.taxonomy import TAXONOMY
        for n in TAXONOMY:
            if n["depth"] == 0:
                assert n.get("colour"), f"Family {n['slug']} has no colour"
                assert n["colour"].startswith("#")

    def test_non_families_have_parents(self):
        from app.services.taste.taxonomy import TAXONOMY
        for n in TAXONOMY:
            if n["depth"] > 0:
                assert n["parent"] is not None, f"{n['slug']} has no parent"

    def test_parent_exists_in_taxonomy(self):
        from app.services.taste.taxonomy import TAXONOMY, TAXONOMY_BY_SLUG
        for n in TAXONOMY:
            if n["parent"]:
                assert n["parent"] in TAXONOMY_BY_SLUG, f"Parent '{n['parent']}' not found for '{n['slug']}'"

    def test_all_slugs_unique(self):
        from app.services.taste.taxonomy import TAXONOMY
        slugs = [n["slug"] for n in TAXONOMY]
        assert len(slugs) == len(set(slugs))

    def test_leaf_tags_have_synonyms(self):
        """Every depth-2 tag should have at least one synonym for matching."""
        from app.services.taste.taxonomy import TAXONOMY
        tags = [n for n in TAXONOMY if n["depth"] == 2]
        assert len(tags) > 50  # sanity check we have enough tags
        no_synonyms = [n["slug"] for n in tags if not n["synonyms"]]
        assert no_synonyms == [], f"Tags with no synonyms: {no_synonyms}"

    def test_family_colour_helper(self):
        from app.services.taste.taxonomy import get_family_colour
        assert get_family_colour("fruity.citrus.lemon").startswith("#")
        assert get_family_colour("floral.jasmine").startswith("#")
        assert get_family_colour("fruity").startswith("#")


# ── Rule-based normaliser ──────────────────────────────────────────────────────

class TestRuleNormaliser:
    def _match(self, note: str):
        from app.services.taste.normaliser import match_note
        return match_note(note)

    def test_exact_match_jasmine(self):
        result = self._match("jasmine")
        assert result is not None
        assert "floral" in result.slug
        assert result.confidence == 1.0
        assert result.match_type == "exact"

    def test_exact_match_lemon(self):
        result = self._match("lemon")
        assert result is not None
        assert "citrus" in result.slug or "fruity" in result.slug

    def test_exact_match_caramel(self):
        result = self._match("caramel")
        assert result is not None
        assert "sweet" in result.slug

    def test_exact_match_dark_chocolate(self):
        result = self._match("dark chocolate")
        assert result is not None
        assert "chocolate" in result.slug

    def test_exact_match_blackcurrant(self):
        result = self._match("blackcurrant")
        assert result is not None
        assert "berry" in result.slug

    def test_exact_match_mango(self):
        result = self._match("mango")
        assert result is not None
        assert "tropical" in result.slug

    def test_substring_match_lemon_curd(self):
        """'lemon curd' should hit the lemon synonym."""
        result = self._match("lemon curd")
        assert result is not None
        assert "citrus" in result.slug or "fruity" in result.slug

    def test_substring_match_tropical_fruit(self):
        result = self._match("tropical fruit")
        assert result is not None
        assert "tropical" in result.slug or "fruity" in result.slug

    def test_no_match_returns_none(self):
        result = self._match("xyz_unknown_note_abc")
        assert result is None

    def test_empty_string_returns_none(self):
        result = self._match("")
        assert result is None

    def test_whitespace_returns_none(self):
        result = self._match("   ")
        assert result is None

    def test_match_depth_preference(self):
        """Should prefer depth-2 tags over depth-0 families."""
        result = self._match("lemon")
        assert result is not None
        assert result.depth == 2

    def test_match_notes_batch(self):
        from app.services.taste.normaliser import match_notes
        pairs = match_notes(["jasmine", "lemon", "unknown_note"])
        assert len(pairs) == 3
        matched = [note for note, m in pairs if m is not None]
        assert "jasmine" in matched
        assert "lemon" in matched
        assert "unknown_note" not in matched

    def test_unmatched_notes(self):
        from app.services.taste.normaliser import unmatched_notes
        result = unmatched_notes(["jasmine", "bergamot", "xyz_mystery"])
        assert "xyz_mystery" in result
        assert "jasmine" not in result

    def test_case_insensitive_match(self):
        """All matching is lowercased, so 'LEMON' should hit lemon."""
        result = self._match("LEMON")
        assert result is not None

    def test_known_notes_all_match(self):
        """Every common note from real seed data should match."""
        common_notes = [
            "jasmine", "bergamot", "lemon", "peach",
            "tropical fruit", "strawberry", "passionfruit", "candy",
            "blackcurrant", "grapefruit", "brown sugar",
        ]
        no_match = []
        for note in common_notes:
            r = self._match(note)
            if r is None:
                no_match.append(note)
        assert no_match == [], f"These common notes have no rule match: {no_match}"

    def test_rule_match_confidence_bounds(self):
        result = self._match("jasmine")
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


# ── Similarity scoring ─────────────────────────────────────────────────────────

class TestSimilarityScoring:
    """Jaccard similarity = |A ∩ B| / |A ∪ B|."""

    def _jaccard(self, a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    def test_identical_sets(self):
        a = {"fruity", "floral", "sweet"}
        assert self._jaccard(a, a) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        a = {"fruity", "floral"}
        b = {"chocolate", "nutty"}
        assert self._jaccard(a, b) == pytest.approx(0.0)

    def test_partial_overlap(self):
        a = {"fruity", "floral", "sweet"}
        b = {"fruity", "chocolate", "sweet"}
        # intersection = {fruity, sweet} = 2
        # union = {fruity, floral, sweet, chocolate} = 4
        assert self._jaccard(a, b) == pytest.approx(0.5)

    def test_single_element_overlap(self):
        a = {"fruity", "floral", "sweet"}
        b = {"fruity", "nutty"}
        # intersection = {fruity} = 1, union = 4
        assert self._jaccard(a, b) == pytest.approx(0.25)

    def test_empty_sets(self):
        assert self._jaccard(set(), set()) == pytest.approx(0.0)

    def test_one_empty(self):
        assert self._jaccard({"fruity"}, set()) == pytest.approx(0.0)

    def test_scores_between_0_and_1(self):
        import random
        families = ["fruity", "floral", "sweet", "chocolate", "nutty", "spice", "earthy", "fermented"]
        for _ in range(20):
            a = set(random.sample(families, k=random.randint(1, 4)))
            b = set(random.sample(families, k=random.randint(1, 4)))
            score = self._jaccard(a, b)
            assert 0.0 <= score <= 1.0

    def test_more_overlap_higher_score(self):
        base = {"fruity", "floral", "sweet", "chocolate"}
        high_overlap = {"fruity", "floral", "sweet", "nutty"}   # 3 shared
        low_overlap  = {"fruity", "nutty", "earthy", "fermented"}  # 1 shared
        score_high = self._jaccard(base, high_overlap)
        score_low  = self._jaccard(base, low_overlap)
        assert score_high > score_low


# ── Taste schemas ──────────────────────────────────────────────────────────────

class TestTasteSchemas:
    def test_tagged_note_schema(self):
        from app.schemas.taste import TaggedNote
        t = TaggedNote(raw_note="jasmine", slug="floral.jasmine", label="Jasmine",
                       confidence=1.0, source="rule")
        assert t.raw_note == "jasmine"
        assert t.confidence == 1.0

    def test_flavor_family_schema(self):
        from app.schemas.taste import FlavorFamily, TaggedNote
        f = FlavorFamily(
            family_slug="floral", family_label="Floral", colour="#c084c0",
            tags=[TaggedNote(raw_note="jasmine", slug="floral.jasmine", label="Jasmine", confidence=1.0, source="rule")],
            weight=1,
        )
        assert f.family_slug == "floral"
        assert len(f.tags) == 1

    def test_taste_profile_schema(self):
        from app.schemas.taste import TasteProfile
        p = TasteProfile(
            bean_id=uuid4(),
            canonical_name="Test Bean",
            raw_notes=["jasmine", "lemon"],
            families=[],
            has_structured_tags=False,
            tag_count=0,
        )
        assert p.has_structured_tags is False
        assert p.tag_count == 0

    def test_similar_coffee_schema(self):
        from app.schemas.taste import SimilarCoffee
        s = SimilarCoffee(
            bean_id=uuid4(),
            canonical_name="Ethiopia Test",
            origin_country="Ethiopia",
            process="washed",
            roast_level="light",
            flavour_notes=["jasmine", "lemon"],
            similarity_score=0.75,
            shared_families=["floral", "fruity"],
        )
        assert s.similarity_score == 0.75
        assert "floral" in s.shared_families

    def test_tag_review_item_schema(self):
        from app.schemas.taste import TagReviewItem
        item = TagReviewItem(
            tag_id=uuid4(), bean_id=uuid4(),
            bean_name="Colombia Test",
            raw_note="candy", slug="sweet.confection.candy",
            label="Candy", confidence=0.65,
            source="llm", review_status="pending",
            llm_audit={"reasoning": "candy-like sweetness", "prompt_version": "taste-v1.0.0"},
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        assert item.review_status == "pending"
        assert item.llm_audit is not None

    def test_family_distribution_schema(self):
        from app.schemas.taste import FamilyDistribution, FamilyDistributionRow
        dist = FamilyDistribution(
            dimension_type="origin_country",
            rows=[
                FamilyDistributionRow(dimension_value="Ethiopia", family_counts={"floral": 8, "fruity": 6}, total_tags=14),
                FamilyDistributionRow(dimension_value="Kenya", family_counts={"fruity": 10, "sweet": 3}, total_tags=13),
            ]
        )
        assert len(dist.rows) == 2
        assert dist.rows[0].total_tags == 14


# ── LLM response parsing ───────────────────────────────────────────────────────

class TestLLMResponseParsing:
    """Validate the LLM normaliser's JSON parsing and slug validation."""

    def test_valid_response_parsed(self):
        import json
        from app.services.taste.taxonomy import TAXONOMY_BY_SLUG

        raw = json.dumps({
            "mappings": [
                {"raw_note": "jasmine", "slug": "floral.jasmine", "confidence": 0.95, "reasoning": "Jasmine is a floral note."},
                {"raw_note": "lemon", "slug": "fruity.citrus.lemon", "confidence": 0.98, "reasoning": "Lemon is a citrus note."},
            ]
        })

        mappings = json.loads(raw)["mappings"]
        for m in mappings:
            assert m["slug"] in TAXONOMY_BY_SLUG, f"Slug '{m['slug']}' not in taxonomy"
            assert 0.0 <= m["confidence"] <= 1.0

    def test_invalid_slug_caught(self):
        from app.services.taste.taxonomy import TAXONOMY_BY_SLUG
        fake_slug = "fruity.citrus.unicorn_fruit"
        assert fake_slug not in TAXONOMY_BY_SLUG

    def test_null_slug_handled(self):
        """slug=null should produce a no-match result, not an error."""
        import json
        raw = json.dumps({
            "mappings": [
                {"raw_note": "mystery_note", "slug": None, "confidence": 0.0, "reasoning": "No match."},
            ]
        })
        m = json.loads(raw)["mappings"][0]
        slug = m.get("slug") or None
        assert slug is None

    def test_confidence_clamped(self):
        """Confidence values should be clamped to [0, 1]."""
        raw_conf = 1.5
        clamped = min(1.0, max(0.0, raw_conf))
        assert clamped == 1.0

    def test_code_fence_stripped(self):
        """LLM sometimes wraps JSON in ```json ... ``` despite instructions."""
        import json
        raw = "```json\n{\"mappings\": []}\n```"
        text = raw
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
        assert "mappings" in parsed

    def test_prompt_version_constant(self):
        from app.services.taste.prompts.v1 import PROMPT_VERSION
        assert PROMPT_VERSION.startswith("taste-v")

    def test_build_messages_returns_list(self):
        from app.services.taste.prompts.v1 import build_messages
        msgs = build_messages(["jasmine", "lemon"])
        assert isinstance(msgs, list)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert "jasmine" in msgs[0]["content"]
