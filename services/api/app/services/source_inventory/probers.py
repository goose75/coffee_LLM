"""
Domain prober.

Each probe is a standalone async function that takes a domain string and an
httpx.AsyncClient and returns a typed result dataclass. They are intentionally
decoupled so they can be tested in isolation with respx mocks.

Timeout strategy:
  - connect: 8s  (DNS + TCP)
  - read:    12s  (page body)
  - overall: 15s per probe

All probes swallow network errors and encode them in the result's .error field.
The caller (DomainDetector) decides how to aggregate.
"""

from __future__ import annotations

import json
import re
import logging
from urllib.parse import urljoin, urlparse

import httpx

from app.services.source_inventory.detection_result import (
    HomepageProbeResult,
    SchemaOrgProbeResult,
    ShopifyProbeResult,
    SitemapProbeResult,
)

log = logging.getLogger(__name__)

# ─── Shared timeouts ──────────────────────────────────────────────────────────

PROBE_TIMEOUT = httpx.Timeout(connect=8.0, read=12.0, write=5.0, pool=5.0)

HEADERS = {
    "User-Agent": (
        "CoffeePlatformBot/1.0 "
        "(+https://coffeeplatform.co.uk/bot; data@coffeeplatform.co.uk)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Pattern to detect Shopify in page source
_SHOPIFY_PATTERNS = [
    re.compile(r"Shopify\.theme", re.IGNORECASE),
    re.compile(r"cdn\.shopify\.com", re.IGNORECASE),
    re.compile(r"shopify-analytics", re.IGNORECASE),
    re.compile(r'"shop_id":\s*\d+', re.IGNORECASE),
]

# Schema.org Product JSON-LD detection
_SCHEMA_LD_PATTERN = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _normalise_domain(domain: str) -> str:
    """Ensure domain has no trailing slash and no scheme."""
    domain = domain.strip().rstrip("/")
    if domain.startswith(("http://", "https://")):
        domain = urlparse(domain).netloc
    return domain


def _base_url(domain: str) -> str:
    return f"https://{domain}"


# ─── Individual probes ────────────────────────────────────────────────────────

async def probe_homepage(domain: str, client: httpx.AsyncClient) -> HomepageProbeResult:
    """
    Fetch the homepage. Detects:
    - Reachability and final URL (after redirects)
    - Shopify meta signals in page source and response headers
    """
    url = _base_url(domain)
    try:
        resp = await client.get(url, timeout=PROBE_TIMEOUT, follow_redirects=True)
        text = resp.text

        is_shopify = (
            any(p.search(text) for p in _SHOPIFY_PATTERNS)
            or "x-shopid" in resp.headers
            or "x-shopify-stage" in resp.headers
        )

        return HomepageProbeResult(
            reachable=True,
            status_code=resp.status_code,
            is_shopify_meta=is_shopify,
            final_url=str(resp.url),
        )
    except httpx.TimeoutException as exc:
        log.debug("Homepage timeout for %s: %s", domain, exc)
        return HomepageProbeResult(reachable=False, error=f"timeout: {exc}")
    except httpx.RequestError as exc:
        log.debug("Homepage error for %s: %s", domain, exc)
        return HomepageProbeResult(reachable=False, error=str(exc))


async def probe_shopify(domain: str, client: httpx.AsyncClient) -> ShopifyProbeResult:
    """
    Probe /products.json?limit=1 to confirm Shopify availability.
    
    A 200 response with a JSON body containing a 'products' key is definitive.
    Some Shopify stores password-protect their storefront but still serve the feed.
    """
    feed_url = f"{_base_url(domain)}/products.json?limit=1"
    try:
        resp = await client.get(feed_url, timeout=PROBE_TIMEOUT, follow_redirects=True)

        if resp.status_code != 200:
            return ShopifyProbeResult(
                reachable=False,
                status_code=resp.status_code,
                feed_url=feed_url,
                error=f"HTTP {resp.status_code}",
            )

        try:
            data = resp.json()
        except json.JSONDecodeError:
            return ShopifyProbeResult(
                reachable=False,
                status_code=resp.status_code,
                feed_url=feed_url,
                error="response not valid JSON",
            )

        if "products" not in data:
            return ShopifyProbeResult(
                reachable=False,
                status_code=resp.status_code,
                feed_url=feed_url,
                error="JSON response missing 'products' key",
            )

        product_count = len(data["products"])
        # Get total product count hint from count endpoint
        count_url = f"{_base_url(domain)}/products/count.json"
        try:
            count_resp = await client.get(count_url, timeout=PROBE_TIMEOUT)
            if count_resp.status_code == 200:
                count_data = count_resp.json()
                product_count = count_data.get("count", product_count)
        except Exception:
            pass  # count is a nice-to-have

        return ShopifyProbeResult(
            reachable=True,
            status_code=resp.status_code,
            product_count=product_count,
            feed_url=f"{_base_url(domain)}/products.json",
        )

    except httpx.TimeoutException as exc:
        return ShopifyProbeResult(reachable=False, error=f"timeout: {exc}")
    except httpx.RequestError as exc:
        return ShopifyProbeResult(reachable=False, error=str(exc))


async def probe_sitemap(domain: str, client: httpx.AsyncClient) -> SitemapProbeResult:
    """
    Check /sitemap.xml availability.
    
    Tries /sitemap.xml first, then /sitemap_index.xml.
    Counts <loc> entries as a proxy for site scale (does not fetch sub-sitemaps).
    """
    candidates = [
        f"{_base_url(domain)}/sitemap.xml",
        f"{_base_url(domain)}/sitemap_index.xml",
    ]

    for url in candidates:
        try:
            resp = await client.get(url, timeout=PROBE_TIMEOUT, follow_redirects=True)
            if resp.status_code == 200 and (
                "xml" in resp.headers.get("content-type", "")
                or resp.text.strip().startswith("<?xml")
                or "<urlset" in resp.text
                or "<sitemapindex" in resp.text
            ):
                loc_count = resp.text.count("<loc>")
                return SitemapProbeResult(
                    found=True,
                    url=url,
                    status_code=resp.status_code,
                    url_count=loc_count,
                )
        except (httpx.TimeoutException, httpx.RequestError):
            continue

    return SitemapProbeResult(found=False)


async def probe_schema_org(
    domain: str,
    client: httpx.AsyncClient,
    homepage_html: str | None = None,
) -> SchemaOrgProbeResult:
    """
    Detect schema.org Product JSON-LD in the homepage HTML.
    
    Accepts pre-fetched HTML to avoid a second homepage request.
    Falls back to fetching /products or /shop if homepage has no products.
    """
    html = homepage_html

    if html is None:
        try:
            resp = await client.get(
                _base_url(domain), timeout=PROBE_TIMEOUT, follow_redirects=True
            )
            html = resp.text
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            return SchemaOrgProbeResult(found=False, error=str(exc))

    product_count = 0
    has_offer = False

    for match in _SCHEMA_LD_PATTERN.finditer(html):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Handle both single object and @graph array
        items = data if isinstance(data, list) else [data]
        # Flatten @graph if present
        graphs = []
        for item in items:
            if isinstance(item, dict) and "@graph" in item:
                graphs.extend(item["@graph"])
            else:
                graphs.append(item)

        for item in graphs:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "Product" in types:
                product_count += 1
                if "offers" in item or "Offer" in str(item):
                    has_offer = True

    if product_count > 0:
        return SchemaOrgProbeResult(
            found=True,
            product_count=product_count,
            has_offer=has_offer,
        )

    # Try a dedicated shop/products listing page if homepage had none
    for path in ["/products", "/shop", "/collections/all"]:
        try:
            resp = await client.get(
                urljoin(_base_url(domain), path),
                timeout=PROBE_TIMEOUT,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                continue
            for match in _SCHEMA_LD_PATTERN.finditer(resp.text):
                raw = match.group(1).strip()
                try:
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            product_count += 1
                except json.JSONDecodeError:
                    continue
            if product_count > 0:
                return SchemaOrgProbeResult(found=True, product_count=product_count)
        except (httpx.TimeoutException, httpx.RequestError):
            continue

    return SchemaOrgProbeResult(found=False)
