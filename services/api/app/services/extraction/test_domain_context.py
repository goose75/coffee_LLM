"""
Test cases for domain context injection logic.
Validates roaster classification and context formatting.
"""

from domain_context import (
    RoasterType,
    infer_domain_type,
    format_domain_context_prompt,
)


def test_specialty_roaster_detection():
    """Test detection of specialty coffee roasters"""

    test_cases = [
        # (store_name, homepage_content, expected_result)
        (
            "Has Bean Coffee",
            "Single origin specialty coffees from around the world",
            RoasterType.SPECIALTY,
        ),
        (
            "Colonna Coffee",
            "Specialty grade single-origin espresso beans for pour-over and espresso",
            RoasterType.SPECIALTY,
        ),
        (
            "Square Mile Coffee",
            "Third-wave artisan specialty roaster. Hand-selected single-estate microlots",
            RoasterType.SPECIALTY,
        ),
        (
            "Monmouth Coffee",
            "Craft roaster specializing in direct trade single origins",
            RoasterType.SPECIALTY,
        ),
    ]

    for store_name, content, expected in test_cases:
        result = infer_domain_type(store_name, content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {store_name}: {result} (expected {expected})")
        assert result == expected, f"Failed for {store_name}"


def test_commodity_roaster_detection():
    """Test detection of commodity coffee suppliers"""

    test_cases = [
        (
            "Budget Coffee Supplies",
            "Bulk coffee wholesale and discount catering packs",
            RoasterType.COMMODITY,
        ),
        (
            "Office Coffee Ltd",
            "Commercial instant coffee and bulk ordering for businesses",
            RoasterType.COMMODITY,
        ),
        (
            "Generic Coffee Co",
            "Standard blend instant coffee with volume discounts",
            RoasterType.COMMODITY,
        ),
    ]

    for store_name, content, expected in test_cases:
        result = infer_domain_type(store_name, content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {store_name}: {result} (expected {expected})")
        assert result == expected, f"Failed for {store_name}"


def test_unknown_roaster_detection():
    """Test detection of unknown/ambiguous roasters"""

    test_cases = [
        ("Random Coffee Store", "", RoasterType.UNKNOWN),
        ("Coffee Plus", "We sell coffee", RoasterType.UNKNOWN),
        ("Beans & Stuff", "High quality low quality", RoasterType.UNKNOWN),
    ]

    for store_name, content, expected in test_cases:
        result = infer_domain_type(store_name, content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {store_name}: {result} (expected {expected})")
        assert result == expected, f"Failed for {store_name}"


def test_context_formatting():
    """Test formatting of domain context for prompt injection"""

    # Sample historical patterns
    patterns = {
        "typical_fields": ["origin", "process", "roast", "varietal"],
        "typical_confidence": [0.78, 0.65, 0.92],
        "typical_price_range": "£8.50-£15.99",
        "common_missing_fields": [],
    }

    context = format_domain_context_prompt(
        RoasterType.SPECIALTY,
        patterns,
        "Has Bean Coffee"
    )

    print("\n📝 Sample Domain Context (Specialty):")
    print(context)
    print()

    # Verify key components are in output
    assert "specialty coffee roaster" in context
    assert "Has Bean Coffee" in context
    assert "origin, process, roast, varietal" in context
    assert "0.78" in context
    assert "£8.50-£15.99" in context
    assert "common" not in context.lower() or "none" in context  # No common missing fields

    # Test commodity context
    commodity_patterns = {
        "typical_fields": ["weight", "price"],
        "typical_confidence": [0.32, 0.15, 0.55],
        "typical_price_range": "£2.00-£5.00",
        "common_missing_fields": ["origin", "process", "roast"],
    }

    commodity_context = format_domain_context_prompt(
        RoasterType.COMMODITY,
        commodity_patterns,
        "Budget Coffee"
    )

    print("📝 Sample Domain Context (Commodity):")
    print(commodity_context)
    print()

    assert "commodity coffee supplier" in commodity_context
    assert "Budget Coffee" in commodity_context
    assert "origin, process, roast" in commodity_context  # Missing fields


if __name__ == "__main__":
    print("🧪 Testing Domain Context Injection Logic\n")
    print("=" * 60)

    print("\n1️⃣  Testing Specialty Roaster Detection...")
    test_specialty_roaster_detection()
    print("✅ All specialty tests passed!\n")

    print("2️⃣  Testing Commodity Roaster Detection...")
    test_commodity_roaster_detection()
    print("✅ All commodity tests passed!\n")

    print("3️⃣  Testing Unknown Roaster Detection...")
    test_unknown_roaster_detection()
    print("✅ All unknown tests passed!\n")

    print("4️⃣  Testing Context Formatting...")
    test_context_formatting()
    print("✅ All formatting tests passed!\n")

    print("=" * 60)
    print("\n✨ All domain context tests passed successfully!")
    print("\n📊 Summary:")
    print("  - Specialty roaster detection: ✅ Working")
    print("  - Commodity roaster detection: ✅ Working")
    print("  - Unknown roaster detection: ✅ Working")
    print("  - Context formatting: ✅ Working")
    print("\n🚀 Ready for prompt injection into v2.0.0!")
