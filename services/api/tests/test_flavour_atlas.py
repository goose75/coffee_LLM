"""
test_flavour_atlas.py — Unit tests for Flavour Atlas aggregation and filtering.

Tests are written to run without a live DB connection using in-memory fixtures.
Run from the repo root:
    docker exec coffee_api python -m pytest services/api/tests/test_flavour_atlas.py -v
"""

from __future__ import annotations

import pytest
from collections import defaultdict
from uuid import UUID, uuid4


# ── Fixtures — minimal taxonomy + tag stubs ───────────────────────────────────

class FakeTaxNode:
    def __init__(self, slug: str, label: str, depth: int, colour: str = "#888"):
        self.id = uuid4()
        self.slug = slug
        self.label = label
        self.depth = depth
        self.colour = colour
        self.sort_order = 0

    @property
    def family_slug(self) -> str:
        return self.slug.split(".")[0]


class FakeTag:
    def __init__(self, bean_id: UUID, tax_node: FakeTaxNode, review_status: str = "accepted"):
        self.bean_id = bean_id
        self.taxonomy_id = tax_node.id
        self.tax_node = tax_node
        self.review_status = review_status
        self.confidence = 1.0
        self.source = "rule"


# ── Build a minimal in-memory taxonomy ───────────────────────────────────────

def build_taxonomy() -> dict[str, FakeTaxNode]:
    nodes = [
        # Fruity family
        FakeTaxNode("fruity",                  "Fruity",      0, "#e05c3a"),
        FakeTaxNode("fruity.citrus",           "Citrus",      1, "#e05c3a"),
        FakeTaxNode("fruity.citrus.lemon",     "Lemon",       2, "#e05c3a"),
        FakeTaxNode("fruity.citrus.orange",    "Orange",      2, "#e05c3a"),
        FakeTaxNode("fruity.berry",            "Berry",       1, "#e05c3a"),
        FakeTaxNode("fruity.berry.cherry",     "Cherry",      2, "#e05c3a"),
        FakeTaxNode("fruity.berry.blueberry",  "Blueberry",   2, "#e05c3a"),
        # Chocolate family — no categories, tags hang directly
        FakeTaxNode("chocolate",               "Chocolate",   0, "#7c4b2a"),
        FakeTaxNode("chocolate.dark",          "Dark Choc",   2, "#7c4b2a"),
        FakeTaxNode("chocolate.milk",          "Milk Choc",   2, "#7c4b2a"),
        # Nutty family
        FakeTaxNode("nutty",                   "Nutty",       0, "#a07850"),
        FakeTaxNode("nutty.almond",            "Almond",      2, "#a07850"),
        FakeTaxNode("nutty.hazelnut",          "Hazelnut",    2, "#a07850"),
    ]
    return {n.slug: n for n in nodes}


# ── Aggregation helpers (mirrors atlas endpoint logic) ────────────────────────

def compute_family_bean_sets(
    tags: list[FakeTag],
    taxonomy: dict[str, FakeTaxNode],
) -> dict[str, set]:
    """Return {family_slug: {bean_id, ...}} for accepted tags."""
    family_sets: dict[str, set] = defaultdict(set)
    cat_sets: dict[str, set] = defaultdict(set)
    for tag in tags:
        if tag.review_status != "accepted":
            continue
        node = taxonomy.get(tag.tax_node.slug)
        if not node:
            continue
        parts = node.slug.split(".")
        family_sets[parts[0]].add(tag.bean_id)
        if len(parts) >= 2:
            cat_sets[f"{parts[0]}.{parts[1]}"].add(tag.bean_id)
    return family_sets, cat_sets


def filter_beans_by_slugs(
    slugs: list[str],
    tags: list[FakeTag],
    taxonomy: dict[str, FakeTaxNode],
) -> list[UUID]:
    """Return distinct bean_ids whose accepted tags match any of the given slugs (prefix match)."""
    matching_ids = [
        t.id for t in taxonomy.values()
        if any(t.slug == s or t.slug.startswith(s + ".") for s in slugs)
    ]
    bean_ids: set[UUID] = set()
    for tag in tags:
        if tag.review_status != "accepted":
            continue
        if tag.taxonomy_id in matching_ids:
            bean_ids.add(tag.bean_id)
    return list(bean_ids)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFamilyBeanCounts:
    """Test that bean counts bubble up correctly to family level."""

    def setup_method(self):
        self.tax = build_taxonomy()
        self.bean_a = uuid4()
        self.bean_b = uuid4()
        self.bean_c = uuid4()

    def test_single_family_count(self):
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"]),
            FakeTag(self.bean_b, self.tax["fruity.berry.cherry"]),
        ]
        fam_sets, _ = compute_family_bean_sets(tags, self.tax)
        assert len(fam_sets["fruity"]) == 2

    def test_same_bean_two_tags_counts_once(self):
        """A bean tagged with lemon AND orange should count as 1 in the family."""
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"]),
            FakeTag(self.bean_a, self.tax["fruity.citrus.orange"]),
        ]
        fam_sets, _ = compute_family_bean_sets(tags, self.tax)
        assert len(fam_sets["fruity"]) == 1

    def test_pending_tags_excluded(self):
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"], review_status="pending"),
            FakeTag(self.bean_b, self.tax["fruity.citrus.orange"], review_status="accepted"),
        ]
        fam_sets, _ = compute_family_bean_sets(tags, self.tax)
        assert len(fam_sets["fruity"]) == 1

    def test_rejected_tags_excluded(self):
        tags = [
            FakeTag(self.bean_a, self.tax["chocolate.dark"], review_status="rejected"),
        ]
        fam_sets, _ = compute_family_bean_sets(tags, self.tax)
        assert "chocolate" not in fam_sets or len(fam_sets["chocolate"]) == 0

    def test_family_isolation(self):
        """Fruity and chocolate counts don't bleed into each other."""
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"]),
            FakeTag(self.bean_b, self.tax["chocolate.dark"]),
            FakeTag(self.bean_c, self.tax["chocolate.milk"]),
        ]
        fam_sets, _ = compute_family_bean_sets(tags, self.tax)
        assert len(fam_sets["fruity"]) == 1
        assert len(fam_sets["chocolate"]) == 2

    def test_category_counts(self):
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"]),
            FakeTag(self.bean_b, self.tax["fruity.citrus.orange"]),
            FakeTag(self.bean_c, self.tax["fruity.berry.cherry"]),
        ]
        _, cat_sets = compute_family_bean_sets(tags, self.tax)
        assert len(cat_sets["fruity.citrus"]) == 2
        assert len(cat_sets["fruity.berry"]) == 1

    def test_empty_tags(self):
        fam_sets, cat_sets = compute_family_bean_sets([], self.tax)
        assert len(fam_sets) == 0


class TestSlugFiltering:
    """Test that family/category/tag slug filtering returns correct bean sets."""

    def setup_method(self):
        self.tax = build_taxonomy()
        self.bean_a = uuid4()  # fruity (citrus only)
        self.bean_b = uuid4()  # fruity (berry only)
        self.bean_c = uuid4()  # chocolate
        self.bean_d = uuid4()  # nutty + fruity

        self.tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"]),
            FakeTag(self.bean_b, self.tax["fruity.berry.cherry"]),
            FakeTag(self.bean_c, self.tax["chocolate.dark"]),
            FakeTag(self.bean_d, self.tax["nutty.almond"]),
            FakeTag(self.bean_d, self.tax["fruity.citrus.orange"]),
        ]

    def test_family_slug_returns_all_in_family(self):
        result = filter_beans_by_slugs(["fruity"], self.tags, self.tax)
        assert set(result) == {self.bean_a, self.bean_b, self.bean_d}

    def test_category_slug_returns_category_beans(self):
        result = filter_beans_by_slugs(["fruity.citrus"], self.tags, self.tax)
        assert set(result) == {self.bean_a, self.bean_d}

    def test_tag_slug_exact_match(self):
        result = filter_beans_by_slugs(["fruity.citrus.lemon"], self.tags, self.tax)
        assert set(result) == {self.bean_a}

    def test_multiple_slugs_union(self):
        """Selecting fruity.citrus AND chocolate returns the union."""
        result = filter_beans_by_slugs(["fruity.citrus", "chocolate"], self.tags, self.tax)
        assert set(result) == {self.bean_a, self.bean_c, self.bean_d}

    def test_nonexistent_slug_returns_empty(self):
        result = filter_beans_by_slugs(["does.not.exist"], self.tags, self.tax)
        assert result == []

    def test_empty_slug_list_returns_empty(self):
        result = filter_beans_by_slugs([], self.tags, self.tax)
        assert result == []

    def test_pending_tags_not_included(self):
        tags = [
            FakeTag(self.bean_a, self.tax["fruity.citrus.lemon"], review_status="pending"),
        ]
        result = filter_beans_by_slugs(["fruity"], tags, self.tax)
        assert result == []

    def test_slug_prefix_match_does_not_cross_families(self):
        """'fruity' should not match 'chocolate' even though 'f' is a prefix of... nothing."""
        result = filter_beans_by_slugs(["fruity"], self.tags, self.tax)
        assert self.bean_c not in result

    def test_cross_family_selection(self):
        """Selecting both chocolate and nutty returns exactly those beans."""
        result = filter_beans_by_slugs(["chocolate", "nutty"], self.tags, self.tax)
        assert set(result) == {self.bean_c, self.bean_d}


class TestAtlasNodeStructure:
    """Test the tree assembly logic — families, categories, tags correctly nested."""

    def setup_method(self):
        self.tax = build_taxonomy()

    def _build_tree(self) -> dict:
        """Simulate the tree-building step in the atlas endpoint."""
        all_nodes = list(self.tax.values())
        families = [n for n in all_nodes if n.depth == 0]
        categories = [n for n in all_nodes if n.depth == 1]
        tags = [n for n in all_nodes if n.depth == 2]

        tree = {}
        for fam in families:
            children = []
            for cat in [c for c in categories if c.slug.startswith(fam.slug + ".")]:
                cat_children = [t for t in tags if t.slug.startswith(cat.slug + ".")]
                children.append({"slug": cat.slug, "children": [{"slug": t.slug} for t in cat_children]})
            # Family with no categories — tags hang directly
            if not children:
                direct_tags = [t for t in tags if t.slug.startswith(fam.slug + ".") and t.depth == 2]
                children = [{"slug": t.slug, "children": []} for t in direct_tags]
            tree[fam.slug] = {"slug": fam.slug, "children": children}
        return tree

    def test_fruity_has_two_categories(self):
        tree = self._build_tree()
        assert len(tree["fruity"]["children"]) == 2

    def test_citrus_has_correct_tags(self):
        tree = self._build_tree()
        citrus = next(c for c in tree["fruity"]["children"] if c["slug"] == "fruity.citrus")
        tag_slugs = {t["slug"] for t in citrus["children"]}
        assert "fruity.citrus.lemon" in tag_slugs
        assert "fruity.citrus.orange" in tag_slugs

    def test_chocolate_tags_hang_directly(self):
        """Chocolate has no depth-1 categories in our fixture — tags should be direct children."""
        tree = self._build_tree()
        choc_children_slugs = {c["slug"] for c in tree["chocolate"]["children"]}
        assert "chocolate.dark" in choc_children_slugs
        assert "chocolate.milk" in choc_children_slugs

    def test_all_families_present(self):
        tree = self._build_tree()
        assert "fruity" in tree
        assert "chocolate" in tree
        assert "nutty" in tree


class TestUrlStateEncoding:
    """Test slug serialisation/deserialisation for URL params."""

    def test_single_slug_roundtrip(self):
        slug = "fruity.citrus.lemon"
        encoded = slug
        decoded = [s.strip() for s in encoded.split(",") if s.strip()]
        assert decoded == [slug]

    def test_multiple_slugs_roundtrip(self):
        slugs = ["fruity", "chocolate.dark", "nutty.almond"]
        encoded = ",".join(slugs)
        decoded = [s.strip() for s in encoded.split(",") if s.strip()]
        assert decoded == slugs

    def test_empty_string_decodes_to_empty(self):
        decoded = [s.strip() for s in "".split(",") if s.strip()]
        assert decoded == []

    def test_comma_only_decodes_to_empty(self):
        decoded = [s.strip() for s in ",,,".split(",") if s.strip()]
        assert decoded == []
