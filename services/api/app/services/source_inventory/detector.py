"""
DomainDetector.

Runs all probes concurrently for a single domain and assembles the final
DomainDetectionResult. Uses a shared httpx.AsyncClient for connection reuse.

Concurrency model:
  - Homepage and Shopify probes fire concurrently.
  - Sitemap probe fires concurrently with the above.
  - Schema.org probe reuses homepage HTML where possible.
  - asyncio.gather with return_exceptions=True ensures one slow/failing probe
    never blocks the others.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.services.source_inventory.detection_result import DomainDetectionResult
from app.services.source_inventory.probers import (
    HEADERS,
    PROBE_TIMEOUT,
    probe_homepage,
    probe_schema_org,
    probe_shopify,
    probe_sitemap,
)

log = logging.getLogger(__name__)


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=HEADERS,
        timeout=PROBE_TIMEOUT,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


class DomainDetector:
    """
    Orchestrates concurrent probing of a single domain.
    
    Usage:
        async with DomainDetector() as detector:
            result = await detector.detect("shop.squaremilecoffee.com")
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "DomainDetector":
        if self._owns_client:
            self._client = _make_client()
        return self

    async def __aexit__(self, *_) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    async def detect(self, domain: str) -> DomainDetectionResult:
        """
        Run all probes against a domain and return an assembled result.
        
        Always returns a DomainDetectionResult — never raises.
        """
        domain = domain.strip().lower().rstrip("/")
        homepage_url = f"https://{domain}"
        log.info("Detecting %s", domain)

        result = DomainDetectionResult(domain=domain, homepage_url=homepage_url, reachable=False)

        try:
            # Fire homepage + shopify + sitemap concurrently
            homepage_task = probe_homepage(domain, self._client)
            shopify_task = probe_shopify(domain, self._client)
            sitemap_task = probe_sitemap(domain, self._client)

            homepage_result, shopify_result, sitemap_result = await asyncio.gather(
                homepage_task, shopify_task, sitemap_task,
                return_exceptions=True,
            )

            # Unwrap exceptions from gather (shouldn't happen — probes swallow errors)
            if isinstance(homepage_result, Exception):
                log.warning("Homepage probe exception for %s: %s", domain, homepage_result)
                from app.services.source_inventory.detection_result import HomepageProbeResult
                homepage_result = HomepageProbeResult(reachable=False, error=str(homepage_result))

            if isinstance(shopify_result, Exception):
                log.warning("Shopify probe exception for %s: %s", domain, shopify_result)
                from app.services.source_inventory.detection_result import ShopifyProbeResult
                shopify_result = ShopifyProbeResult(reachable=False, error=str(shopify_result))

            if isinstance(sitemap_result, Exception):
                log.warning("Sitemap probe exception for %s: %s", domain, sitemap_result)
                from app.services.source_inventory.detection_result import SitemapProbeResult
                sitemap_result = SitemapProbeResult(found=False, error=str(sitemap_result))

            result.homepage = homepage_result
            result.shopify = shopify_result
            result.sitemap = sitemap_result
            result.reachable = homepage_result.reachable

            # Schema.org probe — only run if homepage was reachable and Shopify not detected
            if homepage_result.reachable and not shopify_result.reachable:
                # We don't cache homepage HTML between probers, so pass None
                # (schema_org prober will re-fetch; acceptable for now)
                schema_result = await probe_schema_org(domain, self._client)
                if isinstance(schema_result, Exception):
                    from app.services.source_inventory.detection_result import SchemaOrgProbeResult
                    schema_result = SchemaOrgProbeResult(found=False, error=str(schema_result))
                result.schema_org = schema_result

            # Assign final strategy
            result.assign_strategy()

            # Add sitemap to discovered URLs if found
            if sitemap_result.found and sitemap_result.url:
                result.discovered_urls.append({
                    "url": sitemap_result.url,
                    "page_type": "sitemap",
                    "parser_strategy": result.parser_strategy,
                })

            log.info(
                "Detected %s → strategy=%s signals=%s",
                domain,
                result.parser_strategy,
                [s.value for s in result.signals],
            )

        except Exception as exc:
            log.error("Unexpected error detecting %s: %s", domain, exc, exc_info=True)
            result.error = str(exc)
            result.parser_strategy = "unknown"

        return result


class BulkDetector:
    """
    Runs DomainDetector across many domains with bounded concurrency.
    
    concurrency=10 is conservative — each domain fires 3–4 concurrent probes,
    so 10 domains means ~40 in-flight HTTP requests peak.
    """

    def __init__(self, concurrency: int = 10) -> None:
        self.concurrency = concurrency

    async def detect_all(
        self,
        domains: list[str],
        progress_callback=None,
    ) -> list[DomainDetectionResult]:
        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[DomainDetectionResult] = []

        async with _make_client() as client:
            async def _detect_one(domain: str) -> DomainDetectionResult:
                async with semaphore:
                    detector = DomainDetector(client=client)
                    result = await detector.detect(domain)
                    if progress_callback:
                        await progress_callback(domain, result)
                    return result

            tasks = [_detect_one(d) for d in domains]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        return list(results)
