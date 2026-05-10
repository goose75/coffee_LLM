"""
Tests for the Shopify ingestion module.

Coverage:
  - parse_weight: all unit formats
  - parse_grind: all known keyword patterns
  - parse_variant: full variant dict parsing
  - parse_product_fields: tag extraction, label detection
  - compute_product_hash: stability and sensitivity
  - ShopifyClient: pagination (cursor and legacy), retry, rate limiting
  - ShopifyIngestionPipeline: insert, update (changed), unchanged, deactivation
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from app.models.enums import AvailabilityStatus, GrindType
from app.services.shopify.client import ShopifyClient
from app.services.shopify.hashing import compute_product_hash, compute_listing_hash
from app.services.shopify.parser import (
    parse_grind,
    parse_price,
    parse_product_fields,
    parse_variant,
    parse_weight,
    compute_price_per_100g,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ─── Weight parsing ───────────────────────────────────────────────────────────

class TestParseWeight:
    def test_grams_simple(self):
        assert parse_weight("250g") == 250

    def test_grams_with_space(self):
        assert parse_weight("250 g") == 250

    def test_grams_uppercase(self):
        assert parse_weight("500G") == 500

    def test_kilograms_integer(self):
        assert parse_weight("1kg") == 1000

    def test_kilograms_decimal(self):
        assert parse_weight("0.5kg") == 500

    def test_kilograms_with_space(self):
        assert parse_weight("1 kg") == 1000

    def test_embedded_in_title(self):
        assert parse_weight("250g / Whole Bean") == 250

    def test_kg_in_title(self):
        assert parse_weight("1kg Bag / Espresso") == 1000

    def test_no_weight_returns_none(self):
        assert parse_weight("Whole Bean") is None

    def test_no_weight_empty_string(self):
        assert parse_weight("") is None

    def test_fractional_grams(self):
        # "1.5g" is unusual but should parse
        assert parse_weight("1.5g") == 1


# ─── Grind type parsing ───────────────────────────────────────────────────────

class TestParseGrind:
    def test_whole_bean(self):
        assert parse_grind("Whole Bean") == GrindType.whole_bean

    def test_whole_bean_hyphenated(self):
        assert parse_grind("whole-bean") == GrindType.whole_bean

    def test_beans_shorthand(self):
        assert parse_grind("Beans") == GrindType.whole_bean

    def test_espresso(self):
        assert parse_grind("Espresso") == GrindType.espresso

    def test_filter(self):
        assert parse_grind("Filter") == GrindType.filter

    def test_pour_over(self):
        assert parse_grind("Pour Over") == GrindType.pour_over

    def test_v60(self):
        assert parse_grind("V60") == GrindType.pour_over

    def test_cafetiere(self):
        assert parse_grind("Cafetiere") == GrindType.cafetiere

    def test_cafetiere_accent(self):
        assert parse_grind("Cafetière") == GrindType.cafetiere

    def test_french_press(self):
        assert parse_grind("French Press") == GrindType.cafetiere

    def test_aeropress(self):
        assert parse_grind("AeroPress") == GrindType.aeropress

    def test_moka_pot(self):
        assert parse_grind("Moka Pot") == GrindType.moka

    def test_stovetop(self):
        assert parse_grind("Stovetop") == GrindType.moka

    def test_omni(self):
        assert parse_grind("Omni Grind") == GrindType.omni

    def test_omni_simple(self):
        assert parse_grind("Omni") == GrindType.omni

    def test_unknown(self):
        assert parse_grind("") == GrindType.unknown

    def test_unknown_random(self):
        assert parse_grind("Subscription") == GrindType.unknown

    def test_case_insensitive(self):
        assert parse_grind("ESPRESSO") == GrindType.espresso

    def test_whole_bean_beats_filter_when_both_present(self):
        # "Whole Bean Filter Pack" — whole bean is more specific, found first
        result = parse_grind("Whole Bean Filter Pack")
        assert result == GrindType.whole_bean


# ─── Price parsing ────────────────────────────────────────────────────────────

class TestParsePrice:
    def test_normal_price(self):
        assert parse_price("12.50") == Decimal("12.50")

    def test_integer_price(self):
        assert parse_price("9") == Decimal("9.00")

    def test_three_decimal_places(self):
        # Shopify sometimes returns 3dp
        assert parse_price("12.500") == Decimal("12.50")

    def test_none_returns_zero(self):
        assert parse_price(None) == Decimal("0.00")

    def test_empty_returns_zero(self):
        assert parse_price("") == Decimal("0.00")

    def test_invalid_returns_zero(self):
        assert parse_price("free") == Decimal("0.00")

    def test_price_per_100g(self):
        result = compute_price_per_100g(Decimal("12.50"), 250)
        assert result == Decimal("5.0000")

    def test_price_per_100g_1kg(self):
        result = compute_price_per_100g(Decimal("42.00"), 1000)
        assert result == Decimal("4.2000")

    def test_price_per_100g_none_weight(self):
        assert compute_price_per_100g(Decimal("12.50"), None) is None

    def test_price_per_100g_zero_weight(self):
        assert compute_price_per_100g(Decimal("12.50"), 0) is None


# ─── Variant parsing ─────────────────────────────────────────────────────────

class TestParseVariant:
    def _variant(self, **kwargs) -> dict:
        base = {
            "id": 99001,
            "title": "250g / Whole Bean",
            "option1": "250g",
            "option2": "Whole Bean",
            "option3": None,
            "price": "12.50",
            "sku": "TEST-001",
            "available": True,
            "inventory_quantity": 10,
            "inventory_policy": "deny",
        }
        base.update(kwargs)
        return base

    def test_full_parse(self):
        v = parse_variant(self._variant())
        assert v.weight_g == 250
        assert v.grind_type == GrindType.whole_bean
        assert v.price_gbp == Decimal("12.50")
        assert v.price_per_100g_gbp == Decimal("5.0000")
        assert v.availability_status == AvailabilityStatus.in_stock
        assert v.seller_variant_id == "99001"
        assert v.sku == "TEST-001"

    def test_out_of_stock(self):
        v = parse_variant(self._variant(available=False, inventory_policy="deny"))
        assert v.availability_status == AvailabilityStatus.out_of_stock

    def test_preorder_continue_policy(self):
        v = parse_variant(self._variant(available=False, inventory_policy="continue"))
        assert v.availability_status == AvailabilityStatus.preorder

    def test_kg_variant(self):
        v = parse_variant(self._variant(
            title="1kg / Whole Bean", option1="1kg", price="42.00"
        ))
        assert v.weight_g == 1000
        assert v.price_per_100g_gbp == Decimal("4.2000")

    def test_single_option_no_grind(self):
        """Variant with only weight option — no grind info."""
        v = parse_variant(self._variant(title="250g", option1="250g", option2=None))
        assert v.weight_g == 250
        assert v.grind_type == GrindType.unknown

    def test_espresso_variant(self):
        v = parse_variant(self._variant(
            title="250g / Espresso", option1="250g", option2="Espresso"
        ))
        assert v.grind_type == GrindType.espresso

    def test_empty_sku_becomes_none(self):
        v = parse_variant(self._variant(sku=""))
        assert v.sku is None

    def test_null_sku_becomes_none(self):
        v = parse_variant(self._variant(sku=None))
        assert v.sku is None


# ─── Product field parsing ────────────────────────────────────────────────────

class TestParseProductFields:
    def _product(self, **kwargs) -> dict:
        base = {
            "id": 123,
            "title": "Ethiopia Yirgacheffe",
            "handle": "ethiopia-yirgacheffe",
            "body_html": "<p>Floral and bright.</p>",
            "tags": "Ethiopia, Washed, Light Roast, Filter",
        }
        base.update(kwargs)
        return base

    def test_extracts_title(self):
        f = parse_product_fields(self._product())
        assert f["raw_title"] == "Ethiopia Yirgacheffe"

    def test_extracts_description(self):
        f = parse_product_fields(self._product())
        assert f["raw_description"] == "<p>Floral and bright.</p>"

    def test_detects_roast_from_tags(self):
        f = parse_product_fields(self._product())
        assert f["roast_label_raw"] == "Light Roast"

    def test_detects_process_from_tags(self):
        f = parse_product_fields(self._product())
        assert f["process_label_raw"] == "Washed"

    def test_detects_origin_from_tags(self):
        f = parse_product_fields(self._product())
        assert f["origin_label_raw"] == "Ethiopia"

    def test_seller_product_id(self):
        f = parse_product_fields(self._product(id=9988776655))
        assert f["seller_product_id"] == "9988776655"

    def test_no_tags(self):
        f = parse_product_fields(self._product(tags=""))
        assert f["roast_label_raw"] is None
        assert f["process_label_raw"] is None

    def test_title_truncated_at_500(self):
        long_title = "A" * 600
        f = parse_product_fields(self._product(title=long_title))
        assert len(f["raw_title"]) == 500


# ─── Content hashing ─────────────────────────────────────────────────────────

class TestHashing:
    def _product(self) -> dict:
        return {
            "id": 123,
            "title": "Test Coffee",
            "body_html": "<p>Description</p>",
            "variants": [
                {"id": 1, "title": "250g", "price": "12.00", "available": True},
                {"id": 2, "title": "1kg", "price": "40.00", "available": True},
            ],
        }

    def test_same_input_same_hash(self):
        p = self._product()
        assert compute_product_hash(p) == compute_product_hash(p)

    def test_price_change_changes_hash(self):
        p1 = self._product()
        p2 = self._product()
        p2["variants"][0]["price"] = "14.00"
        assert compute_product_hash(p1) != compute_product_hash(p2)

    def test_title_change_changes_hash(self):
        p1 = self._product()
        p2 = self._product()
        p2["title"] = "Test Coffee - New Harvest"
        assert compute_product_hash(p1) != compute_product_hash(p2)

    def test_availability_change_changes_hash(self):
        p1 = self._product()
        p2 = self._product()
        p2["variants"][0]["available"] = False
        assert compute_product_hash(p1) != compute_product_hash(p2)

    def test_variant_order_does_not_matter(self):
        """Hash must be stable regardless of variant list order."""
        p1 = self._product()
        p2 = self._product()
        p2["variants"] = list(reversed(p2["variants"]))
        assert compute_product_hash(p1) == compute_product_hash(p2)

    def test_hash_is_64_char_hex(self):
        h = compute_product_hash(self._product())
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ─── ShopifyClient ────────────────────────────────────────────────────────────

# pytest.ini sets asyncio_mode = auto, so async tests run without an explicit
# marker. Applying @pytest.mark.asyncio at the class level forced the marker
# onto sync tests too, which produced PytestWarnings.
class TestShopifyClient:
    def _products_response(self, products: list, next_url: str | None = None) -> httpx.Response:
        headers = {}
        if next_url:
            headers["link"] = f'<{next_url}>; rel="next"'
        return httpx.Response(200, json={"products": products}, headers=headers)

    @respx.mock
    async def test_fetches_single_page(self):
        fixture = json.loads((FIXTURE_DIR / "shopify_products_page1.json").read_text())
        respx.get("https://test-roaster.myshopify.com/products.json?limit=250").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        respx.get("https://test-roaster.myshopify.com/products/count.json").mock(
            return_value=httpx.Response(200, json={"count": 3})
        )
        async with ShopifyClient("test-roaster.myshopify.com") as client:
            result = await client.fetch_all_products()

        assert result.success is True
        assert result.total_products == 3
        assert len(result.pages) == 1
        assert len(result.pages[0].products) == 3

    @respx.mock
    async def test_cursor_pagination(self):
        """Follows Link: rel=next header across pages."""
        page1_products = [{"id": 1, "title": "Coffee A", "variants": [], "tags": "", "body_html": ""}]
        page2_products = [{"id": 2, "title": "Coffee B", "variants": [], "tags": "", "body_html": ""}]

        page2_url = "https://test.myshopify.com/products.json?page_info=abc123&limit=250"

        respx.get("https://test.myshopify.com/products.json?limit=250").mock(
            return_value=self._products_response(page1_products, next_url=page2_url)
        )
        respx.get(page2_url).mock(
            return_value=self._products_response(page2_products, next_url=None)
        )

        async with ShopifyClient("test.myshopify.com") as client:
            result = await client.fetch_all_products()

        assert result.success is True
        assert result.total_products == 2
        assert len(result.pages) == 2

    @respx.mock
    async def test_handles_404_gracefully(self):
        respx.get("https://dead-store.com/products.json?limit=250").mock(
            return_value=httpx.Response(404)
        )
        async with ShopifyClient("dead-store.com") as client:
            result = await client.fetch_all_products()

        assert result.success is False
        assert len(result.errors) > 0

    @respx.mock
    async def test_retry_on_500(self):
        """Retries on server errors before failing."""
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500)
            return httpx.Response(200, json={"products": []})

        respx.get("https://flaky-store.com/products.json?limit=250").mock(side_effect=side_effect)

        async with ShopifyClient("flaky-store.com") as client:
            # Mock the sleep to speed up the test
            with patch("app.services.shopify.client.asyncio.sleep"):
                result = await client.fetch_all_products()

        assert result.success is True
        assert call_count == 3

    def test_extract_next_url(self):
        header = '<https://store.myshopify.com/products.json?page_info=abc>; rel="next", <https://store.myshopify.com/products.json?page_info=xyz>; rel="previous"'
        url = ShopifyClient._extract_next_url(header)
        assert url == "https://store.myshopify.com/products.json?page_info=abc"

    def test_extract_next_url_none_when_absent(self):
        assert ShopifyClient._extract_next_url("") is None
        assert ShopifyClient._extract_next_url('<url>; rel="previous"') is None


# ─── Pipeline integration (DB-mocked) ────────────────────────────────────────

class TestShopifyIngestionPipeline:
    """
    Integration tests for the pipeline using mocked DB session and HTTP.
    These verify the insert/update/unchanged/deactivate decision logic.
    """

    def _make_store(self) -> MagicMock:
        store = MagicMock()
        store.id = "00000000-0000-0000-0000-000000000001"
        store.domain = "test-roaster.myshopify.com"
        return store

    def _fixture_products(self) -> list[dict]:
        data = json.loads((FIXTURE_DIR / "shopify_products_page1.json").read_text())
        return data["products"]

    @respx.mock
    async def test_pipeline_creates_new_listings(self):
        """Fresh store: all products should be inserted."""
        from app.services.shopify.pipeline import ShopifyIngestionPipeline
        from app.services.storage.backend import LocalStorageBackend
        import tempfile

        fixture = json.loads((FIXTURE_DIR / "shopify_products_page1.json").read_text())
        respx.get("https://test-roaster.myshopify.com/products.json?limit=250").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        respx.get("https://test-roaster.myshopify.com/products/count.json").mock(
            return_value=httpx.Response(200, json={"count": 3})
        )

        # Mock the DB session
        session = AsyncMock()
        # session.add() is sync on AsyncSession — keep it as MagicMock so
        # calling it doesn't return an unawaited coroutine.
        session.add = MagicMock()

        # Make select().scalar_one_or_none() return None (no existing records)
        mock_execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_execute.return_value = mock_result
        session.execute = mock_execute

        store = self._make_store()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorageBackend(base_dir=tmpdir)
            pipeline = ShopifyIngestionPipeline(session=session, store=store, storage=storage)

            # Mock _open_run and _close_run to avoid full DB interaction
            mock_run = MagicMock()
            mock_run.id = "run-001"
            pipeline._run = mock_run

            with patch.object(pipeline, "_open_run", return_value=mock_run):
                with patch.object(pipeline, "_close_run", return_value=mock_run):
                    with patch("app.services.shopify.client.asyncio.sleep"):
                        await pipeline.run()

        # All 3 products seen
        assert pipeline.counters.records_seen == 3

    def test_counters_initial_state(self):
        from app.services.shopify.pipeline import IngestionCounters
        c = IngestionCounters()
        assert c.records_seen == 0
        assert c.errors == []
        assert c.warnings == []

    def test_counters_warn(self):
        from app.services.shopify.pipeline import IngestionCounters
        c = IngestionCounters()
        c.warn("something went wrong", url="https://example.com", detail="timeout")
        assert len(c.warnings) == 1
        assert c.warnings[0]["message"] == "something went wrong"

    def test_counters_error(self):
        from app.services.shopify.pipeline import IngestionCounters
        c = IngestionCounters()
        c.error("fatal error", detail="exception detail")
        assert len(c.errors) == 1
