"""
Tests for source inventory probers.

Uses respx to mock httpx requests — no real network calls.
Each prober is tested in isolation with representative responses.
"""

from __future__ import annotations

import json
import pytest
import respx
import httpx

from app.services.source_inventory.probers import (
    probe_homepage,
    probe_shopify,
    probe_sitemap,
    probe_schema_org,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SHOPIFY_PRODUCTS_JSON = json.dumps({
    "products": [
        {
            "id": 123456,
            "title": "Ethiopia Yirgacheffe",
            "handle": "ethiopia-yirgacheffe",
            "variants": [
                {"id": 1, "title": "250g / Whole Bean", "price": "12.50"},
                {"id": 2, "title": "1kg / Whole Bean", "price": "42.00"},
            ],
        }
    ]
})

SHOPIFY_COUNT_JSON = json.dumps({"count": 42})

SCHEMA_ORG_HTML = """
<!DOCTYPE html>
<html>
<head><title>Acme Coffee</title></head>
<body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Kenya AA",
  "offers": {
    "@type": "Offer",
    "price": "14.00",
    "priceCurrency": "GBP"
  }
}
</script>
</body>
</html>
"""

SHOPIFY_META_HTML = """
<!DOCTYPE html>
<html>
<head><title>Shop</title></head>
<body>
<script>
  var Shopify = Shopify || {};
  Shopify.theme = {"name": "Dawn"};
  var meta = {"shop_id": 99887766};
</script>
</body>
</html>
"""

PLAIN_HTML = "<html><body><h1>Welcome to our coffee shop</h1></body></html>"

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/products/coffee-a</loc></url>
  <url><loc>https://example.com/products/coffee-b</loc></url>
  <url><loc>https://example.com/products/coffee-c</loc></url>
</urlset>
"""


# ─── probe_homepage ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_probe_homepage_reachable_plain():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=PLAIN_HTML))
    async with httpx.AsyncClient() as client:
        result = await probe_homepage("example.com", client)
    assert result.reachable is True
    assert result.status_code == 200
    assert result.is_shopify_meta is False


@pytest.mark.asyncio
@respx.mock
async def test_probe_homepage_detects_shopify_meta():
    respx.get("https://shopifystore.com").mock(
        return_value=httpx.Response(200, text=SHOPIFY_META_HTML)
    )
    async with httpx.AsyncClient() as client:
        result = await probe_homepage("shopifystore.com", client)
    assert result.reachable is True
    assert result.is_shopify_meta is True


@pytest.mark.asyncio
@respx.mock
async def test_probe_homepage_unreachable():
    respx.get("https://deadsite.com").mock(side_effect=httpx.ConnectError("refused"))
    async with httpx.AsyncClient() as client:
        result = await probe_homepage("deadsite.com", client)
    assert result.reachable is False
    assert result.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_probe_homepage_timeout():
    respx.get("https://slowsite.com").mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await probe_homepage("slowsite.com", client)
    assert result.reachable is False
    assert "timeout" in result.error


# ─── probe_shopify ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_probe_shopify_success():
    respx.get("https://roaster.myshopify.com/products.json?limit=1").mock(
        return_value=httpx.Response(200, text=SHOPIFY_PRODUCTS_JSON)
    )
    respx.get("https://roaster.myshopify.com/products/count.json").mock(
        return_value=httpx.Response(200, text=SHOPIFY_COUNT_JSON)
    )
    async with httpx.AsyncClient() as client:
        result = await probe_shopify("roaster.myshopify.com", client)
    assert result.reachable is True
    assert result.product_count == 42
    assert result.feed_url == "https://roaster.myshopify.com/products.json"


@pytest.mark.asyncio
@respx.mock
async def test_probe_shopify_404():
    respx.get("https://nonshopify.com/products.json?limit=1").mock(
        return_value=httpx.Response(404)
    )
    async with httpx.AsyncClient() as client:
        result = await probe_shopify("nonshopify.com", client)
    assert result.reachable is False
    assert "404" in result.error


@pytest.mark.asyncio
@respx.mock
async def test_probe_shopify_invalid_json():
    respx.get("https://weirdsite.com/products.json?limit=1").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    async with httpx.AsyncClient() as client:
        result = await probe_shopify("weirdsite.com", client)
    assert result.reachable is False
    assert "not valid JSON" in result.error


@pytest.mark.asyncio
@respx.mock
async def test_probe_shopify_json_missing_products_key():
    respx.get("https://partialsite.com/products.json?limit=1").mock(
        return_value=httpx.Response(200, text='{"items": []}')
    )
    async with httpx.AsyncClient() as client:
        result = await probe_shopify("partialsite.com", client)
    assert result.reachable is False
    assert "products" in result.error


# ─── probe_sitemap ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_probe_sitemap_found():
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP_XML, headers={"content-type": "application/xml"})
    )
    async with httpx.AsyncClient() as client:
        result = await probe_sitemap("example.com", client)
    assert result.found is True
    assert result.url == "https://example.com/sitemap.xml"
    assert result.url_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_probe_sitemap_tries_index_fallback():
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/sitemap_index.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP_XML, headers={"content-type": "application/xml"})
    )
    async with httpx.AsyncClient() as client:
        result = await probe_sitemap("example.com", client)
    assert result.found is True
    assert "sitemap_index" in result.url


@pytest.mark.asyncio
@respx.mock
async def test_probe_sitemap_not_found():
    respx.get("https://nositemapsite.com/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get("https://nositemapsite.com/sitemap_index.xml").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        result = await probe_sitemap("nositemapsite.com", client)
    assert result.found is False


# ─── probe_schema_org ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_probe_schema_org_found_in_html():
    """Schema.org probe reuses provided HTML without making a network call."""
    from app.services.source_inventory.probers import probe_schema_org
    async with httpx.AsyncClient() as client:
        result = await probe_schema_org("example.com", client, homepage_html=SCHEMA_ORG_HTML)
    assert result.found is True
    assert result.product_count == 1
    assert result.has_offer is True


@pytest.mark.asyncio
async def test_probe_schema_org_not_found_in_plain_html():
    async with httpx.AsyncClient() as client:
        result = await probe_schema_org("example.com", client, homepage_html=PLAIN_HTML)
    assert result.found is False
    assert result.product_count == 0


@pytest.mark.asyncio
async def test_probe_schema_org_graph_format():
    """Handles @graph array format."""
    graph_html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {"@type": "WebSite", "name": "Acme"},
        {"@type": "Product", "name": "Coffee A", "offers": {"@type": "Offer", "price": "10"}}
      ]
    }
    </script>
    """
    async with httpx.AsyncClient() as client:
        result = await probe_schema_org("example.com", client, homepage_html=graph_html)
    assert result.found is True
    assert result.product_count == 1


# ─── Strategy assignment ──────────────────────────────────────────────────────

def test_detection_result_assign_strategy_shopify():
    from app.services.source_inventory.detection_result import (
        DomainDetectionResult, ShopifyProbeResult, HomepageProbeResult, SitemapProbeResult
    )
    result = DomainDetectionResult(domain="test.com", homepage_url="https://test.com", reachable=True)
    result.homepage = HomepageProbeResult(reachable=True, status_code=200)
    result.shopify = ShopifyProbeResult(reachable=True, product_count=10, feed_url="https://test.com/products.json")
    result.sitemap = SitemapProbeResult(found=True, url="https://test.com/sitemap.xml")
    result.assign_strategy()
    assert result.parser_strategy == "shopify"
    assert result.source_type == "shopify"
    assert any(u["page_type"] == "feed" for u in result.discovered_urls)


def test_detection_result_assign_strategy_schema_org():
    from app.services.source_inventory.detection_result import (
        DomainDetectionResult, ShopifyProbeResult, HomepageProbeResult,
        SitemapProbeResult, SchemaOrgProbeResult
    )
    result = DomainDetectionResult(domain="test.com", homepage_url="https://test.com", reachable=True)
    result.homepage = HomepageProbeResult(reachable=True, final_url="https://test.com")
    result.shopify = ShopifyProbeResult(reachable=False, error="404")
    result.sitemap = SitemapProbeResult(found=False)
    result.schema_org = SchemaOrgProbeResult(found=True, product_count=2)
    result.assign_strategy()
    assert result.parser_strategy == "schema_org"


def test_detection_result_assign_strategy_html_fallback():
    from app.services.source_inventory.detection_result import (
        DomainDetectionResult, ShopifyProbeResult, HomepageProbeResult,
        SitemapProbeResult, SchemaOrgProbeResult
    )
    result = DomainDetectionResult(domain="test.com", homepage_url="https://test.com", reachable=True)
    result.homepage = HomepageProbeResult(reachable=True)
    result.shopify = ShopifyProbeResult(reachable=False)
    result.sitemap = SitemapProbeResult(found=False)
    result.schema_org = SchemaOrgProbeResult(found=False)
    result.assign_strategy()
    assert result.parser_strategy == "html"


def test_detection_result_assign_strategy_unreachable():
    from app.services.source_inventory.detection_result import (
        DomainDetectionResult, HomepageProbeResult
    )
    result = DomainDetectionResult(domain="dead.com", homepage_url="https://dead.com", reachable=False)
    result.homepage = HomepageProbeResult(reachable=False, error="connection refused")
    result.assign_strategy()
    assert result.parser_strategy == "unknown"
