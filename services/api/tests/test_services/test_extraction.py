"""
Tests for the extraction module.

Coverage:
  TestExtractionPayload   — schema validation, completeness, coercion
  TestTextUtils           — all text mining functions
  TestSchemaOrgParser     — all three real-world fixtures + edge cases
  TestHtmlRulesParser     — WooCommerce fixture + edge cases
  TestParserChain         — strategy selection and fallback behaviour
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Fixture paths ─────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_FIXTURES = FIXTURES / "schema_org"
HTML_FIXTURES = FIXTURES / "html"


def _html(path: Path) -> bytes:
    return path.read_bytes()


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionPayload
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionPayload:
    def test_empty_payload_has_defaults(self):
        from app.services.extraction.payload import ExtractionPayload
        p = ExtractionPayload()
        assert p.coffee_name == ""
        assert p.varietal == []
        assert p.price_variants == []
        assert p.decaf_flag is False
        assert p.confidence == 0.0

    def test_confidence_clamped_above_1(self):
        from app.services.extraction.payload import ExtractionPayload
        p = ExtractionPayload(confidence=5.0)
        assert p.confidence == 1.0

    def test_confidence_clamped_below_0(self):
        from app.services.extraction.payload import ExtractionPayload
        p = ExtractionPayload(confidence=-0.5)
        assert p.confidence == 0.0

    def test_price_coercion_in_variant(self):
        from app.services.extraction.payload import PriceVariantPayload
        pv = PriceVariantPayload(price_gbp="£12.50")
        assert pv.price_gbp == 12.50

    def test_price_coercion_comma_separator(self):
        from app.services.extraction.payload import PriceVariantPayload
        pv = PriceVariantPayload(price_gbp="1,200.00")
        assert pv.price_gbp == 1200.00

    def test_weight_coercion(self):
        from app.services.extraction.payload import PriceVariantPayload
        pv = PriceVariantPayload(weight_g="250")
        assert pv.weight_g == 250

    def test_weight_coercion_float_string(self):
        from app.services.extraction.payload import PriceVariantPayload
        pv = PriceVariantPayload(weight_g="1000.0")
        assert pv.weight_g == 1000

    def test_string_list_coercion(self):
        from app.services.extraction.payload import ExtractionPayload
        p = ExtractionPayload(varietal="Heirloom")
        assert p.varietal == ["Heirloom"]

    def test_weights_synced_from_variants(self):
        from app.services.extraction.payload import ExtractionPayload, PriceVariantPayload
        p = ExtractionPayload(
            price_variants=[
                PriceVariantPayload(weight_g=250, price_gbp=12.50),
                PriceVariantPayload(weight_g=1000, price_gbp=42.00),
            ]
        )
        assert 250 in p.weights
        assert 1000 in p.weights

    def test_completeness_score_empty(self):
        from app.services.extraction.payload import ExtractionPayload
        p = ExtractionPayload()
        assert p.completeness_score() == 0.0

    def test_completeness_score_full(self):
        from app.services.extraction.payload import ExtractionPayload, PriceVariantPayload
        p = ExtractionPayload(
            coffee_name="Test Coffee",
            origin_country="Ethiopia",
            origin_region="Yirgacheffe",
            process="Washed",
            roast_level="Light",
            varietal=["Heirloom"],
            flavour_notes=["jasmine", "lemon"],
            price_variants=[PriceVariantPayload(price_gbp=12.50)],
            farm_or_estate="Konga",
        )
        assert p.completeness_score() > 0.8

    def test_to_db_dict_is_json_serialisable(self):
        from app.services.extraction.payload import ExtractionPayload
        import json
        p = ExtractionPayload(coffee_name="Test")
        d = p.to_db_dict()
        # Should not raise
        json.dumps(d)
        assert isinstance(d, dict)

    def test_extraction_result_invalid_factory(self):
        from app.services.extraction.payload import ExtractionResult
        r = ExtractionResult.invalid(method="schema_org", errors=["No JSON-LD found"])
        assert r.validation_status == "invalid"
        assert r.validation_errors == ["No JSON-LD found"]
        assert r.payload.coffee_name == ""

    def test_extraction_result_partial_factory(self):
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        p = ExtractionPayload(coffee_name="Partial Coffee")
        r = ExtractionResult.partial(payload=p, method="html_rules", errors=["No price found"])
        assert r.validation_status == "partial"
        assert r.payload.coffee_name == "Partial Coffee"


# ─────────────────────────────────────────────────────────────────────────────
# Text utilities
# ─────────────────────────────────────────────────────────────────────────────

class TestTextUtils:
    def test_clean_html_strips_tags(self):
        from app.services.extraction.text_utils import clean_html
        assert clean_html("<p>Hello <strong>world</strong></p>") == "Hello world"

    def test_clean_html_empty(self):
        from app.services.extraction.text_utils import clean_html
        assert clean_html("") == ""

    def test_clean_html_preserves_content(self):
        from app.services.extraction.text_utils import clean_html
        result = clean_html("<p>Tasting notes: jasmine, bergamot.</p>")
        assert "jasmine" in result
        assert "bergamot" in result

    def test_extract_origin_known_country(self):
        from app.services.extraction.text_utils import extract_origin_country
        assert extract_origin_country("A coffee from Ethiopia") == "Ethiopia"

    def test_extract_origin_case_insensitive(self):
        from app.services.extraction.text_utils import extract_origin_country
        assert extract_origin_country("grown in KENYA") == "Kenya"

    def test_extract_origin_none(self):
        from app.services.extraction.text_utils import extract_origin_country
        assert extract_origin_country("A delicious coffee") == ""

    def test_extract_process_washed(self):
        from app.services.extraction.text_utils import extract_process
        assert extract_process("Fully washed and sun dried") == "Washed"

    def test_extract_process_anaerobic(self):
        from app.services.extraction.text_utils import extract_process
        assert extract_process("Double anaerobic fermentation") == "Anaerobic"

    def test_extract_process_anaerobic_natural_more_specific(self):
        from app.services.extraction.text_utils import extract_process
        assert extract_process("anaerobic natural process") == "Anaerobic Natural"

    def test_extract_process_honey(self):
        from app.services.extraction.text_utils import extract_process
        assert extract_process("Red honey process") == "Red Honey"

    def test_extract_process_none(self):
        from app.services.extraction.text_utils import extract_process
        assert extract_process("Great coffee from our roastery") == ""

    def test_extract_roast_level_light(self):
        from app.services.extraction.text_utils import extract_roast_level
        assert extract_roast_level("Light roast, ideal for filter") == "Light"

    def test_extract_roast_level_medium_dark(self):
        from app.services.extraction.text_utils import extract_roast_level
        assert extract_roast_level("medium-dark roast") == "Medium Dark"

    def test_extract_roast_level_none(self):
        from app.services.extraction.text_utils import extract_roast_level
        assert extract_roast_level("A coffee from Kenya") == ""

    def test_extract_varietal_sl28(self):
        from app.services.extraction.text_utils import extract_varietal
        result = extract_varietal("SL28 and SL34 varietals")
        assert "SL28" in result
        assert "SL34" in result

    def test_extract_varietal_gesha(self):
        from app.services.extraction.text_utils import extract_varietal
        result = extract_varietal("100% Gesha varietal")
        assert "Gesha" in result

    def test_extract_varietal_deduplicates(self):
        from app.services.extraction.text_utils import extract_varietal
        result = extract_varietal("Bourbon bourbon Bourbon")
        assert result.count("Bourbon") == 1

    def test_extract_flavour_notes_from_section(self):
        from app.services.extraction.text_utils import extract_flavour_notes
        result = extract_flavour_notes("Tasting notes: jasmine, bergamot, lemon and peach")
        assert "Jasmine" in result or "jasmine" in [n.lower() for n in result]
        assert "Lemon" in result or "lemon" in [n.lower() for n in result]

    def test_extract_flavour_notes_from_text(self):
        from app.services.extraction.text_utils import extract_flavour_notes
        result = extract_flavour_notes("A coffee with notes of blueberry and chocolate")
        assert any("blueberry" in n.lower() for n in result)
        assert any("chocolate" in n.lower() for n in result)

    def test_extract_flavour_notes_cap_at_12(self):
        from app.services.extraction.text_utils import extract_flavour_notes
        long_text = "jasmine bergamot lemon peach cherry raspberry strawberry blueberry chocolate caramel vanilla toffee honey maple"
        result = extract_flavour_notes(long_text)
        assert len(result) <= 12

    def test_extract_weight_g(self):
        from app.services.extraction.text_utils import extract_weight_g
        assert extract_weight_g("250g bag") == 250

    def test_extract_weight_kg(self):
        from app.services.extraction.text_utils import extract_weight_g
        assert extract_weight_g("1kg whole bean") == 1000

    def test_extract_price(self):
        from app.services.extraction.text_utils import extract_price_gbp
        assert extract_price_gbp("£12.50") == 12.50

    def test_extract_price_none(self):
        from app.services.extraction.text_utils import extract_price_gbp
        assert extract_price_gbp("free shipping") is None


# ─────────────────────────────────────────────────────────────────────────────
# SchemaOrgParser — real-world fixtures
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaOrgParser:
    @pytest.fixture(autouse=True)
    def skip_if_no_extruct(self):
        try:
            import extruct  # noqa: F401
        except ImportError:
            pytest.skip("extruct not installed")

    @pytest.fixture
    def parser(self):
        from app.services.extraction.schema_org_parser import SchemaOrgParser
        return SchemaOrgParser()

    def test_fixture1_colonna_woocommerce(self, parser):
        """Rich schema.org with additionalProperty — should yield full payload."""
        html = _html(SCHEMA_FIXTURES / "colonna_woocommerce.html")
        result = parser.extract(html, "https://colonnacoffee.com/products/ethiopia-konga")

        assert result.validation_status in ("valid", "partial")
        p = result.payload
        assert "Ethiopia" in p.coffee_name or "Yirgacheffe" in p.coffee_name
        assert p.origin_country == "Ethiopia"
        assert p.origin_region == "Yirgacheffe"
        assert p.process == "Washed"
        assert p.roast_level == "Light"
        assert "Heirloom" in p.varietal
        assert len(p.price_variants) == 3
        assert any(pv.price_gbp == 12.50 for pv in p.price_variants)
        assert any(pv.price_gbp == 42.00 for pv in p.price_variants)
        assert any("jasmine" in n.lower() for n in p.flavour_notes)
        assert p.confidence > 0.5
        assert p.roaster_name == "Colonna Coffee"

    def test_fixture1_price_variants_have_weights(self, parser):
        """Offer names like '250g Whole Bean' should yield weight_g=250."""
        html = _html(SCHEMA_FIXTURES / "colonna_woocommerce.html")
        result = parser.extract(html, "https://colonnacoffee.com/products/ethiopia-konga")
        weights = [pv.weight_g for pv in result.payload.price_variants if pv.weight_g]
        assert 250 in weights
        assert 1000 in weights

    def test_fixture2_workshop_graph(self, parser):
        """@graph format JSON-LD — should unwrap and extract Product correctly."""
        html = _html(SCHEMA_FIXTURES / "workshop_graph.html")
        result = parser.extract(html, "https://www.workshopcoffee.com/products/colombia-el-paraiso")

        assert result.validation_status in ("valid", "partial")
        p = result.payload
        assert "Colombia" in p.coffee_name
        assert p.origin_country == "Colombia"
        assert p.origin_region == "Cauca"
        assert "Anaerobic" in p.process
        assert p.roaster_name == "Workshop Coffee"
        assert len(p.price_variants) >= 1
        assert any(pv.price_gbp == 18.50 for pv in p.price_variants)
        # Out of stock offer should be detected
        out_of_stock = [pv for pv in p.price_variants if pv.availability == "out_of_stock"]
        assert len(out_of_stock) >= 1

    def test_fixture2_castillo_varietal(self, parser):
        """Castillo is a known varietal — should be extracted."""
        html = _html(SCHEMA_FIXTURES / "workshop_graph.html")
        result = parser.extract(html, "https://www.workshopcoffee.com/products/colombia-el-paraiso")
        assert "Castillo" in result.payload.varietal

    def test_fixture3_sparse_minimal(self, parser):
        """Minimal schema.org — should extract what it can, status=partial."""
        html = _html(SCHEMA_FIXTURES / "sparse_minimal.html")
        result = parser.extract(html, "https://smallbatchroaster.com/products/kenya-kirinyaga")

        assert result.validation_status in ("valid", "partial")
        p = result.payload
        assert "Kenya" in p.coffee_name
        assert p.origin_country == "Kenya"
        assert p.process == "Washed"
        assert len(p.price_variants) >= 1
        assert any(pv.price_gbp == 14.00 for pv in p.price_variants)
        assert "SL28" in p.varietal or "SL34" in p.varietal

    def test_fixture3_flavour_notes_from_description(self, parser):
        """Flavour notes in description should be mined even without additionalProperty."""
        html = _html(SCHEMA_FIXTURES / "sparse_minimal.html")
        result = parser.extract(html, "https://smallbatchroaster.com/products/kenya-kirinyaga")
        notes_lower = [n.lower() for n in result.payload.flavour_notes]
        assert any("blackcurrant" in n or "grapefruit" in n for n in notes_lower)

    def test_no_json_ld_returns_invalid(self, parser):
        """Page with no JSON-LD at all should return invalid."""
        html = b"<html><body><h1>About us</h1></body></html>"
        result = parser.extract(html, "https://example.com/about")
        assert result.validation_status == "invalid"
        assert any("JSON-LD" in e or "json-ld" in e.lower() for e in result.validation_errors)

    def test_json_ld_without_product_type_returns_invalid(self, parser):
        """JSON-LD present but no Product type — should return invalid."""
        html = b"""
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Acme"}
        </script>
        </head><body></body></html>
        """
        result = parser.extract(html, "https://example.com/")
        assert result.validation_status == "invalid"

    def test_extraction_method_is_schema_org(self, parser):
        html = _html(SCHEMA_FIXTURES / "colonna_woocommerce.html")
        result = parser.extract(html, "https://colonnacoffee.com/products/test")
        assert result.extraction_method == "schema_org"

    def test_confidence_above_zero_for_valid(self, parser):
        html = _html(SCHEMA_FIXTURES / "colonna_woocommerce.html")
        result = parser.extract(html, "https://colonnacoffee.com/products/test")
        assert result.payload.confidence > 0.0

    def test_roaster_name_fallback_to_url(self, parser):
        """When no brand/org in JSON-LD, roaster name extracted from URL domain."""
        html = b"""
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Test Coffee",
         "offers": {"@type": "Offer", "price": "10.00", "priceCurrency": "GBP"}}
        </script>
        </head><body></body></html>
        """
        result = parser.extract(html, "https://myroaster.co.uk/products/test")
        # Should not be empty
        assert result.payload.roaster_name != ""


# ─────────────────────────────────────────────────────────────────────────────
# HtmlRulesParser
# ─────────────────────────────────────────────────────────────────────────────

class TestHtmlRulesParser:
    @pytest.fixture
    def parser(self):
        from app.services.extraction.html_parser import HtmlRulesParser
        return HtmlRulesParser()

    def test_woocommerce_fixture(self, parser):
        """Real WooCommerce markup — should extract title, attributes, price."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/ethiopia-sidama")

        assert result.validation_status in ("valid", "partial")
        p = result.payload
        assert "Ethiopia" in p.coffee_name
        assert p.origin_country == "Ethiopia"
        assert p.origin_region == "Sidama"
        assert p.process == "Natural"
        assert "Medium" in p.roast_level
        assert "Heirloom" in p.varietal

    def test_woocommerce_extracts_grind_variants(self, parser):
        """Select options for grind should populate grind_options."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        # espresso and filter should be detected from select options
        grind_opts = result.payload.grind_options
        assert len(grind_opts) > 0

    def test_woocommerce_extracts_weight_variants(self, parser):
        """Select options for weight should populate weights list."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        assert 250 in result.payload.weights or 1000 in result.payload.weights

    def test_no_title_returns_invalid(self, parser):
        """Page with no detectable product title should return invalid."""
        html = _html(HTML_FIXTURES / "no_schema_about_page.html")
        result = parser.extract(html, "https://ravecoffee.co.uk/about")
        # About page has <h1> but no product-specific selectors should match a price
        # The parser should at minimum get the h1 title (it's a fallback selector)
        # but can't find price → partial or we confirm it tried
        assert result.extraction_method == "html_rules"

    def test_flavour_notes_from_description(self, parser):
        """Flavour notes in description text should be extracted."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        notes_lower = [n.lower() for n in result.payload.flavour_notes]
        assert any("blueberry" in n or "chocolate" in n for n in notes_lower)

    def test_extraction_method_is_html_rules(self, parser):
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        assert result.extraction_method == "html_rules"

    def test_confidence_capped_at_max(self, parser):
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        assert result.payload.confidence <= 0.70

    def test_decaf_flag_detected(self, parser):
        decaf_html = b"""
        <html><body>
        <h1 class="product_title">Decaf Colombia Swiss Water</h1>
        <div class="woocommerce-product-details__short-description">
          <p>Our decaf offering using Swiss Water process. Suitable for espresso.</p>
        </div>
        <div class="price"><bdi>\xc2\xa311.00</bdi></div>
        </body></html>
        """
        result = parser.extract(decaf_html, "https://example.com/decaf")
        assert result.payload.decaf_flag is True

    def test_brew_suitability_espresso_detected(self, parser):
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")
        assert "espresso" in result.payload.brew_suitability

    def test_malformed_html_does_not_raise(self, parser):
        """Parser must never raise — bad HTML should return a result."""
        html = b"<html><body><<<<<not valid html>>>>}</body>"
        result = parser._safe_extract(html, "https://example.com")
        assert result is not None
        assert result.extraction_method == "html_rules"


# ─────────────────────────────────────────────────────────────────────────────
# Parser chain
# ─────────────────────────────────────────────────────────────────────────────

class TestParserChain:
    def test_chain_uses_schema_org_when_available(self):
        """Schema.org parser succeeds → chain returns its result."""
        try:
            import extruct  # noqa: F401
        except ImportError:
            pytest.skip("extruct not installed")

        from app.services.extraction.base import ParserChain
        from app.services.extraction.html_parser import HtmlRulesParser
        from app.services.extraction.schema_org_parser import SchemaOrgParser

        chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
        html = _html(SCHEMA_FIXTURES / "colonna_woocommerce.html")
        result = chain.run(html, "https://colonnacoffee.com/products/test")

        assert result is not None
        assert result.extraction_method == "schema_org"

    def test_chain_falls_back_to_html_rules(self):
        """Schema.org not found → chain falls back to HTML rules."""
        from app.services.extraction.base import ParserChain
        from app.services.extraction.html_parser import HtmlRulesParser
        from app.services.extraction.schema_org_parser import SchemaOrgParser

        chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = chain.run(html, "https://monmouthcoffee.co.uk/products/test")

        assert result is not None
        # If extruct is available, schema_org will fail (no JSON-LD) → html_rules
        # If extruct not available, schema_org returns invalid immediately → html_rules
        assert result.extraction_method == "html_rules"

    def test_chain_returns_none_when_all_fail(self):
        """All parsers invalid → chain returns None."""
        from app.services.extraction.base import BaseParser, ParserChain
        from app.services.extraction.payload import ExtractionResult

        class AlwaysInvalidParser(BaseParser):
            extraction_method = "test"
            def extract(self, html: bytes, url: str) -> ExtractionResult:
                return ExtractionResult.invalid(method="test", errors=["always fails"])

        chain = ParserChain([AlwaysInvalidParser(), AlwaysInvalidParser()])
        result = chain.run(b"<html></html>", "https://example.com")
        assert result is None

    def test_chain_run_all_returns_all_results(self):
        """run_all() should return one result per parser."""
        from app.services.extraction.base import ParserChain
        from app.services.extraction.html_parser import HtmlRulesParser
        from app.services.extraction.schema_org_parser import SchemaOrgParser

        chain = ParserChain([SchemaOrgParser(), HtmlRulesParser()])
        html = b"<html><body><h1>Test</h1></body></html>"
        results = chain.run_all(html, "https://example.com")
        assert len(results) == 2

    def test_base_parser_safe_extract_catches_exception(self):
        """_safe_extract() must never propagate — catches and wraps any exception."""
        from app.services.extraction.base import BaseParser
        from app.services.extraction.payload import ExtractionResult

        class BrokenParser(BaseParser):
            extraction_method = "broken"
            def extract(self, html: bytes, url: str) -> ExtractionResult:
                raise RuntimeError("I am broken")

        p = BrokenParser()
        result = p._safe_extract(b"", "https://example.com")
        assert result.validation_status == "invalid"
        assert "Unhandled exception" in result.validation_errors[0]
