"""Custom HTML parser for sites with product details blocks (Monmouth, similar designs)."""
from __future__ import annotations

import re
from app.services.extraction.payload import ExtractionPayload, ExtractionResult, PriceVariantPayload


class CustomStyleParser:
    """
    Extracts coffee products from sites with custom HTML product details blocks.
    Generic parser for sites like Monmouth Coffee that use similar class-based structures.
    """

    async def extract_all(self, html_bytes: bytes, url: str) -> list[ExtractionResult]:
        """
        Parse product structure and return all products found.
        Handles custom blocks, WooCommerce listings, Wix galleries, and WooCommerce REST API.
        Returns list of ExtractionResult objects (one per product).
        """
        html = html_bytes.decode('utf-8', errors='ignore')
        results = []

        # Try WooCommerce REST API first (JSON endpoint)
        if '/wp-json/wc/v3/products' in url:
            results.extend(await self._extract_woocommerce_api_products(html, url))
            if results:
                return results

        # Try custom product-details pattern (featured products slider)
        product_pattern = r'<div class="product-details__details">(.*?)</div>\s*</div>'
        for match in re.finditer(product_pattern, html, re.DOTALL):
            block = match.group(1)
            product = self._parse_product_block(block, url)
            if product and product.coffee_name:
                result = ExtractionResult(
                    payload=product,
                    validation_status="valid",
                )
                results.append(result)

        # If no results, try WooCommerce product listing
        if not results:
            results.extend(await self._extract_woocommerce_products(html, url))

        # If still no results, try Wix product gallery
        if not results:
            results.extend(await self._extract_wix_products(html, url))

        return results

    async def extract(self, html_bytes: bytes, url: str) -> ExtractionResult:
        """
        Fallback single-product extract method for compatibility.
        Returns the first product found.
        """
        results = await self.extract_all(html_bytes, url)
        if results:
            return results[0]
        return ExtractionResult(payload=ExtractionPayload(), validation_status="invalid")


    def _parse_product_block(self, block: str, url: str) -> ExtractionPayload | None:
        """Extract fields from a single product block."""
        
        # Coffee name (h2)
        name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', block)
        coffee_name = name_match.group(1).strip() if name_match else None
        
        if not coffee_name:
            return None
        
        # Origin country
        country_match = re.search(r'class="product-details__country">([^<]+)</span>', block)
        origin_country = country_match.group(1).strip() if country_match else None
        
        # Producer/farm
        producer_match = re.search(r'__country">\s*</span>\s*<span>([^<]+)</span>', block)
        producer = producer_match.group(1).strip() if producer_match else None
        
        # Tasting notes
        tasting_match = re.search(r'class="product-details__tasting-notes"[^>]*><i>([^<]+)</i>', block)
        raw_notes = tasting_match.group(1).strip() if tasting_match else None
        
        # Parse tasting notes into individual flavours
        flavour_notes = []
        if raw_notes:
            # Split by comma and clean up
            notes = [n.strip() for n in raw_notes.split(',')]
            flavour_notes = [n for n in notes if n]
        
        # Try to extract roast level from notes
        roast_level = self._extract_roast_level(raw_notes or "")
        
        # Process is typically washed for specialty coffee
        process = "washed"

        # Monmouth doesn't show pricing on homepage, so return without variants
        return ExtractionPayload(
            coffee_name=coffee_name,
            origin_country=origin_country or "",
            producer=producer or "",
            process=process,
            roast_level=roast_level or "medium",
            flavour_notes=flavour_notes,
            confidence=0.8,  # High confidence for custom parser
            source_url=url,
            price_variants=[],  # Pricing not available on homepage
        )
    
    async def _extract_woocommerce_products(self, html: str, url: str) -> list[ExtractionResult]:
        """Extract products from WooCommerce product listing pages."""
        results = []

        # WooCommerce product pattern - li.product elements
        product_pattern = r'<li[^>]*class="[^"]*product[^"]*"[^>]*>(.*?)</li>'

        for match in re.finditer(product_pattern, html, re.DOTALL):
            block = match.group(1)

            # Extract product URL from the woocommerce-LoopProduct-link
            product_url_match = re.search(r'href="([^"]*)"[^>]*class="woocommerce-LoopProduct-link', block)
            product_url = product_url_match.group(1) if product_url_match else url

            # Extract the details div which has the same structure as product-details
            details_match = re.search(r'<div[^>]*class="[^"]*details[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            if not details_match:
                continue

            details_block = details_match.group(1)

            # Extract product name
            name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', details_block)
            coffee_name = name_match.group(1).strip() if name_match else None

            if not coffee_name:
                continue

            # Origin country
            country_match = re.search(r'class="product__country">([^<]+)</span>', details_block)
            origin_country = country_match.group(1).strip() if country_match else None

            # Producer - second span after country
            spans = re.findall(r'class="product__country">\s*</span>\s*<span>([^<]+)</span>', details_block)
            producer = spans[0] if spans else None

            # Flavor notes - in italic tags
            tasting_match = re.search(r'<span><i>([^<]+)</i></span>', details_block)
            raw_notes = tasting_match.group(1).strip() if tasting_match else None

            # Parse tasting notes into individual flavors
            flavour_notes = []
            if raw_notes:
                notes = [n.strip() for n in raw_notes.split(',')]
                flavour_notes = [n for n in notes if n]

            # Extract roast level from notes
            roast_level = self._extract_roast_level(raw_notes or "")

            product = ExtractionPayload(
                coffee_name=coffee_name,
                origin_country=origin_country or "",
                producer=producer or "",
                process="washed",  # Default process
                roast_level=roast_level or "medium",
                flavour_notes=flavour_notes,
                confidence=0.8,  # High confidence for WooCommerce parsing
                source_url=product_url,
                price_variants=[],
            )

            result = ExtractionResult(
                payload=product,
                validation_status="valid",
            )
            results.append(result)

        return results

    async def _extract_woocommerce_api_products(self, html: str, url: str) -> list[ExtractionResult]:
        """Extract products from WooCommerce REST API JSON response."""
        import json
        results = []

        try:
            data = json.loads(html)
            if not isinstance(data, list):
                return results

            for product in data:
                name = product.get('name', '').strip()
                if not name:
                    continue

                product_url = product.get('permalink', url)

                payload = ExtractionPayload(
                    coffee_name=name,
                    source_url=product_url,
                    confidence=0.65,  # Medium confidence for API data
                )

                result = ExtractionResult(
                    payload=payload,
                    validation_status="valid",
                )
                results.append(result)

        except (json.JSONDecodeError, TypeError):
            pass

        return results

    async def _extract_wix_products(self, html: str, url: str) -> list[ExtractionResult]:
        """Extract products from Wix product gallery pages."""
        results = []

        # Wix product pattern - li with data-hook="product-list-grid-item"
        product_pattern = r'<li[^>]*data-hook="product-list-grid-item"[^>]*>(.*?)</li>'

        for match in re.finditer(product_pattern, html, re.DOTALL):
            block = match.group(1)

            # Extract product slug and URL
            slug_match = re.search(r'data-slug="([^"]+)"', block)
            if not slug_match:
                continue

            slug = slug_match.group(1)

            # Extract product URL
            url_match = re.search(r'href="([^"]*product-page/[^"]*)"', block)
            product_url = url_match.group(1) if url_match else f"{url.rstrip('/')}/product-page/{slug}"

            # Extract product name from h3 with data-hook="product-item-name"
            name_match = re.search(r'data-hook="product-item-name"[^>]*>([^<]+)</h3>', block)
            coffee_name = name_match.group(1).strip() if name_match else None

            # Use slug as fallback name if h3 is empty
            if not coffee_name or coffee_name.startswith('<'):
                coffee_name = slug.replace('-', ' ').title()

            # Filter out non-coffee products (boxes, subscriptions)
            if any(skip in coffee_name.lower() for skip in ['box', 'subscription', 'set']):
                continue

            product = ExtractionPayload(
                coffee_name=coffee_name,
                confidence=0.6,  # Lower confidence for Wix (less structured data)
                source_url=product_url,
            )

            result = ExtractionResult(
                payload=product,
                validation_status="valid",
            )
            results.append(result)

        return results

    def _extract_roast_level(self, text: str) -> str | None:
        """Extract roast level from description text."""
        roast_keywords = {
            'light': ['light', 'cinnamon', 'city', 'filter'],
            'medium': ['medium', 'city+', 'american'],
            'medium_dark': ['full city', 'dark city'],
            'dark': ['dark', 'french', 'italian', 'espresso'],
        }
        
        text_lower = text.lower()
        for roast, keywords in roast_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return roast
        
        return None
