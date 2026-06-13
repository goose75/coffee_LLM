"""
BrowserExtractor — Playwright-based extraction for JavaScript-heavy sites.

Phase B Week 2 Track 1: Browser Automation for high-value stores.

Solves the problem identified in Week 1 Day 4: 50% of extraction failures
are due to products being loaded via JavaScript (SPA/template rendering).

Architecture:
  1. Render page with Playwright (Chromium) to fully load JavaScript
  2. Extract products from rendered DOM
  3. Fall back to static HTML extraction if rendering fails or times out
  4. Never raises; returns ExtractionResult with validation_status

Performance targets:
  - Page render timeout: 10 seconds (configurable)
  - Memory per instance: <100MB
  - Timeout frequency target: <10%
  - Fallback trigger rate: < 5%
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from app.services.extraction.base import BaseParser
from app.services.extraction.payload import ExtractionPayload, ExtractionResult
from app.services.extraction.html_parser import HtmlRulesParser
from app.services.extraction.text_utils import (
    extract_weight_g,
    extract_price_gbp,
    extract_roast_level,
)

log = logging.getLogger(__name__)


class BrowserExtractor(BaseParser):
    """
    Renders JavaScript-heavy pages and extracts coffee products from the DOM.

    Fallback chain:
      1. Render page with Playwright
      2. Extract from rendered HTML (using HtmlRulesParser)
      3. If confidence too low, fall back to static extraction
      4. If all fails, return invalid result

    Browser instance pooling is handled by a singleton BrowserPool (see below).
    """

    extraction_method = "browser_automation"

    # Render timeout in seconds
    RENDER_TIMEOUT = 10.0

    # Network timeout for page.goto() in seconds
    NETWORK_TIMEOUT = 8.0

    # Wait for selector timeout
    WAIT_TIMEOUT = 5.0

    # Confidence threshold to trigger fallback
    FALLBACK_THRESHOLD = 0.4

    def __init__(self, pool: Optional[BrowserPool] = None):
        """
        Initialize extractor. If no pool provided, uses the global singleton.

        Args:
            pool: Optional BrowserPool for testing. Uses global pool if None.
        """
        self.pool = pool or get_browser_pool()
        self.html_parser = HtmlRulesParser()

    def extract(self, html: bytes, url: str) -> ExtractionResult:
        """
        Synchronous extract() wrapper for BaseParser interface.

        Runs async rendering in an event loop.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self._extract_async(html, url))
        except Exception as exc:
            log.error(
                "BrowserExtractor.extract() failed for %s: %s",
                url, exc, exc_info=True
            )
            return ExtractionResult.invalid(
                method=self.extraction_method,
                errors=[f"Browser extraction failed: {exc}"],
            )

    async def _extract_async(self, html: bytes, url: str) -> ExtractionResult:
        """
        Main async extraction method.

        Flow:
          1. Render page with Playwright
          2. Extract products from rendered DOM
          3. If confidence too low, fall back to static HTML extraction
          4. Return result (never raises)
        """

        # Step 1: Try to render the page with Playwright
        rendered_html = await self._render_page_with_playwright(url, html)

        if rendered_html is None:
            # Rendering failed or timed out — fall back to static extraction
            log.warning(
                "Playwright rendering failed for %s, falling back to static extraction",
                url
            )
            result = self.html_parser._safe_extract(html, url)
            if result.payload:
                result.payload.reasoning_summary = "Browser rendering failed; used static extraction"
            return result

        # Step 2: Extract from rendered HTML
        result = self.html_parser._safe_extract(rendered_html.encode('utf-8'), url)

        # Step 3: If confidence too low, try static extraction as alternative
        if result.payload and result.payload.confidence < self.FALLBACK_THRESHOLD:
            log.debug(
                "Rendered extraction confidence %.2f < threshold %.2f for %s, trying static",
                result.payload.confidence, self.FALLBACK_THRESHOLD, url
            )
            static_result = self.html_parser._safe_extract(html, url)
            if static_result.payload and static_result.payload.confidence > result.payload.confidence:
                result = static_result
                result.payload.reasoning_summary = "Static extraction outperformed rendered extraction"

        # Mark as browser-extracted in reasoning
        if result.payload and not result.payload.reasoning_summary:
            result.payload.reasoning_summary = "Extracted from rendered page (JavaScript executed)"

        return result

    async def _render_page_with_playwright(self, url: str, fallback_html: bytes) -> Optional[str]:
        """
        Render a page with Playwright and return the rendered HTML.

        Handles:
          - Page timeouts (returns None)
          - Network errors (returns fallback_html)
          - JavaScript errors (logs but continues)
          - Memory issues (returns None)

        Returns:
            Rendered HTML as string, or None if rendering failed
        """

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            # Acquire browser context from pool
            context = await self.pool.acquire_context()

            # Create new page
            page = await context.new_page()

            # Set timeout for all operations
            page.set_default_timeout(int(self.RENDER_TIMEOUT * 1000))

            # Navigate to URL with timeout
            try:
                await asyncio.wait_for(
                    page.goto(url, wait_until="networkidle"),
                    timeout=self.NETWORK_TIMEOUT
                )
            except (PlaywrightTimeoutError, asyncio.TimeoutError):
                log.warning(
                    "Network timeout loading %s (timeout=%.1fs), using partial render",
                    url, self.NETWORK_TIMEOUT
                )
                # Even if page.goto times out, page may have partial content
                # Continue to extract from what we have

            # Wait for common product selectors to appear
            # This handles JavaScript that populates product lists
            selectors_to_wait = [
                ".product",
                ".coffee",
                "[data-product-id]",
                ".item",
                ".shop-item",
            ]

            for selector in selectors_to_wait:
                try:
                    await asyncio.wait_for(
                        page.wait_for_selector(selector),
                        timeout=self.WAIT_TIMEOUT
                    )
                    log.debug("Found selector %s on %s", selector, url)
                    break
                except (PlaywrightTimeoutError, asyncio.TimeoutError):
                    # This selector doesn't exist on this page, try next
                    continue
                except Exception as e:
                    log.debug("Error waiting for selector %s: %s", selector, e)
                    continue

            # Get the rendered HTML
            rendered_html = await page.content()

            log.info(
                "Successfully rendered page for %s (%.1f KB)",
                url, len(rendered_html) / 1024
            )

            return rendered_html

        except PlaywrightTimeoutError as exc:
            log.warning("Playwright timeout for %s: %s", url, exc)
            return None

        except asyncio.TimeoutError as exc:
            log.warning("Asyncio timeout for %s: %s", url, exc)
            return None

        except Exception as exc:
            log.error(
                "Unexpected error rendering %s: %s",
                url, exc, exc_info=True
            )
            return None

        finally:
            # Always clean up page and context
            if page is not None:
                try:
                    await page.close()
                except Exception as e:
                    log.warning("Error closing page: %s", e)

            if context is not None:
                try:
                    await self.pool.release_context(context)
                except Exception as e:
                    log.warning("Error releasing context: %s", e)


class BrowserPool:
    """
    Manages a pool of Playwright browser contexts for concurrent extraction.

    Pooling strategy:
      - Single browser instance (shared across all contexts)
      - Multiple isolated contexts (one per extraction)
      - Context reuse for memory efficiency
      - Configurable max concurrent contexts

    Benefits:
      - Efficient memory usage (browser instance is expensive)
      - Isolated contexts prevent cookie/session cross-contamination
      - Supports concurrent extractions
      - Graceful fallback if pool is exhausted
    """

    def __init__(self, max_contexts: int = 5, headless: bool = True):
        """
        Initialize browser pool.

        Args:
            max_contexts: Max number of concurrent contexts
            headless: Run browser in headless mode (no UI)
        """
        self.max_contexts = max_contexts
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.contexts: list[BrowserContext] = []
        self.available: asyncio.Queue = asyncio.Queue(maxsize=max_contexts)
        self._initialized = False

    async def initialize(self) -> None:
        """Start the browser and create initial context pool."""
        if self._initialized:
            return

        log.info("Initializing BrowserPool with max_contexts=%d", self.max_contexts)

        # Keep Playwright instance alive (don't use context manager)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

        # Pre-create context pool
        for i in range(self.max_contexts):
            try:
                context = await self.browser.new_context()
                self.contexts.append(context)
                await self.available.put(context)
                log.debug("Created browser context %d/%d", i + 1, self.max_contexts)
            except Exception as e:
                log.error("Failed to create context %d: %s", i, e)

        self._initialized = True
        log.info("BrowserPool initialized with %d contexts", len(self.contexts))

    async def acquire_context(self) -> BrowserContext:
        """
        Acquire a browser context from the pool.

        Blocks if no contexts available (queues the request).
        """
        if not self._initialized:
            await self.initialize()

        try:
            context = await asyncio.wait_for(
                self.available.get(),
                timeout=5.0
            )
            log.debug("Acquired context from pool (queue size: %d)", self.available.qsize())
            return context
        except asyncio.TimeoutError:
            log.error("Timeout acquiring context from pool (all %d contexts busy)", self.max_contexts)
            # Return a new temporary context as fallback
            if self.browser:
                return await self.browser.new_context()
            raise RuntimeError("Browser not initialized and cannot create new context")

    async def release_context(self, context: BrowserContext) -> None:
        """Release a context back to the pool."""
        try:
            await context.clear_cookies()  # Clear session data
            await self.available.put(context)
            log.debug("Released context back to pool (queue size: %d)", self.available.qsize())
        except Exception as e:
            log.warning("Error releasing context: %s", e)
            await context.close()

    async def shutdown(self) -> None:
        """Shut down the browser and clean up all contexts."""
        log.info("Shutting down BrowserPool")

        for context in self.contexts:
            try:
                await context.close()
            except Exception as e:
                log.warning("Error closing context during shutdown: %s", e)

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                log.warning("Error closing browser during shutdown: %s", e)

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                log.warning("Error stopping playwright during shutdown: %s", e)

        self._initialized = False
        log.info("BrowserPool shutdown complete")


# Global singleton browser pool
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool(max_contexts: int = 5) -> BrowserPool:
    """Get or create the global browser pool singleton."""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(max_contexts=max_contexts)
    return _browser_pool


async def shutdown_browser_pool() -> None:
    """Shut down the global browser pool (call at application shutdown)."""
    global _browser_pool
    if _browser_pool is not None:
        await _browser_pool.shutdown()
        _browser_pool = None
