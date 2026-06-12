"""
Tests for the WooCommerce-specific parser.

Coverage:
  TestWooCommerceParser   — WooCommerce fixture extraction + confidence scoring
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Fixture paths ─────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"
HTML_FIXTURES = FIXTURES / "html"


def _html(path: Path) -> bytes:
    return path.read_bytes()


class TestWooCommerceParser:
    @pytest.fixture
    def parser(self):
        from app.services.extraction.woocommerce_parser import WooCommerceParser
        return WooCommerceParser()

    def test_woocommerce_fixture_extraction(self, parser):
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
        assert "Heirloom" in str(p.varietal)

    def test_woocommerce_extracts_price(self, parser):
        """Should extract price from woocommerce-Price-amount."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        assert len(result.payload.price_variants) > 0
        pv = result.payload.price_variants[0]
        assert pv.price_gbp > 0

    def test_woocommerce_extracts_grind_variants(self, parser):
        """Select options for grind should populate grind_options."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        grind_opts = result.payload.grind_options
        assert len(grind_opts) > 0
        assert any("espresso" in opt.lower() or "filter" in opt.lower() for opt in grind_opts)

    def test_woocommerce_extracts_weight_variants(self, parser):
        """Select options for weight should populate weights list."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        weights = result.payload.weights
        assert len(weights) > 0
        assert 250 in weights or 1000 in weights

    def test_woocommerce_extracts_attributes_table(self, parser):
        """Should extract all fields from attributes table."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        p = result.payload
        # All attributes should be populated from the table
        assert p.origin_country  # Origin row
        assert p.origin_region    # Region row
        assert p.process          # Process row
        assert p.roast_level      # Roast row
        assert p.varietal         # Varietal row

    def test_woocommerce_confidence_higher_than_generic(self, parser):
        """WooCommerce parser should have higher confidence than generic HTML rules."""
        from app.services.extraction.html_parser import HtmlRulesParser

        html = _html(HTML_FIXTURES / "woocommerce_product.html")

        woo_result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        generic_parser = HtmlRulesParser()
        generic_result = generic_parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        # WooCommerce parser should achieve higher confidence when processing WooCommerce markup
        # (though both might do well on this fixture)
        assert woo_result.payload.confidence <= 0.80  # WooCommerce max confidence
        assert generic_result.payload.confidence <= 0.70  # Generic max confidence

        # On well-formed WooCommerce markup, WooCommerce parser should do at least as well
        assert woo_result.payload.confidence >= generic_result.payload.confidence

    def test_woocommerce_flavour_notes_from_description(self, parser):
        """Flavour notes in description should be extracted."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        notes_lower = [n.lower() for n in result.payload.flavour_notes]
        assert any("blueberry" in n or "chocolate" in n for n in notes_lower)

    def test_woocommerce_extraction_method(self, parser):
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        assert result.extraction_method == "woocommerce"

    def test_woocommerce_decaf_flag_detected(self, parser):
        decaf_html = b"""
        <html><body>
        <h1 class="product_title">Decaf Colombia Swiss Water</h1>
        <div class="woocommerce-product-details__short-description">
          <p>Our decaf offering using Swiss Water process. Suitable for espresso.</p>
        </div>
        <table class="woocommerce-product-attributes">
          <tr><th>Origin</th><td>Colombia</td></tr>
          <tr><th>Process</th><td>Swiss Water</td></tr>
        </table>
        <div class="price"><bdi>£11.00</bdi></div>
        </body></html>
        """
        result = parser.extract(decaf_html, "https://example.com/decaf")

        assert result.payload.decaf_flag is True

    def test_woocommerce_brew_suitability_from_description(self, parser):
        """Should detect brew suitability from description keywords."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        # Description mentions "espresso" and "cafetiere" (filter)
        assert "espresso" in result.payload.brew_suitability or len(result.payload.brew_suitability) > 0

    def test_woocommerce_roaster_from_og_meta(self, parser):
        """Should extract roaster name from og:site_name meta tag."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        # The fixture has og:site_name="Monmouth Coffee"
        assert result.payload.roaster_name == "Monmouth Coffee"

    def test_woocommerce_no_title_returns_invalid(self, parser):
        """Page with no product title should return invalid."""
        html = b"""
        <html><body>
        <h1>Just a heading</h1>
        <p>No product title here</p>
        </body></html>
        """
        result = parser.extract(html, "https://example.com/test")

        # Should fail to extract because no .product_title found
        assert result.validation_status == "invalid"

    def test_woocommerce_malformed_html_does_not_raise(self, parser):
        """Parser must never raise — bad HTML should return a result."""
        html = b"<html><body><<<<<not valid html>>>>}</body>"
        result = parser._safe_extract(html, "https://example.com")

        assert result is not None
        assert result.extraction_method == "woocommerce"

    def test_woocommerce_max_confidence_is_0_80(self, parser):
        """WooCommerce parser should cap confidence at 0.80."""
        html = _html(HTML_FIXTURES / "woocommerce_product.html")
        result = parser.extract(html, "https://monmouthcoffee.co.uk/products/test")

        assert result.payload.confidence <= 0.80
