"""WooCommerce REST API parser for sites using Elementor or complex layouts."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from app.services.extraction.payload import ExtractionPayload, ExtractionResult


class WooCommerceAPIParser:
    """
    Extracts coffee products from WooCommerce sites using REST API.
    Works for sites using Elementor or other complex page builders.
    """

    async def extract_category(
        self, store_domain: str, category_id: int | str
    ) -> list[ExtractionResult]:
        """
        Extract products from a WooCommerce category via REST API.
        Returns list of ExtractionResult objects (one per product).
        """
        results = []

        try:
            # Construct API URL
            api_url = f"https://{store_domain}/wp-json/wc/v3/products?category={category_id}&per_page=100"

            # Fetch from API
            req = urllib.request.Request(
                api_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Handle both list and dict responses
            if isinstance(data, dict) and "message" in data:
                # Error response
                return results

            products = data if isinstance(data, list) else []

            # Process each product
            for product in products:
                result = self._parse_product(product, store_domain)
                if result:
                    results.append(result)

        except urllib.error.URLError:
            pass
        except json.JSONDecodeError:
            pass
        except Exception:
            pass

        return results

    def _parse_product(
        self, product: dict, store_domain: str
    ) -> ExtractionResult | None:
        """Extract fields from a WooCommerce product."""

        # Basic required fields
        name = product.get("name", "").strip()
        if not name:
            return None

        # Description contains origin, producer, flavor notes
        description = product.get("description", "").strip()
        short_description = product.get("short_description", "").strip()

        # Extract price
        price_str = product.get("price", "")

        payload = ExtractionPayload(
            coffee_name=name,
            source_url=product.get("permalink", f"https://{store_domain}"),
            confidence=0.65,  # Medium confidence for API-sourced data
            price_variants=[],  # Pricing data could be extracted from product details
        )

        result = ExtractionResult(
            payload=payload, validation_status="valid"
        )
        return result
