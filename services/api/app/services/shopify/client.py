"""
Shopify products.json HTTP client.

Handles:
  - Paginated fetching via ?page= parameter (legacy) and Link header (cursor)
  - Rate limiting: Shopify public storefront allows ~2 req/s, we stay well under
  - Retry on transient errors (429, 5xx) with exponential backoff
  - Returns raw bytes per page for storage, plus parsed product dicts

Pagination strategy:
  Shopify's /products.json supports two pagination modes:
  1. Legacy: ?page=N&limit=250 (deprecated but widely supported on older stores)
  2. Cursor: Link response header with rel="next" (preferred for large catalogs)

  We attempt cursor pagination first (checking for Link header after page 1),
  falling back to page-number pagination if the header is absent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx

log = logging.getLogger(__name__)

# Shopify storefront API limits — stay conservative
PAGE_SIZE = 250
MAX_PAGES = 100          # Safety cap: 25,000 products max per store
REQUEST_DELAY_S = 0.6    # ~1.6 req/s — comfortable under Shopify's 2/s limit
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = [2.0, 5.0, 15.0]

HEADERS = {
    "User-Agent": (
        "CoffeePlatformBot/1.0 "
        "(+https://coffeeplatform.co.uk/bot; data@coffeeplatform.co.uk)"
    ),
    "Accept": "application/json",
}

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


@dataclass
class FetchedPage:
    """One page of products.json with its raw payload."""
    page_number: int
    url: str
    raw_bytes: bytes
    products: list[dict]
    is_last: bool = False


@dataclass
class FetchResult:
    """Complete result of fetching all pages for a store."""
    store_domain: str
    feed_url: str
    pages: list[FetchedPage] = field(default_factory=list)
    total_products: int = 0
    errors: list[dict] = field(default_factory=list)
    success: bool = True


class ShopifyClient:
    """
    Async Shopify products.json client.

    Usage:
        async with ShopifyClient("shop.squaremilecoffee.com") as client:
            result = await client.fetch_all_products()
    """

    def __init__(self, domain: str, http_client: httpx.AsyncClient | None = None) -> None:
        self.domain = domain.strip().lower().rstrip("/")
        self.base_url = f"https://{self.domain}"
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> "ShopifyClient":
        if self._owns_client:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=5.0),
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *_) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    # ── Public API ────────────────────────────────────────────────────────

    async def fetch_all_products(self) -> FetchResult:
        """
        Fetch all products from this store's /products.json feed.

        Returns a FetchResult containing every page's raw bytes and parsed
        product dicts. Never raises — errors are captured in result.errors.
        """
        result = FetchResult(
            store_domain=self.domain,
            feed_url=f"{self.base_url}/products.json",
        )

        try:
            async for page in self._paginate():
                result.pages.append(page)
                result.total_products += len(page.products)
                if page.is_last:
                    break
        except Exception as exc:
            log.error("Fatal error fetching %s: %s", self.domain, exc, exc_info=True)
            result.errors.append({"message": str(exc), "url": result.feed_url})
            result.success = False

        return result

    async def fetch_product_count(self) -> int | None:
        """Quick count probe — returns None on error."""
        url = f"{self.base_url}/products/count.json"
        try:
            resp = await self._get_with_retry(url)
            data = resp.json()
            return data.get("count")
        except Exception:
            return None

    # ── Pagination ────────────────────────────────────────────────────────

    async def _paginate(self) -> AsyncIterator[FetchedPage]:
        """
        Yield FetchedPage objects. Tries cursor pagination first, falls back
        to legacy page-number pagination.
        """
        first_url = f"{self.base_url}/products.json?limit={PAGE_SIZE}"
        page_num = 1

        resp = await self._get_with_retry(first_url)
        raw = resp.content
        data = resp.json()
        products = data.get("products", [])

        # Check for cursor-based pagination (Link: <...>; rel="next")
        link_header = resp.headers.get("link", "")
        next_url = self._extract_next_url(link_header)

        is_last = len(products) < PAGE_SIZE and next_url is None
        yield FetchedPage(
            page_number=page_num,
            url=first_url,
            raw_bytes=raw,
            products=products,
            is_last=is_last,
        )

        if is_last:
            return

        # Use cursor pagination if available, otherwise fall back to page numbers
        if next_url:
            async for page in self._cursor_paginate(next_url, page_num + 1):
                yield page
        else:
            async for page in self._legacy_paginate(page_num + 1):
                yield page

    async def _cursor_paginate(
        self, first_next_url: str, start_page: int
    ) -> AsyncIterator[FetchedPage]:
        next_url: str | None = first_next_url
        page_num = start_page

        while next_url and page_num <= MAX_PAGES:
            await asyncio.sleep(REQUEST_DELAY_S)

            resp = await self._get_with_retry(next_url)
            raw = resp.content
            data = resp.json()
            products = data.get("products", [])

            link_header = resp.headers.get("link", "")
            next_url = self._extract_next_url(link_header)

            is_last = next_url is None or len(products) == 0
            yield FetchedPage(
                page_number=page_num,
                url=next_url or "",
                raw_bytes=raw,
                products=products,
                is_last=is_last,
            )
            page_num += 1

            if len(products) == 0:
                break

    async def _legacy_paginate(self, start_page: int) -> AsyncIterator[FetchedPage]:
        page_num = start_page

        while page_num <= MAX_PAGES:
            await asyncio.sleep(REQUEST_DELAY_S)

            url = f"{self.base_url}/products.json?limit={PAGE_SIZE}&page={page_num}"
            resp = await self._get_with_retry(url)
            raw = resp.content
            data = resp.json()
            products = data.get("products", [])

            is_last = len(products) < PAGE_SIZE or len(products) == 0
            yield FetchedPage(
                page_number=page_num,
                url=url,
                raw_bytes=raw,
                products=products,
                is_last=is_last,
            )
            page_num += 1

            if is_last:
                break

    # ── HTTP with retry ───────────────────────────────────────────────────

    async def _get_with_retry(self, url: str) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt, backoff in enumerate(RETRY_BACKOFF_S[:RETRY_ATTEMPTS]):
            try:
                resp = await self._client.get(url)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", backoff))
                    log.warning("Rate limited by %s — waiting %.1fs", self.domain, retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code >= 500:
                    log.warning(
                        "Server error %d from %s (attempt %d) — retrying in %.1fs",
                        resp.status_code, url, attempt + 1, backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                log.warning(
                    "Network error fetching %s (attempt %d/%d): %s",
                    url, attempt + 1, RETRY_ATTEMPTS, exc,
                )
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(backoff)

        raise last_exc or RuntimeError(f"Failed to fetch {url} after {RETRY_ATTEMPTS} attempts")

    @staticmethod
    def _extract_next_url(link_header: str) -> str | None:
        """Extract the rel="next" URL from a Shopify Link header."""
        match = _LINK_NEXT_RE.search(link_header)
        return match.group(1) if match else None
