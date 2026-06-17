"""
HTML Ingestion Pipeline.

Extracts products from HTML storefronts using schema.org/html/llm extraction chain.
Follows ShopifyIngestionPipeline pattern exactly.

Pipeline steps per store:
  1. Open ingestion_run record (status=running)
  2. Fetch all source_pages for this store (or discover from homepage)
  3. For each page: fetch HTML, extract products via HtmlExtractor
  4. For each product: compute hash, check against bean_listing.content_hash
     a. Hash unchanged → update last_seen_at, append price_history only
     b. Hash changed   → upsert bean_listing, upsert listing_variants, append price_history
     c. New product    → insert bean_listing, insert listing_variants, append price_history
  5. Mark products missing from discovery as inactive
  6. Close ingestion_run (status=completed|partial|failed)
"""

from __future__ import annotations

import hashlib
import logging
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bean_listing import BeanListing
from app.models.enums import (
    AvailabilityStatus,
    GrindType,
    ListingStatus,
    RunStatus,
    RunType,
    PageType,
    ParserStrategy,
)
from app.models.ingestion_run import IngestionRun
from app.models.pricing import ListingVariant, PriceHistory
from app.models.source_page import SourcePage
from app.models.store import Store
from app.services.extraction.payload import ExtractionPayload, ExtractionResult
from app.services.storage.backend import StorageBackend, compute_hash, get_storage_backend
from .extractor import HtmlExtractor
from .product_page_detector import ProductPageDetector

# Type alias for clarity
ExtractionResultType = ExtractionResult

log = logging.getLogger(__name__)


@dataclass
class IngestionCounters:
    """Mutable counters threaded through the pipeline."""

    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    warnings: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def warn(
        self, message: str, url: str | None = None, detail: str | None = None
    ) -> None:
        self.warnings.append({"message": message, "url": url, "detail": detail})
        log.warning("%s | %s", message, detail or "")

    def error(
        self, message: str, url: str | None = None, detail: str | None = None
    ) -> None:
        self.errors.append({"message": message, "url": url, "detail": detail})
        log.error("%s | %s", message, detail or "")


class HtmlIngestionPipeline:
    """
    Ingests products from an HTML storefront into the platform database.

    Uses extraction chain (schema.org → html rules → llm) to parse product data,
    then populates bean_listing and listing_variant tables.

    Usage:
        pipeline = HtmlIngestionPipeline(session, store)
        run = await pipeline.run()
    """

    def __init__(
        self,
        session: AsyncSession,
        store: Store,
        storage: StorageBackend | None = None,
    ) -> None:
        self.session = session
        self.store = store
        self.storage = storage or get_storage_backend()
        self.extractor = HtmlExtractor()
        self.counters = IngestionCounters()
        self._run: IngestionRun | None = None
        self._now = datetime.now(timezone.utc)
        # Use realistic browser User-Agent to avoid bot blocking
        # Many sites block requests with "Bot" in the User-Agent
        self._user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(self) -> IngestionRun:
        """
        Execute the full HTML ingestion pipeline for this store.
        Always returns an IngestionRun — never raises.
        """
        print(f"🔥 HtmlIngestionPipeline.run() STARTED for {self.store.domain}")
        log.info(f"HtmlIngestionPipeline.run() started for {self.store.domain}")
        self._run = await self._open_run()
        print(f"🔥 Opened run: {self._run.id}")

        try:
            # Fetch all source pages for this store
            print(f"🔥 Fetching source pages for {self.store.domain}")
            source_pages = await self._fetch_source_pages()
            print(f"🔥 Found {len(source_pages)} source pages")

            if not source_pages:
                self.counters.warn(
                    f"No source pages found for {self.store.domain}",
                    detail="Store has no discovered product pages",
                )
                return await self._close_run(RunStatus.partial)

            # Track which seller_product_ids we see in this run
            seen_seller_ids: set[str] = set()

            for source_page in source_pages:
                await self._process_page(source_page, seen_seller_ids)

            # Mark products absent from discovery as inactive
            await self._deactivate_missing(seen_seller_ids)

            # Only stamp successful crawl on clean run
            status = RunStatus.partial if self.counters.errors else RunStatus.completed
            if status == RunStatus.completed:
                await self._update_store_crawl_time()
            return await self._close_run(status)

        except Exception as exc:
            log.error(
                "Pipeline failure for %s: %s", self.store.domain, exc, exc_info=True
            )
            bucket = _classify_pipeline_exception(exc)
            self.counters.error(f"{bucket}: {exc}", detail=repr(exc))
            return await self._close_run(RunStatus.failed)

    # ── Page discovery ────────────────────────────────────────────────────────

    async def _fetch_source_pages(self) -> list[SourcePage]:
        """
        Get all known source_pages for this store.
        If none exist, try to discover from sitemap.xml, then breadth-first crawl, then homepage.
        """
        stmt = (
            select(SourcePage)
            .where(SourcePage.store_id == self.store.id)
            .order_by(SourcePage.discovered_at)
        )
        pages = (await self.session.execute(stmt)).scalars().all()

        if not pages:
            # Try to discover from sitemap.xml
            sitemap_urls = await self._discover_from_sitemap()

            if sitemap_urls:
                # Create source pages from discovered URLs
                for url in sitemap_urls[:200]:  # Limit to 200 pages per run
                    source_page = SourcePage(
                        store_id=self.store.id,
                        url=url,
                        page_type=PageType.product,
                        parser_strategy=ParserStrategy.html,
                        discovered_at=self._now,
                    )
                    self.session.add(source_page)
                await self.session.flush()
                pages = (await self.session.execute(stmt)).scalars().all()
            else:
                # Fallback: Try breadth-first crawl from homepage
                log.info(f"Sitemap discovery failed for {self.store.domain}, trying breadth-first crawl...")
                crawled_urls = await self._discover_from_homepage_crawl()

                if crawled_urls:
                    # Create source pages from crawled URLs
                    for url in crawled_urls[:200]:  # Limit to 200 pages per run
                        source_page = SourcePage(
                            store_id=self.store.id,
                            url=url,
                            page_type=PageType.product,
                            parser_strategy=ParserStrategy.html,
                            discovered_at=self._now,
                        )
                        self.session.add(source_page)
                    await self.session.flush()
                    pages = (await self.session.execute(stmt)).scalars().all()
                else:
                    # Final fallback: Create homepage page as starting point
                    log.warning(f"No product pages found for {self.store.domain}, using homepage only")
                    homepage_url = self.store.homepage_url or f"https://{self.store.domain}"
                    source_page = SourcePage(
                        store_id=self.store.id,
                        url=homepage_url,
                        page_type=PageType.homepage,
                        parser_strategy=ParserStrategy.html,
                        discovered_at=self._now,
                    )
                    self.session.add(source_page)
                    await self.session.flush()
                    pages = [source_page]

        return pages

    async def _discover_from_sitemap(self) -> list[str]:
        """
        Fetch and parse sitemap.xml to discover product page URLs.

        Returns:
            List of product URLs found in sitemap, deduplicated and filtered.
            Returns empty list if sitemap not found or unparseable.
        """
        sitemap_url = f"https://{self.store.domain}/sitemap.xml"

        try:
            log.debug(f"Attempting to discover product pages from {sitemap_url}")

            # Fetch sitemap.xml with proper headers
            headers = {
                "User-Agent": self._user_agent,
                "Accept": "application/xml,text/xml,*/*;q=0.9",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            req = urllib.request.Request(sitemap_url, headers=headers)

            # Retry on transient errors (429, 503)
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=15) as response:
                        sitemap_bytes = response.read()
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code in (429, 503) and attempt < 2:
                        import time
                        wait_time = 2 ** attempt
                        log.warning(f"Rate limited on sitemap ({exc.code}), retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    raise

            # Parse XML
            root = ET.fromstring(sitemap_bytes)

            # Extract all URLs from sitemap
            # Standard sitemap namespace
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []
            for loc in root.findall(".//sm:loc", ns):
                if loc.text:
                    urls.append(loc.text.strip())

            # If no URLs found with namespace, try without namespace
            if not urls:
                for loc in root.findall(".//loc"):
                    if loc.text:
                        urls.append(loc.text.strip())

            log.debug(f"Found {len(urls)} URLs in sitemap")

            # Filter to likely product pages using improved detector
            product_urls = set()
            for url in urls:
                is_product, reason = ProductPageDetector.is_product_page_by_url(url)
                if is_product:
                    product_urls.add(url)

            log.info(
                f"Discovered {len(product_urls)} product pages for {self.store.domain} "
                f"from {len(urls)} total sitemap entries"
            )

            return sorted(list(product_urls))

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                log.debug(f"Sitemap not found at {sitemap_url}")
            else:
                log.warning(f"HTTP {exc.code} fetching sitemap: {exc.reason}")
            return []
        except urllib.error.URLError as exc:
            log.debug(f"URL error fetching sitemap: {exc.reason}")
            return []
        except ET.ParseError as exc:
            log.warning(f"Failed to parse sitemap XML: {exc}")
            return []
        except Exception as exc:
            log.warning(f"Error discovering from sitemap: {exc}")
            return []

    async def _discover_from_homepage_crawl(self) -> list[str]:
        """
        Breadth-first crawl from homepage to find product pages.

        Uses BFS to crawl up to 50 pages looking for product links.
        Uses improved product page detector with both URL patterns and HTML analysis.
        """
        homepage_url = self.store.homepage_url or f"https://{self.store.domain}"
        product_urls = set()
        visited = set()
        queue = [homepage_url]

        max_crawl_pages = 50  # Limit crawl depth to avoid excessive requests

        try:
            while queue and len(visited) < max_crawl_pages:
                url = queue.pop(0)
                if url in visited:
                    continue

                visited.add(url)

                try:
                    # Fetch page with timeout and browser headers
                    headers = {
                        "User-Agent": self._user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                    }
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        html_bytes = response.read()

                    html_text = html_bytes.decode('utf-8', errors='ignore')

                    # Check if current page is a product page (with HTML analysis)
                    is_product, reason = ProductPageDetector.is_product_page(url, html_text)
                    if is_product:
                        product_urls.add(url)
                        log.debug(f"Detected product page {url}: {reason}")

                    # Parse HTML to find links
                    from html.parser import HTMLParser

                    class LinkExtractor(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.links = []

                        def handle_starttag(self, tag, attrs):
                            if tag == "a":
                                for attr, value in attrs:
                                    if attr == "href" and value:
                                        self.links.append(value)

                    extractor = LinkExtractor()
                    extractor.feed(html_text)

                    # Process discovered links
                    for link in extractor.links:
                        # Convert relative URLs to absolute
                        if link.startswith('/'):
                            link = f"https://{self.store.domain}{link}"
                        elif link.startswith('http'):
                            pass
                        else:
                            link = f"https://{self.store.domain}/{link}"

                        # Remove fragments and query params for matching
                        clean_url = link.split('#')[0].split('?')[0]

                        # Check if it looks like a product page by URL (quick check)
                        is_product_by_url, _ = ProductPageDetector.is_product_page_by_url(clean_url)
                        if is_product_by_url:
                            product_urls.add(link)

                        # Add to queue if it's from same domain and not yet visited
                        if clean_url not in visited and self.store.domain in clean_url:
                            queue.append(clean_url)

                except urllib.error.HTTPError as exc:
                    log.debug(f"HTTP {exc.code} crawling {url}: {exc.reason}")
                except urllib.error.URLError as exc:
                    log.debug(f"URL error crawling {url}: {exc.reason}")
                except Exception as exc:
                    log.debug(f"Error crawling {url}: {exc}")

            log.info(
                f"Discovered {len(product_urls)} product pages for {self.store.domain} "
                f"from breadth-first crawl ({len(visited)} pages visited)"
            )
            return sorted(list(product_urls))

        except Exception as exc:
            log.warning(f"Error in homepage crawl for {self.store.domain}: {exc}")
            return []

    # ── Page processing ───────────────────────────────────────────────────────

    async def _process_page(self, source_page: SourcePage, seen_ids: set[str]) -> None:
        """
        Fetch HTML from source_page, extract products, process each one.
        """
        print(f"🔥 Processing page: {source_page.url}")
        try:
            # Fetch raw HTML
            html_bytes = await self._fetch_page(source_page.url)
            page_hash = compute_hash(html_bytes)

            # Update source_page with fetch metadata
            await self._upsert_source_page(source_page, page_hash)

            # Store raw bytes in object storage
            storage_path = self.storage.build_path(
                store_domain=self.store.domain,
                source_type="html",
                filename=f"page_{hashlib.md5(source_page.url.encode()).hexdigest()}.html",
                date=self._now,
            )
            try:
                actual_path = await self.storage.write(storage_path, html_bytes)
                source_page.raw_storage_path = actual_path
                self.counters.pages_fetched += 1
            except Exception as exc:
                self.counters.warn(
                    f"Failed to write page to storage",
                    url=source_page.url,
                    detail=str(exc),
                )

            # Extract products using HtmlExtractor
            print(f"🔥 ABOUT TO CALL extract_products for {source_page.url}")
            log.info(f"Calling extract_products for {source_page.url}")
            extraction_results = await self.extractor.extract_products(
                html_bytes, source_page.url
            )
            print(f"🔥 extract_products returned {len(extraction_results)} results")
            log.info(f"extract_products returned {len(extraction_results)} results for {source_page.url}")

            for extraction_result in extraction_results:
                # Skip invalid extractions and very low confidence results
                if extraction_result.validation_status == "invalid":
                    log.warning(
                        f"Skipping invalid extraction from {source_page.url}: {extraction_result.errors}"
                    )
                    continue
                if extraction_result.payload.confidence < 0.1:
                    log.info(
                        f"Skipping low-confidence extraction from {source_page.url}: confidence={extraction_result.payload.confidence}"
                    )
                    continue

                # ── Coffee classification: reject non-coffee items ──────────────
                from app.services.shopify.coffee_classifier import is_coffee_product

                product_dict = {
                    "title": extraction_result.payload.coffee_name or "",
                    "product_type": "",
                    "tags": [],
                }
                is_coffee, reason = is_coffee_product(product_dict)
                if not is_coffee:
                    log.info(
                        f"Skipping non-coffee product '{extraction_result.payload.coffee_name}' from {source_page.url}: {reason}"
                    )
                    self.counters.warn(
                        f"Rejected non-coffee product: {reason}",
                        url=source_page.url,
                        detail=extraction_result.payload.coffee_name or "Unknown"
                    )
                    continue

                log.info(
                    f"Processing extraction: {extraction_result.payload.coffee_name} (confidence={extraction_result.payload.confidence:.2f})"
                )
                self.counters.records_seen += 1
                seller_product_id = self._derive_seller_product_id(
                    extraction_result.payload, source_page
                )
                if seller_product_id:
                    seen_ids.add(seller_product_id)

                try:
                    await self._process_product(
                        extraction_result.payload, source_page, seller_product_id
                    )
                except Exception as exc:
                    self.counters.error(
                        f"Failed processing product '{extraction_result.payload.coffee_name}'",
                        url=source_page.url,
                        detail=str(exc),
                    )

            await self.session.flush()

        except Exception as exc:
            self.counters.error(
                f"Page fetch/processing failed: {source_page.url}",
                url=source_page.url,
                detail=str(exc),
            )
            self.counters.pages_failed += 1

    async def _fetch_page(self, url: str, retries: int = 3) -> bytes:
        """
        Fetch HTML from URL with timeout, proper headers, and retry logic.

        Uses realistic browser headers to avoid bot blocking.
        Retries with exponential backoff on transient errors.

        Returns:
            Raw HTML bytes
        """
        import time

        # Headers that mimic a real browser request
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": url.rsplit('/', 1)[0] + "/",  # Add referer to appear more like real browser
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        last_error = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code} from {url}: {exc.reason}"
                # 429 (Too Many Requests), 503 (Service Unavailable), 403 (Forbidden), 401 (Unauthorized) - all can be transient
                if exc.code in (403, 401, 429, 503) and attempt < retries - 1:
                    wait_time = (2 ** attempt) + (attempt * 1)  # Increased backoff: 1s, 3s, 7s
                    log.warning(f"HTTP {exc.code} (likely bot detection), retrying in {wait_time}s: {url}")
                    time.sleep(wait_time)
                    continue
                # Other HTTP errors: retry once
                if attempt < retries - 1:
                    wait_time = 2
                    log.warning(f"HTTP error {exc.code}, retrying in {wait_time}s: {url}")
                    time.sleep(wait_time)
                    continue
                raise Exception(last_error) from exc
            except urllib.error.URLError as exc:
                last_error = f"URL error for {url}: {exc.reason}"
                if attempt < retries - 1:
                    log.warning(f"Connection error, retrying: {url}")
                    time.sleep(1)
                    continue
                raise Exception(last_error) from exc
            except Exception as exc:
                last_error = f"Failed to fetch {url}: {exc}"
                raise Exception(last_error) from exc

        raise Exception(f"Failed to fetch after {retries} attempts: {last_error}")

    async def _process_product(
        self,
        payload: ExtractionPayload,
        source_page: SourcePage,
        seller_product_id: str,
    ) -> None:
        """
        Upsert a single extracted product and all its price variants.

        Decision tree:
          - Product hash unchanged → update timestamps + price history only
          - Product hash changed   → update listing fields + variants + price history
          - New product            → insert listing + variants + price history
        """
        # Compute content hash from extraction
        content_hash = self._compute_hash(payload)

        log.debug(
            f"_process_product: {payload.coffee_name} | seller_id={seller_product_id} | hash={content_hash}"
        )

        # Look up existing listing by seller_product_id
        existing_listing = await self._find_listing(seller_product_id)
        if existing_listing:
            log.debug(f"  → Found existing listing")
        else:
            log.debug(f"  → New listing")

        if existing_listing is not None:
            if existing_listing.content_hash == content_hash:
                # ── Unchanged: update freshness and append prices only ────
                await self._touch_listing(existing_listing)
                await self._append_price_history_for_listing(
                    existing_listing, payload
                )
                self.counters.records_unchanged += 1
                log.info(f"  → Unchanged (touched)")
                return

            # ── Changed: update listing fields and variants ───────────────
            await self._update_listing(
                existing_listing, payload, source_page, content_hash
            )
            await self._upsert_variants(existing_listing, payload)
            await self._append_price_history_for_listing(existing_listing, payload)
            self.counters.records_updated += 1
            log.info(f"  → Updated")

        else:
            # ── New product: insert listing and variants ───────────────────
            listing = await self._insert_listing(
                payload, source_page, content_hash, seller_product_id
            )
            await self._upsert_variants(listing, payload)
            await self._append_price_history_for_listing(listing, payload)
            self.counters.records_created += 1
            log.info(f"  → Created new listing {listing.id}")

    # ── Listing operations ────────────────────────────────────────────────────

    async def _find_listing(self, seller_product_id: str) -> BeanListing | None:
        """Look up existing listing by seller_product_id."""
        stmt = select(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.seller_product_id == seller_product_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _insert_listing(
        self,
        payload: ExtractionPayload,
        source_page: SourcePage,
        content_hash: str,
        seller_product_id: str,
    ) -> BeanListing:
        """Insert a new product listing."""
        listing = BeanListing(
            store_id=self.store.id,
            source_page_id=source_page.id,
            seller_product_id=seller_product_id,
            content_hash=content_hash,
            listing_status=ListingStatus.active,
            active_flag=True,
            first_seen_at=self._now,
            last_seen_at=self._now,
            last_changed_at=self._now,
            raw_title=payload.raw_title or payload.coffee_name,
            raw_description=payload.raw_description,
            roast_label_raw=payload.roast_level,
            process_label_raw=payload.process,
            origin_label_raw=payload.origin_country,
            varietal_label_raw="|".join(payload.varietal) if payload.varietal else "",
        )
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def _update_listing(
        self,
        listing: BeanListing,
        payload: ExtractionPayload,
        source_page: SourcePage,
        content_hash: str,
    ) -> None:
        """Update an existing product listing."""
        listing.content_hash = content_hash
        listing.last_seen_at = self._now
        listing.last_changed_at = self._now
        listing.source_page_id = source_page.id
        listing.listing_status = ListingStatus.active
        listing.active_flag = True

        # Update raw label fields if extraction provided them
        if payload.raw_title:
            listing.raw_title = payload.raw_title
        if payload.raw_description:
            listing.raw_description = payload.raw_description
        if payload.roast_level:
            listing.roast_label_raw = payload.roast_level
        if payload.process:
            listing.process_label_raw = payload.process
        if payload.origin_country:
            listing.origin_label_raw = payload.origin_country
        if payload.varietal:
            listing.varietal_label_raw = "|".join(payload.varietal)

    async def _touch_listing(self, listing: BeanListing) -> None:
        """Update only last_seen_at for unchanged listings."""
        listing.last_seen_at = self._now

    # ── Variant upsert ────────────────────────────────────────────────────────

    async def _upsert_variants(
        self, listing: BeanListing, payload: ExtractionPayload
    ) -> None:
        """Upsert all price variants for a listing."""
        if not payload.price_variants:
            return

        for price_var in payload.price_variants:
            # Derive stable seller_variant_id from weight + grind
            seller_variant_id = f"{listing.seller_product_id}|{price_var.weight_g}|{price_var.grind_type}"

            # Look up existing variant
            existing_stmt = select(ListingVariant).where(
                ListingVariant.bean_listing_id == listing.id,
                ListingVariant.seller_variant_id == seller_variant_id,
            )
            existing = (await self.session.execute(existing_stmt)).scalar_one_or_none()

            # Parse grind type
            grind_type = self._parse_grind_type(price_var.grind_type)

            if existing is None:
                # New variant
                variant = ListingVariant(
                    bean_listing_id=listing.id,
                    seller_variant_id=seller_variant_id,
                    variant_title_raw=f"{price_var.weight_g}g / {price_var.grind_type}",
                    weight_g=price_var.weight_g,
                    grind_type=grind_type,
                    price_gbp=price_var.price_gbp,
                    price_per_100g_gbp=self._compute_price_per_100g(
                        price_var.price_gbp, price_var.weight_g
                    ),
                    currency_code=price_var.currency_code or "GBP",
                    availability_status=self._parse_availability(price_var.availability),
                    recorded_at=self._now,
                )
                self.session.add(variant)
            else:
                # Update existing
                existing.price_gbp = price_var.price_gbp
                existing.price_per_100g_gbp = self._compute_price_per_100g(
                    price_var.price_gbp, price_var.weight_g
                )
                existing.availability_status = self._parse_availability(
                    price_var.availability
                )
                existing.recorded_at = self._now
                # Update weight/grind if we now have better values
                if price_var.weight_g is not None:
                    existing.weight_g = price_var.weight_g
                if grind_type != GrindType.unknown:
                    existing.grind_type = grind_type

    # ── Price history ─────────────────────────────────────────────────────────

    async def _append_price_history_for_listing(
        self, listing: BeanListing, payload: ExtractionPayload
    ) -> None:
        """Append one PriceHistory row per variant on every run."""
        if not payload.price_variants:
            return

        # Fetch current persisted variants for this listing
        variant_stmt = select(ListingVariant).where(
            ListingVariant.bean_listing_id == listing.id
        )
        variants = (await self.session.execute(variant_stmt)).scalars().all()

        # Build lookup from seller_variant_id to price_variant
        price_var_lookup = {
            self._make_seller_variant_id(listing.seller_product_id, pv): pv
            for pv in payload.price_variants
        }

        for variant in variants:
            price_var = price_var_lookup.get(variant.seller_variant_id or "")
            if price_var is None:
                # Variant in DB but not in extraction — out of stock
                price = variant.price_gbp
                avail = AvailabilityStatus.out_of_stock
                price_per_100g = variant.price_per_100g_gbp
            else:
                price = price_var.price_gbp
                avail = self._parse_availability(price_var.availability)
                price_per_100g = self._compute_price_per_100g(
                    price_var.price_gbp, price_var.weight_g
                )

            history = PriceHistory(
                listing_variant_id=variant.id,
                price_gbp=price,
                price_per_100g_gbp=price_per_100g,
                availability_status=avail,
                recorded_at=self._now,
            )
            self.session.add(history)

    # ── Source page upsert ────────────────────────────────────────────────────

    async def _upsert_source_page(
        self, source_page: SourcePage, page_hash: str
    ) -> None:
        """Update source_page with fetch metadata."""
        changed = source_page.content_hash != page_hash
        source_page.last_fetched_at = self._now
        source_page.status_code = 200
        source_page.changed_flag = changed
        source_page.content_hash = page_hash

        await self.session.flush()

    # ── Deactivation ──────────────────────────────────────────────────────────

    async def _deactivate_missing(self, seen_seller_ids: set[str]) -> None:
        """Mark listings that weren't in the current discovery as inactive."""
        if not seen_seller_ids:
            return

        stmt = select(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.active_flag == True,  # noqa: E712
            BeanListing.seller_product_id.notin_(seen_seller_ids),
        )
        missing = (await self.session.execute(stmt)).scalars().all()

        for listing in missing:
            listing.active_flag = False
            listing.listing_status = ListingStatus.inactive
            self.counters.warn(
                f"Product deactivated (absent from feed): {listing.raw_title}",
                detail=f"seller_product_id={listing.seller_product_id}",
            )

    # ── Store update ──────────────────────────────────────────────────────────

    async def _update_store_crawl_time(self) -> None:
        """Update store's last_successful_crawl_at timestamp."""
        self.store.last_successful_crawl_at = self._now

    # ── Run lifecycle ─────────────────────────────────────────────────────────

    async def _open_run(self) -> IngestionRun:
        """Create and open a new IngestionRun record."""
        run = IngestionRun(
            run_type=RunType.incremental,
            store_id=self.store.id,
            started_at=self._now,
            status=RunStatus.running,
        )
        self.session.add(run)
        await self.session.commit()
        log.info("Opened ingestion run %s for %s", run.id, self.store.domain)
        return run

    async def _close_run(self, status: RunStatus) -> IngestionRun:
        """Close IngestionRun with final counters and status."""
        completed_at = datetime.now(timezone.utc)
        self._run.status = status
        self._run.completed_at = completed_at
        self._run.records_seen = self.counters.records_seen
        self._run.records_created = self.counters.records_created
        self._run.records_updated = self.counters.records_updated
        self._run.records_unchanged = self.counters.records_unchanged
        self._run.pages_fetched = self.counters.pages_fetched
        self._run.pages_failed = self.counters.pages_failed
        self._run.warnings = self.counters.warnings
        self._run.errors = self.counters.errors

        await self.session.commit()

        duration = (completed_at - self._now).total_seconds()
        log.info(
            "Ingestion run %s closed: status=%s seen=%d created=%d updated=%d "
            "unchanged=%d errors=%d duration=%.1fs",
            self._run.id,
            status.value,
            self.counters.records_seen,
            self.counters.records_created,
            self.counters.records_updated,
            self.counters.records_unchanged,
            len(self.counters.errors),
            duration,
        )
        return self._run

    # ── Helper methods ────────────────────────────────────────────────────────

    def _derive_seller_product_id(
        self, payload: ExtractionPayload, source_page: SourcePage
    ) -> str:
        """
        Create stable product ID from extraction and URL for idempotent matching.

        Strategy:
          1. Try URL path-based ID (last non-generic path segment)
          2. Fallback to query parameters (?product=, ?id=)
          3. Last resort: hash URL
        """
        url = payload.source_url or source_page.url

        # Try URL path-based ID
        path = urlparse(url).path
        slug = path.rstrip("/").split("/")[-1]
        if (
            slug
            and slug
            not in (
                "shop",
                "products",
                "product",
                "items",
                "item",
                "coffee",
                "coffees",
                "index.html",
                "",
            )
        ):
            return slug

        # Fallback to query params
        params = parse_qs(urlparse(url).query)
        if "product" in params:
            return f"product-{params['product'][0]}"
        if "id" in params:
            return f"id-{params['id'][0]}"

        # Last resort: hash URL
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _compute_hash(self, payload: ExtractionPayload) -> str:
        """Compute SHA-256 of immutable product data."""
        immutable_fields = [
            payload.coffee_name,
            payload.roaster_name,
            payload.raw_title,
            payload.raw_description,
            "|".join(payload.varietal),
            payload.process,
            payload.origin_country,
            str(payload.price_variants),
        ]
        combined = "|".join(str(f) for f in immutable_fields)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _compute_price_per_100g(
        self, price_gbp: float, weight_g: int | None
    ) -> float | None:
        """Compute normalized price per 100g."""
        if weight_g is None or weight_g <= 0 or price_gbp <= 0:
            return None
        return round((price_gbp / weight_g) * 100, 4)

    def _make_seller_variant_id(self, seller_product_id: str, price_var) -> str:
        """Reconstruct seller_variant_id from components."""
        return f"{seller_product_id}|{price_var.weight_g}|{price_var.grind_type}"

    def _parse_grind_type(self, raw_grind: str) -> GrindType:
        """Parse raw grind string to GrindType enum."""
        raw = raw_grind.lower().strip()

        if not raw or raw == "unknown":
            return GrindType.unknown
        if "whole" in raw or "bean" in raw:
            return GrindType.whole_bean
        if "espresso" in raw:
            return GrindType.espresso
        if "filter" in raw or "drip" in raw:
            return GrindType.filter
        if "french" in raw or "cafetiere" in raw or "press" in raw:
            return GrindType.french_press

        return GrindType.unknown

    def _parse_availability(self, raw_avail: str) -> AvailabilityStatus:
        """Parse raw availability string to AvailabilityStatus enum."""
        raw = raw_avail.lower().strip()

        if not raw or raw == "unknown":
            return AvailabilityStatus.unknown
        if "in stock" in raw or "available" in raw:
            return AvailabilityStatus.in_stock
        if "out of stock" in raw or "unavailable" in raw:
            return AvailabilityStatus.out_of_stock
        if "pre" in raw or "coming" in raw:
            return AvailabilityStatus.preorder

        return AvailabilityStatus.unknown


def _classify_pipeline_exception(exc: BaseException) -> str:
    """
    Map a top-level pipeline exception to a short, human-readable bucket label.
    """
    name = type(exc).__name__
    msg = str(exc).lower()

    # urllib-specific
    if "httperror" in name.lower():
        if "404" in msg:
            return "HTTP_404"
        if "403" in msg:
            return "HTTP_403"
        if "500" in msg or "502" in msg or "503" in msg:
            return "HTTP_5XX"
        return "HTTP_ERROR"

    if "urlerror" in name.lower():
        if "timeout" in msg:
            return "TIMEOUT"
        if "connection" in msg or "refused" in msg:
            return "CONNECTION_ERROR"
        return "URL_ERROR"

    # JSON / parse
    if "json" in name.lower() or "json" in msg and "decode" in msg:
        return "PARSE_ERROR"

    # DB — sqlalchemy/asyncpg
    if "sqlalchemy" in type(exc).__module__ or "asyncpg" in type(exc).__module__:
        return "DATABASE_ERROR"

    return f"UNHANDLED_{name}"
