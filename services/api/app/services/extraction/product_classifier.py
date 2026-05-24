"""
Product classifier to distinguish coffee beans from non-coffee products.

Filters out:
- Coffee pods (capsules, K-Cups, Nespresso, etc.)
- Coffee machines, grinders, brewers
- Tea, chai, and other beverages
- Coffee subscriptions, bundles, gift sets
- Coffee utensils and accessories
- Decaf blends that aren't pure coffee
"""

import re
from typing import Optional


class ProductClassifier:
    """Classify products as coffee beans or non-coffee items."""

    # Patterns for products to EXCLUDE
    NON_COFFEE_PATTERNS = {
        # Tea products
        "tea": r"\b(teas?|chai|rooibos|herbal|matcha)\b",

        # Coffee pods and capsules
        "pods": r"\b(pods?|capsules?|k-?cups?|nespresso|dolce gusto|keurig)\b",

        # Coffee machines and equipment
        "machines": r"\b(machines?|makers?|brewers?|espresso machines?|coffee makers?|grinders?|burr grinders?|scales?|pitchers?)\b",

        # Courses and training (non-product)
        "courses": r"\b(courses?|trainings?|lessons?|classes?|workshops?|barista|latte art)\b",

        # Utensils and accessories
        "utensils": r"\b(cups?|mugs?|glasses?|tumblers?|filters?|baskets?|scoops?|tampers?|portafilters?|coasters?)\b",

        # Subscriptions and bundles
        "bundles": r"\b(subscriptions?|bundles?|gift sets?|gift courses?|packs?|samplers?|collections?|combos?|starter kits?)\b",

        # Non-coffee beverages
        "other_beverages": r"\b(chocolates?|cocoas?|hot chocolates?|smoothies?|shakes?|juices?|energy drinks?|proteins?)\b",

        # Decaf blends that aren't coffee
        "decaf_non_coffee": r"decaf\s+(teas?|chai|rooibos|herbal)",
    }

    @classmethod
    def is_coffee_bean_product(
        cls,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Classify a product as coffee bean or non-coffee.

        Args:
            title: Product title/name
            description: Product description

        Returns:
            (is_coffee_bean: bool, reason: Optional[str])
            If is_coffee_bean is False, reason explains why
        """
        combined_text = f"{title or ''} {description or ''}".lower()

        if not combined_text.strip():
            return True, None  # Default to coffee if no text

        # Check each non-coffee pattern
        for pattern_name, pattern in cls.NON_COFFEE_PATTERNS.items():
            if re.search(pattern, combined_text):
                return False, f"Non-coffee product: {pattern_name}"

        # Additional heuristic: if "coffee" or "bean" appears, it's likely coffee
        # This helps avoid false positives on ambiguous descriptions
        has_coffee_keyword = bool(
            re.search(r"\b(coffee|bean|origin|roast|espresso|filter)\b", combined_text)
        )

        # If no coffee keywords AND looks like a beverage, it's suspicious
        if not has_coffee_keyword and re.search(
            r"\b(blend|drink|beverage|drinkers|brew)\b", combined_text
        ):
            # More lenient - only exclude if it matches a known pattern
            # (we already checked those above)
            pass

        return True, None

    @classmethod
    def filter_coffee_products(
        cls,
        products: list[dict],
        title_field: str = "title",
        description_field: str = "description",
    ) -> tuple[list[dict], list[tuple[dict, str]]]:
        """
        Filter a list of products, separating coffee from non-coffee.

        Args:
            products: List of product dicts with title/description
            title_field: Key name for title in product dict
            description_field: Key name for description in product dict

        Returns:
            (coffee_products, non_coffee_products)
            non_coffee_products is list of (product, reason) tuples
        """
        coffee_products = []
        non_coffee_products = []

        for product in products:
            title = product.get(title_field, "")
            description = product.get(description_field, "")
            is_coffee, reason = cls.is_coffee_bean_product(title, description)

            if is_coffee:
                coffee_products.append(product)
            else:
                non_coffee_products.append((product, reason))

        return coffee_products, non_coffee_products
