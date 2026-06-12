"""
Source Page Discovery — crawl sites to find product pages.

Discovers product pages by:
1. Fetching homepage
2. Parsing links
3. Filtering to product pages (heuristics)
4. Storing as source_pages
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)


class SourcePageDiscovery:
    """Discover product pages on a site."""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        # Heuristic patterns for product pages
        self.product_patterns = [
            r'/product[s]?/',
            r'/item[s]?/',
            r'/shop/',
            r'/coffee[s]?/',
            r'/beans?/',
            r'/catalog/',
            r'[\?&]product[_id]*=',
            r'[\?&]item[_id]*=',
        ]

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def discover(self, domain: str, homepage_url: str, max_pages: int = 100) -> list[str]:
        """
        Discover product pages on a site.

        Returns:
            List of product page URLs discovered
        """
        if not self.client:
            raise RuntimeError("Discovery not initialized. Use 'async with' context manager.")

        discovered = set()

        try:
            # Fetch homepage
            log.info(f"Discovering pages for {domain}...")
            html = await self._fetch_page(homepage_url)
            if not html:
                log.warning(f"Failed to fetch homepage for {domain}")
                return []

            # Extract all links from homepage
            links = self._extract_links(html, homepage_url)
            log.info(f"Found {len(links)} links on homepage")

            # Filter to likely product pages
            for link in links:
                if len(discovered) >= max_pages:
                    break

                if self._is_product_page(link):
                    discovered.add(link)

            log.info(f"Discovered {len(discovered)} product pages for {domain}")

        except Exception as e:
            log.error(f"Discovery error for {domain}: {e}")

        return sorted(list(discovered))

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return HTML."""
        if not self.client:
            return None

        try:
            response = await self.client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            log.debug(f"Fetch error for {url}: {e}")

        return None

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract all links from HTML."""
        links = []

        try:
            parser = HTMLParser(html)

            for link_elem in parser.css('a[href]'):
                href = link_elem.attributes.get('href')
                if not href:
                    continue

                # Convert relative to absolute
                absolute_url = urljoin(base_url, href)

                # Remove fragments
                if '#' in absolute_url:
                    absolute_url = absolute_url.split('#')[0]

                # Only include same-domain links
                if self._is_same_domain(base_url, absolute_url):
                    links.append(absolute_url)

        except Exception as e:
            log.debug(f"Link extraction error: {e}")

        return links

    def _is_product_page(self, url: str) -> bool:
        """Check if URL looks like a product page."""
        # Skip common non-product pages
        skip_patterns = [
            r'/about',
            r'/contact',
            r'/faq',
            r'/blog',
            r'/news',
            r'/account',
            r'/login',
            r'/register',
            r'/cart',
            r'/checkout',
            r'/privacy',
            r'/terms',
            r'/style\.css',
            r'\.jpg',
            r'\.png',
            r'\.pdf',
        ]

        for pattern in skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False

        # Check product patterns
        for pattern in self.product_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def _is_same_domain(self, base_url: str, target_url: str) -> bool:
        """Check if target URL is on same domain as base."""
        base_domain = urlparse(base_url).netloc.lower()
        target_domain = urlparse(target_url).netloc.lower()

        # Handle www prefix
        base_domain = base_domain.replace('www.', '')
        target_domain = target_domain.replace('www.', '')

        return base_domain == target_domain


async def discover_source_pages(
    domain: str,
    homepage_url: str,
    max_pages: int = 100
) -> list[str]:
    """Discover product pages for a store."""
    async with SourcePageDiscovery() as discovery:
        return await discovery.discover(domain, homepage_url, max_pages)
