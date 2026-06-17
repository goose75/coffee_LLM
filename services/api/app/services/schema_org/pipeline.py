"""
Schema.org Ingestion Pipeline.

Extracts products from storefronts using schema.org JSON-LD markup.
Follows ShopifyIngestionPipeline pattern exactly.

Pipeline steps per store:
  1. Open ingestion_run record (status=running)
  2. Fetch all source_pages for this store
  3. For each page: fetch HTML, extract products via SchemaOrgParser
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
import urllib.request
import urllib.error
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
from app.services.extraction.payload import ExtractionResult
from app.services.extraction.schema_org_parser import SchemaOrgParser
from app.services.storage.backend import StorageBackend, compute_hash, get_storage_backend

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
    pages_no_schema: int = 0
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


class SchemaOrgIngestionPipeline:
    """
    Ingests products from storefronts with schema.org JSON-LD markup.

    Uses SchemaOrgParser to extract product data from structured markup,
    then populates bean_listing and listing_variant tables.

    Usage:
        pipeline = SchemaOrgIngestionPipeline(session, store)
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
        self.parser = SchemaOrgParser()
        self.counters = IngestionCounters()
        self._run: IngestionRun | None = None
        self._now = datetime.now(timezone.utc)
        self._user_agent = (
            "CoffeePlatformBot/1.0 "
            "(+https://coffeeplatform.co.uk/bot; data@coffeeplatform.co.uk)"
        )

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(self) -> IngestionRun:
        """
        Execute the full schema.org ingestion pipeline for this store.
        Always returns an IngestionRun — never raises.
        """
        self._run = await self._open_run()

        try:
            # Fetch all source pages for this store
            source_pages = await self._fetch_source_pages()

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
                "Schema.org pipeline crashed for %s: %s",
                self.store.domain,
                exc,
                exc_info=True,
            )
            self.counters.error(
                f"Pipeline exception for {self.store.domain}",
                detail=str(exc),
            )
            return await self._close_run(RunStatus.failed)

    # ── Page processing ──────────────────────────────────────────────────────

    async def _process_page(
        self, source_page: SourcePage, seen_seller_ids: set[str]
    ) -> None:
        """
        Fetch HTML for a page, extract products via SchemaOrgParser,
        and upsert each product into the database.
        """
        try:
            # Fetch raw HTML
            html_bytes = await self._fetch_page(source_page.url)
            self.counters.pages_fetched += 1

            # Extract via schema.org parser
            extraction = self.parser.extract(html_bytes, source_page.url)

            # If no schema.org markup found, skip gracefully (not an error)
            if extraction.validation_status == "invalid":
                self.counters.pages_no_schema += 1
                log.debug(
                    f"No schema.org markup for {source_page.url}: {extraction.validation_errors}"
                )
                return

            # Process the extracted product
            await self._process_product(extraction, source_page, seen_seller_ids)

        except Exception as exc:
            self.counters.error(
                f"Page failed: {source_page.url}",
                url=source_page.url,
                detail=str(exc),
            )
            self.counters.pages_failed += 1

    async def _process_product(
        self,
        extraction: ExtractionResult,
        source_page: SourcePage,
        seen_seller_ids: set[str],
    ) -> None:
        """
        Decision tree for product: insert new → update changed → touch unchanged.
        Mirrors ShopifyIngestionPipeline logic exactly.
        """
        if not extraction.payload:
            return

        # ── Coffee classification: reject non-coffee items ──────────────────────
        from app.services.shopify.coffee_classifier import is_coffee_product

        product_dict = {
            "title": extraction.payload.coffee_name or "",
            "product_type": "",
            "tags": [],
        }
        is_coffee, reason = is_coffee_product(product_dict)
        if not is_coffee:
            log.info(
                f"Skipping non-coffee product '{extraction.payload.coffee_name}' from {source_page.url}: {reason}"
            )
            self.counters.warn(
                f"Rejected non-coffee product: {reason}",
                url=source_page.url,
                detail=extraction.payload.coffee_name or "Unknown"
            )
            return

        self.counters.records_seen += 1

        # Compute content hash from immutable fields
        content_hash = self._compute_hash(extraction.payload)

        # Derive seller_product_id from URL or name
        seller_product_id = self._derive_seller_product_id(
            extraction.payload, source_page
        )

        # Avoid processing the same product twice in one run
        if seller_product_id in seen_seller_ids:
            log.debug(f"Duplicate product in run: {seller_product_id}")
            return
        seen_seller_ids.add(seller_product_id)

        # Lookup existing listing
        existing_listing = await self._find_listing(seller_product_id)

        if existing_listing is None:
            # NEW: Insert fresh product
            listing = await self._insert_listing(
                extraction, source_page, content_hash, seller_product_id
            )
            await self._upsert_variants(listing, extraction)
            await self._append_price_history_for_listing(listing, extraction)
            self.counters.records_created += 1
            log.info(f"Created listing: {seller_product_id} ({extraction.payload.coffee_name})")

        elif existing_listing.content_hash == content_hash:
            # UNCHANGED: Touch freshness only
            await self._touch_listing(existing_listing)
            await self._append_price_history_for_listing(existing_listing, extraction)
            self.counters.records_unchanged += 1

        else:
            # CHANGED: Update all fields
            await self._update_listing(
                existing_listing, extraction, source_page, content_hash
            )
            await self._upsert_variants(existing_listing, extraction)
            await self._append_price_history_for_listing(existing_listing, extraction)
            self.counters.records_updated += 1
            log.info(f"Updated listing: {seller_product_id}")

    # ── Database operations ──────────────────────────────────────────────────

    async def _find_listing(self, seller_product_id: str) -> BeanListing | None:
        """Find existing listing by seller_product_id."""
        stmt = select(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.seller_product_id == seller_product_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _insert_listing(
        self,
        extraction: ExtractionResult,
        source_page: SourcePage,
        content_hash: str,
        seller_product_id: str,
    ) -> BeanListing:
        """Insert a new BeanListing."""
        payload = extraction.payload

        listing = BeanListing(
            store_id=self.store.id,
            source_page_id=source_page.id,
            seller_product_id=seller_product_id,
            raw_title=payload.raw_title or payload.coffee_name or "Unknown",
            raw_description=payload.raw_description,
            product_url=payload.source_url or source_page.url,
            listing_status=ListingStatus.active.value,
            content_hash=content_hash,
            extraction_method=extraction.extraction_method,
            extraction_confidence=payload.confidence,
            created_at=self._now,
            updated_at=self._now,
            last_seen_at=self._now,
        )
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def _update_listing(
        self,
        listing: BeanListing,
        extraction: ExtractionResult,
        source_page: SourcePage,
        new_content_hash: str,
    ) -> None:
        """Update an existing BeanListing."""
        payload = extraction.payload

        listing.source_page_id = source_page.id
        listing.raw_title = payload.raw_title or payload.coffee_name or "Unknown"
        listing.raw_description = payload.raw_description
        listing.product_url = payload.source_url or source_page.url
        listing.content_hash = new_content_hash
        listing.extraction_method = extraction.extraction_method
        listing.extraction_confidence = payload.confidence
        listing.updated_at = self._now
        listing.last_seen_at = self._now

    async def _touch_listing(self, listing: BeanListing) -> None:
        """Update last_seen_at timestamp only."""
        listing.last_seen_at = self._now

    async def _upsert_variants(
        self, listing: BeanListing, extraction: ExtractionResult
    ) -> None:
        """Upsert price variants for a listing."""
        payload = extraction.payload

        if not payload.price_variants:
            return

        # Fetch all existing variants for this listing
        stmt = select(ListingVariant).where(
            ListingVariant.bean_listing_id == listing.id
        )
        existing_variants = {
            v.seller_variant_id: v for v in (await self.session.execute(stmt)).scalars()
        }

        # Track which variants we process in this run
        seen_variant_ids: set[str] = set()

        for price_var in payload.price_variants:
            # Derive stable seller_variant_id
            seller_variant_id = self._derive_seller_variant_id(
                listing.seller_product_id, price_var
            )
            seen_variant_ids.add(seller_variant_id)

            if seller_variant_id in existing_variants:
                # Update existing variant
                variant = existing_variants[seller_variant_id]
                variant.price_gbp = price_var.price_gbp
                variant.price_per_100g_gbp = self._compute_price_per_100g(
                    price_var.price_gbp, price_var.weight_g
                )
                variant.availability_status = price_var.availability_status
                variant.recorded_at = self._now
            else:
                # Insert new variant
                variant = ListingVariant(
                    bean_listing_id=listing.id,
                    seller_variant_id=seller_variant_id,
                    variant_title_raw=price_var.title or (
                        f"{price_var.weight_g}g / {price_var.grind_type}"
                        if price_var.weight_g
                        else f"{price_var.grind_type}"
                    ),
                    weight_g=price_var.weight_g,
                    grind_type=price_var.grind_type,
                    price_gbp=price_var.price_gbp,
                    price_per_100g_gbp=self._compute_price_per_100g(
                        price_var.price_gbp, price_var.weight_g
                    ),
                    availability_status=price_var.availability_status,
                    recorded_at=self._now,
                )
                self.session.add(variant)

        # Mark unseen variants as inactive
        for variant_id, variant in existing_variants.items():
            if variant_id not in seen_variant_ids:
                variant.availability_status = AvailabilityStatus.unavailable.value

        await self.session.flush()

    async def _append_price_history_for_listing(
        self, listing: BeanListing, extraction: ExtractionResult
    ) -> None:
        """Append price history for each variant."""
        payload = extraction.payload

        if not payload.price_variants:
            return

        for price_var in payload.price_variants:
            seller_variant_id = self._derive_seller_variant_id(
                listing.seller_product_id, price_var
            )

            # Find the variant
            stmt = select(ListingVariant).where(
                ListingVariant.bean_listing_id == listing.id,
                ListingVariant.seller_variant_id == seller_variant_id,
            )
            variant = (await self.session.execute(stmt)).scalar_one_or_none()

            if variant and price_var.price_gbp and price_var.price_gbp > 0:
                history = PriceHistory(
                    listing_variant_id=variant.id,
                    price_gbp=price_var.price_gbp,
                    price_per_100g_gbp=self._compute_price_per_100g(
                        price_var.price_gbp, price_var.weight_g
                    ),
                    availability_status=price_var.availability_status,
                    recorded_at=self._now,
                )
                self.session.add(history)

        await self.session.flush()

    async def _deactivate_missing(self, seen_seller_ids: set[str]) -> None:
        """Mark products not seen in this run as inactive."""
        stmt = update(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.seller_product_id.notin_(seen_seller_ids),
            BeanListing.listing_status != ListingStatus.inactive.value,
        )
        result = await self.session.execute(stmt)
        log.info(f"Deactivated {result.rowcount} missing products")

    # ── Ingestion run lifecycle ──────────────────────────────────────────────

    async def _open_run(self) -> IngestionRun:
        """Create and open a new IngestionRun record."""
        run = IngestionRun(
            store_id=self.store.id,
            run_type=RunType.schema_org.value,
            status=RunStatus.running.value,
            started_at=self._now,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def _close_run(self, status: RunStatus) -> IngestionRun:
        """Close the ingestion run, commit all changes."""
        if self._run is None:
            raise RuntimeError("No run in progress")

        self._run.status = status.value
        self._run.completed_at = self._now
        self._run.records_seen = self.counters.records_seen
        self._run.records_created = self.counters.records_created
        self._run.records_updated = self.counters.records_updated
        self._run.error_count = len(self.counters.errors)
        self._run.warning_count = len(self.counters.warnings)
        self._run.errors = self.counters.errors
        self._run.warnings = self.counters.warnings

        await self.session.commit()
        return self._run

    async def _update_store_crawl_time(self) -> None:
        """Stamp successful crawl time on the store."""
        self.store.last_successful_crawl_at = self._now
        await self.session.flush()

    # ── Page discovery & fetching ────────────────────────────────────────────

    async def _fetch_source_pages(self) -> list[SourcePage]:
        """
        Get all known source_pages for this store.
        If none exist, attempt to discover from homepage.
        """
        stmt = (
            select(SourcePage)
            .where(SourcePage.store_id == self.store.id)
            .order_by(SourcePage.discovered_at)
        )
        pages = (await self.session.execute(stmt)).scalars().all()

        if not pages:
            # Fallback: discover from homepage
            log.info(
                f"No source pages found for {self.store.domain}, attempting homepage discovery"
            )
            homepage = SourcePage(
                store_id=self.store.id,
                url=self.store.homepage_url,
                page_type=PageType.homepage.value,
                parser_strategy=ParserStrategy.schema_org.value,
                discovered_at=self._now,
            )
            self.session.add(homepage)
            await self.session.flush()
            pages = [homepage]

        return pages

    async def _fetch_page(self, url: str) -> bytes:
        """Fetch HTML from a URL with timeout and error handling."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self._user_agent},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {url}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection failed: {url}") from e
        except Exception as e:
            raise RuntimeError(f"Fetch failed: {url}") from e

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _derive_seller_product_id(
        self, payload, source_page: SourcePage
    ) -> str:
        """
        Create stable product ID from URL for idempotent matching.
        Examples:
          /products/ethiopian-yirgacheffe → "ethiopian-yirgacheffe"
          /shop/item/123 → "item-123"
          ?product=456 → "product-456"
        """
        url = payload.source_url or source_page.url

        # Try URL path-based ID
        path = urlparse(url).path
        slug = path.rstrip("/").split("/")[-1]
        if slug and slug not in ("shop", "products", "items", "coffee", ""):
            return slug

        # Try query params
        params = parse_qs(urlparse(url).query)
        if "product" in params:
            return f"product-{params['product'][0]}"
        if "id" in params:
            return f"id-{params['id'][0]}"
        if "p" in params:
            return f"p-{params['p'][0]}"

        # Last resort: hash URL + name for uniqueness
        combined = f"{url}|{payload.coffee_name or 'unknown'}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _derive_seller_variant_id(self, product_id: str, price_var) -> str:
        """Create stable variant ID from weight and grind."""
        weight_part = f"w{price_var.weight_g}" if price_var.weight_g else "wunk"
        grind_part = f"g{price_var.grind_type}" if price_var.grind_type else "gunk"
        return f"{product_id}|{weight_part}|{grind_part}"

    def _compute_hash(self, payload) -> str:
        """Compute SHA-256 of immutable product data."""
        immutable_fields = [
            payload.coffee_name,
            payload.roaster_name,
            payload.raw_title,
            payload.raw_description,
            payload.varietal,
            payload.process,
            payload.origin_country,
            str(payload.price_variants),  # Serialize variants
        ]
        combined = "|".join(str(f) for f in immutable_fields if f)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _compute_price_per_100g(
        self, price_gbp: float | None, weight_g: float | None
    ) -> float | None:
        """Compute price per 100g if both price and weight are available."""
        if price_gbp and weight_g and weight_g > 0:
            return round((price_gbp / weight_g) * 100, 2)
        return None
