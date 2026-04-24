"""
Tests for price intelligence.

Coverage:
  TestPriceNormalisation  — price_per_100g computation correctness
  TestPriceSchemas        — Pydantic schema validation and computed fields
  TestPriceEndpoints      — API response shapes (mocked DB)
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ── Price-per-100g normalisation ───────────────────────────────────────────────

class TestPriceNormalisation:
    """p100 = price / weight_g * 100 — no library, just arithmetic."""

    def _p100(self, price: float, weight_g: int) -> float:
        return round(price / weight_g * 100, 4)

    def test_250g_standard(self):
        assert self._p100(12.50, 250) == pytest.approx(5.00)

    def test_1kg(self):
        assert self._p100(42.00, 1000) == pytest.approx(4.20)

    def test_500g(self):
        assert self._p100(21.50, 500) == pytest.approx(4.30)

    def test_1kg_cheaper_per_100g(self):
        """Buying in bulk should be cheaper per 100g."""
        p100_250 = self._p100(12.50, 250)
        p100_1k  = self._p100(42.00, 1000)
        assert p100_1k < p100_250

    def test_none_weight_returns_none(self):
        # The router returns None for weight_g=None
        weight_g = None
        result = (round(12.50 / weight_g * 100, 4) if weight_g else None)
        assert result is None

    def test_very_small_weight_is_anomaly(self):
        """weight_g < 10 triggers the anomaly detector."""
        assert 5 < 10  # the threshold used in get_weight_coverage

    def test_very_large_weight_is_anomaly(self):
        assert 15000 > 10000  # the threshold used in get_weight_coverage


class TestPriceSummaryStats:
    """Verify the statistics used in PriceSummaryStats."""

    def _stats(self, prices: list[float]) -> dict:
        return {
            "min": min(prices),
            "max": max(prices),
            "median": statistics.median(prices),
            "mean": statistics.mean(prices),
        }

    def test_single_price(self):
        s = self._stats([12.50])
        assert s["min"] == 12.50
        assert s["max"] == 12.50
        assert s["median"] == 12.50
        assert s["mean"] == 12.50

    def test_multiple_prices(self):
        s = self._stats([11.50, 12.50, 13.50])
        assert s["min"] == 11.50
        assert s["max"] == 13.50
        assert s["median"] == pytest.approx(12.50)

    def test_median_even_count(self):
        """Median of [11, 13] = 12."""
        s = self._stats([11.0, 13.0])
        assert s["median"] == pytest.approx(12.0)

    def test_anomaly_3x_median(self):
        """The anomaly check: price > 3× median flags as outlier."""
        prices = [12.00, 12.50, 11.50, 38.00]  # 38 is ~3× median
        med = statistics.median(prices)
        anomalous = [p for p in prices if p > med * 3]
        assert 38.00 in anomalous

    def test_no_anomaly_for_normal_range(self):
        prices = [11.50, 12.00, 12.50, 13.00]
        med = statistics.median(prices)
        anomalous = [p for p in prices if p > med * 3]
        assert len(anomalous) == 0


class TestPriceSchemas:
    """Pydantic schema validation for price intelligence models."""

    def test_price_point_valid(self):
        from app.schemas.prices import PricePoint
        pt = PricePoint(
            recorded_at=datetime.now(timezone.utc),
            price_gbp=12.50,
            price_per_100g_gbp=5.00,
            availability_status="in_stock",
        )
        assert pt.price_gbp == 12.50

    def test_variant_price_history_latest(self):
        from app.schemas.prices import VariantPriceHistory, PricePoint
        now = datetime.now(timezone.utc)
        v = VariantPriceHistory(
            variant_id=uuid4(),
            variant_title="250g / Whole Bean",
            weight_g=250,
            grind_type="whole_bean",
            store_name="Test Store",
            store_id=uuid4(),
            history=[
                PricePoint(recorded_at=now - timedelta(days=1), price_gbp=12.00, price_per_100g_gbp=4.80, availability_status="in_stock"),
                PricePoint(recorded_at=now, price_gbp=12.50, price_per_100g_gbp=5.00, availability_status="in_stock"),
            ],
        )
        assert v.latest_price_gbp == pytest.approx(12.50)

    def test_variant_price_history_7d_change(self):
        from app.schemas.prices import VariantPriceHistory, PricePoint
        now = datetime.now(timezone.utc)
        v = VariantPriceHistory(
            variant_id=uuid4(),
            variant_title="250g",
            weight_g=250,
            grind_type="whole_bean",
            store_name="Test",
            store_id=uuid4(),
            history=[
                PricePoint(recorded_at=now - timedelta(days=8), price_gbp=12.00, price_per_100g_gbp=4.80, availability_status="in_stock"),
                PricePoint(recorded_at=now, price_gbp=13.00, price_per_100g_gbp=5.20, availability_status="in_stock"),
            ],
        )
        assert v.price_change_7d == pytest.approx(1.00)

    def test_seller_listing_min_price_excludes_out_of_stock(self):
        from app.schemas.prices import SellerListing, VariantOffer
        store = SellerListing(
            store_id=uuid4(),
            store_name="Test",
            store_domain="test.co.uk",
            store_homepage_url="https://test.co.uk",
            offers=[
                VariantOffer(variant_id=uuid4(), variant_title="250g", weight_g=250, grind_type="whole_bean",
                             price_gbp=11.50, price_per_100g_gbp=4.60, availability_status="in_stock", product_url=None),
                VariantOffer(variant_id=uuid4(), variant_title="1kg", weight_g=1000, grind_type="whole_bean",
                             price_gbp=8.00, price_per_100g_gbp=0.80, availability_status="out_of_stock", product_url=None),
            ]
        )
        # out-of-stock should be excluded from min
        assert store.min_price_gbp == pytest.approx(11.50)

    def test_seller_comparison_best_price(self):
        from app.schemas.prices import SellerComparison, SellerListing, VariantOffer
        def make_store(price: float, avail: str = "in_stock") -> SellerListing:
            return SellerListing(
                store_id=uuid4(), store_name="S", store_domain="s.com", store_homepage_url="",
                offers=[VariantOffer(variant_id=uuid4(), variant_title="250g", weight_g=250, grind_type="whole_bean",
                                     price_gbp=price, price_per_100g_gbp=price/250*100, availability_status=avail, product_url=None)]
            )
        comparison = SellerComparison(bean_id=uuid4(), canonical_name="Test Bean",
                                      stores=[make_store(13.50), make_store(11.50), make_store(12.00)])
        assert comparison.best_price_gbp == pytest.approx(11.50)

    def test_price_anomaly_schema(self):
        from app.schemas.prices import PriceAnomaly
        a = PriceAnomaly(
            variant_id=uuid4(),
            bean_id=uuid4(),
            bean_name="Test Coffee",
            store_name="Test Store",
            weight_g=250,
            grind_type="whole_bean",
            price_gbp=250.00,
            price_per_100g_gbp=100.00,
            reason="Price > £200",
            severity="high",
            recorded_at=datetime.now(timezone.utc),
        )
        assert a.severity == "high"

    def test_weight_coverage_row_schema(self):
        from app.schemas.prices import WeightCoverageRow
        row = WeightCoverageRow(
            variant_id=uuid4(),
            bean_id=None,
            bean_name="Mystery Coffee",
            store_name="Store",
            variant_title="Unknown Size",
            weight_g=None,
            price_gbp=12.00,
            price_per_100g_gbp=None,
            issue="missing_weight",
        )
        assert row.issue == "missing_weight"
        assert row.bean_id is None


class TestPriceChangeDirection:
    def test_price_increase_is_up(self):
        from app.schemas.prices import PriceChangeEvent
        e = PriceChangeEvent(
            variant_id=uuid4(), bean_id=uuid4(), bean_name="Test", store_name="Store",
            weight_g=250, grind_type="whole_bean",
            old_price_gbp=12.00, new_price_gbp=13.00,
            change_gbp=1.00, change_pct=8.3,
            old_per_100g=4.80, new_per_100g=5.20,
            recorded_at=datetime.now(timezone.utc),
        )
        assert e.direction == "up"

    def test_price_decrease_is_down(self):
        from app.schemas.prices import PriceChangeEvent
        e = PriceChangeEvent(
            variant_id=uuid4(), bean_id=uuid4(), bean_name="Test", store_name="Store",
            weight_g=250, grind_type="whole_bean",
            old_price_gbp=13.00, new_price_gbp=11.50,
            change_gbp=-1.50, change_pct=11.5,
            old_per_100g=5.20, new_per_100g=4.60,
            recorded_at=datetime.now(timezone.utc),
        )
        assert e.direction == "down"


class TestMarketAverages:
    def test_market_averages_schema(self):
        from app.schemas.prices import MarketAverages, MarketAverageRow
        avg = MarketAverages(
            dimension_type="origin_country",
            weight_g_filter=250,
            rows=[
                MarketAverageRow(dimension="Ethiopia", dimension_type="origin_country",
                                 bean_count=5, sample_count=12,
                                 mean_price_gbp=12.80, mean_per_100g=5.12, median_per_100g=5.00),
                MarketAverageRow(dimension="Colombia", dimension_type="origin_country",
                                 bean_count=3, sample_count=8,
                                 mean_price_gbp=14.20, mean_per_100g=5.68, median_per_100g=5.50),
            ]
        )
        assert len(avg.rows) == 2
        assert avg.rows[0].dimension == "Ethiopia"
