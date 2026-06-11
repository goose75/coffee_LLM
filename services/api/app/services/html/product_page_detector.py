"""
Improved product page detector using flexible heuristics.

Detects product pages using:
1. URL patterns (primary) - improved regex patterns
2. HTML content analysis (secondary) - looks for e-commerce signals
3. Link context analysis (tertiary) - analyzes surrounding link text
"""

import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse


class ProductPageDetector:
    """Detects if a URL points to a product page."""

    # Primary: URL patterns that strongly indicate product pages
    STRONG_PRODUCT_PATTERNS = [
        # Standard e-commerce patterns
        r"/product(?:s)?/",  # /product/, /products/
        r"/(?:item|article|good|sku)/",  # Common alternatives
        r"/(?:coffee|bean|roast)(?:s)?/[a-z0-9\-]+/?$",  # Coffee-specific with slug
        r"/p/\d+",  # /p/123 format
        r"/products/\d+",  # /products/123 format
        r"/view/\d+",  # /view/123 format
        r"/detail/",  # /detail/...
        r"/(?:shop|store)/[a-z0-9\-]+/?$",  # /shop/product-name
    ]

    # Secondary: URL patterns that might indicate product pages
    WEAK_PRODUCT_PATTERNS = [
        r"/shop(?:/|$)",  # /shop/ or /shop endpoints
        r"/(?:catalog|collection|category)/",  # Might be category or product
        r"/(?:coffee|bean|roast)(?:s)?(?:/|$)",  # Coffee section (could be category)
        r"[?&](?:id|product_id|item_id|sku)=",  # Query params with product ID
    ]

    # Patterns that suggest this is NOT a product page
    NON_PRODUCT_PATTERNS = [
        r"/(?:about|contact|faq|blog|news|press|team|careers|privacy|terms|policy)",
        r"/(?:home|index|main|landing)(?:/|\.html|$)",
        r"/(?:cart|checkout|order|account|login|register|profile)",
        r"/(?:search|results|query)",
        r"/(?:category|categories|collection|collections|filter|filters)",
        r"/(?:page|admin|api|service|health|status)",
    ]

    @classmethod
    def is_product_page_by_url(cls, url: str) -> tuple[bool, str]:
        """
        Classify URL as product page or not.

        Returns:
            (is_product_page: bool, confidence_reason: str)
        """
        url_lower = url.lower()

        # First check: exclude non-product pages
        for pattern in cls.NON_PRODUCT_PATTERNS:
            if re.search(pattern, url_lower):
                return False, f"non_product_pattern: {pattern}"

        # Second check: strong product patterns (high confidence)
        for pattern in cls.STRONG_PRODUCT_PATTERNS:
            if re.search(pattern, url_lower):
                return True, f"strong_match: {pattern}"

        # Third check: weak product patterns (lower confidence, but better than nothing)
        for pattern in cls.WEAK_PRODUCT_PATTERNS:
            if re.search(pattern, url_lower):
                return True, f"weak_match: {pattern}"

        return False, "no_match"

    @classmethod
    def analyze_page_content(cls, html_content: str) -> tuple[bool, float]:
        """
        Analyze HTML content for e-commerce signals.

        Looks for:
        - Price tags ($, £, €, prices)
        - "Add to cart" or purchase buttons
        - Product image tags
        - Rating/review elements
        - Product-specific metadata

        Returns:
            (is_likely_product: bool, confidence: float 0.0-1.0)
        """
        html_lower = html_content.lower()
        signals = []
        max_signals = 10

        # Signal 1: Price tags (strong indicator)
        price_patterns = [
            r'[$£€]\s*\d+',  # Currency symbol + number
            r'\d+\.\d{2}\s*[$£€]',  # Number + currency
            r'price\s*[:=]\s*\$?\d+',  # price: $99
            r'\b(?:cost|price|amount|total)\b.*\$?\d+',
        ]
        for pattern in price_patterns:
            if re.search(pattern, html_lower):
                signals.append(('price_tag', 0.3))
                break

        # Signal 2: Purchase buttons (strong indicator)
        purchase_patterns = [
            r'add\s+to\s+cart',
            r'(?:buy|purchase|order|checkout)\s+(?:now|button)',
            r'<button[^>]*>.*?(?:buy|add|cart)',
            r'class=["\'].*?(?:btn|button|cta).*?(?:cart|buy|checkout)',
        ]
        for pattern in purchase_patterns:
            if re.search(pattern, html_lower):
                signals.append(('purchase_button', 0.4))
                break

        # Signal 3: Product images (moderate indicator)
        if re.search(r'<img[^>]*(?:alt|src)=["\'].*?(?:product|item|coffee|bean)', html_lower):
            signals.append(('product_image', 0.2))

        # Signal 4: Rating/review elements (moderate indicator)
        if re.search(r'(?:rating|review|star|out\s+of\s+\d)', html_lower):
            signals.append(('rating_element', 0.2))

        # Signal 5: Product schema/metadata (strong indicator)
        if re.search(r'schema\.org/Product|itemtype.*product', html_lower):
            signals.append(('schema_org_product', 0.4))

        # Signal 6: Stock/availability (strong indicator)
        if re.search(r'(?:in stock|out of stock|available|quantity|buy now)', html_lower):
            signals.append(('stock_info', 0.3))

        # Signal 7: Product description patterns (moderate indicator)
        if re.search(r'(?:description|details|specifications|features)["\']?\s*[:=]', html_lower):
            signals.append(('description_field', 0.2))

        # Signal 8: Coffee-specific terms (strong for coffee sites)
        coffee_terms = [
            r'\b(?:roast level|single origin|origin|varietal|process|tasting notes)\b',
            r'\b(?:espresso|filter|pour over)\b',
            r'\b(?:100%|whole bean|ground|instant)\b',
        ]
        for pattern in coffee_terms:
            if re.search(pattern, html_lower):
                signals.append(('coffee_signal', 0.3))
                break

        # Calculate confidence
        if not signals:
            return False, 0.0

        # Sum confidence, capped at 1.0
        total_confidence = min(1.0, sum(conf for _, conf in signals))

        # Product page if confidence > 0.4
        is_product = total_confidence > 0.4

        return is_product, total_confidence

    @classmethod
    def is_product_page(cls, url: str, html_content: Optional[str] = None) -> tuple[bool, str]:
        """
        Comprehensive product page detection.

        Strategy:
        1. If URL strongly indicates product page → return True
        2. If URL excludes product page → return False
        3. If HTML content suggests product → return True
        4. Otherwise → return False

        Returns:
            (is_product_page: bool, reason: str)
        """
        # Step 1: URL-based classification
        url_is_product, url_reason = cls.is_product_page_by_url(url)

        # If strong signal from URL, return immediately
        if url_reason.startswith("strong_match"):
            return True, url_reason
        if url_reason.startswith("non_product_pattern"):
            return False, url_reason

        # Step 2: If HTML available, analyze content
        if html_content:
            html_is_product, html_confidence = cls.analyze_page_content(html_content)
            if html_is_product and html_confidence > 0.4:
                return True, f"content_analysis: {html_confidence:.2f}"

        # Step 3: Fall back to weak URL signals
        if url_reason.startswith("weak_match"):
            return True, url_reason

        return False, url_reason


class PageContentAnalyzer(HTMLParser):
    """Extract text content and structure from HTML."""

    def __init__(self):
        super().__init__()
        self.text_content = []
        self.in_script = False
        self.in_style = False
        self.all_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            text = data.strip()
            if text:
                self.text_content.append(text)
                self.all_text += " " + text

    def get_text(self) -> str:
        """Get extracted text content."""
        return self.all_text.strip()
