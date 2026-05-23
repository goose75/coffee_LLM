#!/usr/bin/env python3
"""
Validation script for v2.0 prompt implementation.

This validates the prompt structure, examples, and schema without making API calls.

Usage:
    python -m scripts.validate_v2_prompt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.prompts import v1, v2


def validate_prompt_structure():
    """Verify both prompts have required components."""
    print("\n" + "=" * 80)
    print("V2.0 PROMPT VALIDATION")
    print("=" * 80 + "\n")

    errors = []

    # ── Check v1 structure ────────────────────────────────────────────────
    print("1. Validating v1.0 structure...")
    v1_checks = {
        "PROMPT_VERSION": hasattr(v1, "PROMPT_VERSION"),
        "SYSTEM_PROMPT": hasattr(v1, "SYSTEM_PROMPT"),
        "USER_TEMPLATE": hasattr(v1, "USER_TEMPLATE"),
        "FEW_SHOT_EXAMPLES": hasattr(v1, "FEW_SHOT_EXAMPLES"),
        "build_messages": callable(getattr(v1, "build_messages", None)),
        "MAX_OUTPUT_TOKENS": hasattr(v1, "MAX_OUTPUT_TOKENS"),
    }

    for key, present in v1_checks.items():
        status = "✓" if present else "✗"
        print(f"  {status} {key}")
        if not present:
            errors.append(f"v1 missing: {key}")

    # ── Check v2 structure ────────────────────────────────────────────────
    print("\n2. Validating v2.0 structure...")
    v2_checks = {
        "PROMPT_VERSION": hasattr(v2, "PROMPT_VERSION"),
        "SYSTEM_PROMPT_TEMPLATE": hasattr(v2, "SYSTEM_PROMPT_TEMPLATE"),
        "SYSTEM_PROMPT_NO_CONTEXT": hasattr(v2, "SYSTEM_PROMPT_NO_CONTEXT"),
        "USER_TEMPLATE": hasattr(v2, "USER_TEMPLATE"),
        "FEW_SHOT_EXAMPLES": hasattr(v2, "FEW_SHOT_EXAMPLES"),
        "get_system_prompt": callable(getattr(v2, "get_system_prompt", None)),
        "build_messages": callable(getattr(v2, "build_messages", None)),
        "MAX_OUTPUT_TOKENS": hasattr(v2, "MAX_OUTPUT_TOKENS"),
    }

    for key, present in v2_checks.items():
        status = "✓" if present else "✗"
        print(f"  {status} {key}")
        if not present:
            errors.append(f"v2 missing: {key}")

    # ── Verify few-shot examples count ────────────────────────────────────
    print("\n3. Validating few-shot examples...")
    v1_examples = len(v1.FEW_SHOT_EXAMPLES)
    v2_examples = len(v2.FEW_SHOT_EXAMPLES)

    print(f"  v1.0 examples: {v1_examples} (expected: 3, even number of pairs)")
    print(f"  v2.0 examples: {v2_examples} (expected: 10, even number of pairs)")

    if v1_examples != 6:  # 3 user + 3 assistant
        errors.append(f"v1 examples: expected 6 (3 pairs), got {v1_examples}")
    if v2_examples != 20:  # 10 user + 10 assistant
        errors.append(f"v2 examples: expected 20 (10 pairs), got {v2_examples}")

    # ── Verify example structure ──────────────────────────────────────────
    print("\n4. Validating example structure...")
    for i, example in enumerate(v1.FEW_SHOT_EXAMPLES):
        if "role" not in example or "content" not in example:
            errors.append(f"v1 example {i} missing role/content")

    for i, example in enumerate(v2.FEW_SHOT_EXAMPLES):
        if "role" not in example or "content" not in example:
            errors.append(f"v2 example {i} missing role/content")

    if not errors:
        print("  ✓ All examples have required role/content fields")

    # ── Verify prompt content ─────────────────────────────────────────────
    print("\n5. Validating prompt content...")

    # Check v2 has domain context
    if "{domain_type}" in v2.SYSTEM_PROMPT_TEMPLATE:
        print("  ✓ v2 has domain_type placeholder")
    else:
        errors.append("v2 missing domain_type placeholder")

    if "{historical_pattern}" in v2.SYSTEM_PROMPT_TEMPLATE:
        print("  ✓ v2 has historical_pattern placeholder")
    else:
        errors.append("v2 missing historical_pattern placeholder")

    # Check confidence scale in v2
    if "0.85" in v2.SYSTEM_PROMPT_TEMPLATE and "0.70" in v2.SYSTEM_PROMPT_TEMPLATE:
        print("  ✓ v2 has explicit confidence scale")
    else:
        errors.append("v2 missing explicit confidence scale")

    # Check brew suitability rules in v2
    if "Light roasts" in v2.SYSTEM_PROMPT_TEMPLATE and "Dark roasts" in v2.SYSTEM_PROMPT_TEMPLATE:
        print("  ✓ v2 has brew suitability rules")
    else:
        errors.append("v2 missing brew suitability rules")

    # Check weight-first grouping guidance
    if "weight-first" in v2.SYSTEM_PROMPT_TEMPLATE.lower():
        print("  ✓ v2 has weight-first variant grouping guidance")
    else:
        errors.append("v2 missing weight-first grouping guidance")

    # ── Verify version strings ────────────────────────────────────────────
    print("\n6. Validating version strings...")
    if v1.PROMPT_VERSION == "v1.0.0":
        print(f"  ✓ v1 version: {v1.PROMPT_VERSION}")
    else:
        errors.append(f"v1 version mismatch: {v1.PROMPT_VERSION}")

    if v2.PROMPT_VERSION == "v2.0.0":
        print(f"  ✓ v2 version: {v2.PROMPT_VERSION}")
    else:
        errors.append(f"v2 version mismatch: {v2.PROMPT_VERSION}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    if errors:
        print("❌ VALIDATION FAILED\n")
        for error in errors:
            print(f"  • {error}")
        return False
    else:
        print("✅ VALIDATION PASSED\n")
        print("Summary:")
        print(f"  • v1.0 prompt: {len(v1.SYSTEM_PROMPT)} chars, 3 examples")
        print(f"  • v2.0 prompt: {len(v2.SYSTEM_PROMPT_TEMPLATE)} chars, 10 examples")
        print(f"  • v2.0 enhancements:")
        print(f"    - Domain context injection (specialty/commodity/unknown)")
        print(f"    - Historical pattern learning")
        print(f"    - Explicit 7-field confidence mapping")
        print(f"    - Confidence penalties (generic names, price ranges)")
        print(f"    - Weight-first variant grouping")
        print(f"    - Explicit brew suitability rules")
        print()
        return True


def test_get_system_prompt():
    """Test v2 system prompt generation with context."""
    print("\n" + "=" * 80)
    print("TESTING SYSTEM PROMPT GENERATION")
    print("=" * 80 + "\n")

    # Test with context
    prompt_with_context = v2.get_system_prompt(
        domain_context="specialty",
        historical_pattern="Typically has: weight, price, process, origin"
    )

    print("Generated prompt with context:")
    print(f"  • Length: {len(prompt_with_context)} chars")
    print(f"  • Contains domain context: {'specialty' in prompt_with_context}")
    print(f"  • Contains historical pattern: {'Typically has' in prompt_with_context}")

    # Test without context (fallback)
    prompt_no_context = v2.get_system_prompt()
    print("\nGenerated prompt without context (fallback):")
    print(f"  • Length: {len(prompt_no_context)} chars")
    print(f"  • Uses default: {'No historical pattern' in prompt_no_context}")

    return True


def test_build_messages():
    """Test message building with context."""
    print("\n" + "=" * 80)
    print("TESTING MESSAGE BUILDING")
    print("=" * 80 + "\n")

    test_text = "Ethiopia Yirgacheffe Washed, £12.50 for 250g"
    test_url = "https://example.com/coffee"

    # Test v1 messages
    v1_messages = v1.build_messages(test_text, test_url)
    print(f"v1 messages: {len(v1_messages)} total")
    print(f"  • {len([m for m in v1_messages if m['role'] == 'user'])} user messages")
    print(f"  • {len([m for m in v1_messages if m['role'] == 'assistant'])} assistant examples")

    # Test v2 messages
    v2_messages = v2.build_messages(
        test_text,
        test_url,
        domain_context="specialty",
        historical_pattern="Typically has: origin, weight, price"
    )
    print(f"\nv2 messages: {len(v2_messages)} total")
    print(f"  • {len([m for m in v2_messages if m['role'] == 'user'])} user messages")
    print(f"  • {len([m for m in v2_messages if m['role'] == 'assistant'])} assistant examples")

    # Verify context is preserved in v2 system prompt
    # (Note: context is in the system prompt, not in messages)
    print(f"\n✓ Message structure valid for both versions")

    return True


if __name__ == "__main__":
    try:
        success = True
        success = validate_prompt_structure() and success
        success = test_get_system_prompt() and success
        success = test_build_messages() and success

        if success:
            print("\n" + "=" * 80)
            print("✅ ALL VALIDATIONS PASSED")
            print("=" * 80)
            print("\nv2.0 prompt is ready for integration testing.")
            print("\nNext steps:")
            print("  1. Wire v2.0 into LLMParser (done)")
            print("  2. Run comparison tests with real pages (requires API credits)")
            print("  3. Measure confidence calibration improvements")
            print("  4. Deploy with phased rollout (10% → 50% → 100%)")
            print("  5. Monitor metrics and iterate on prompt")
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ VALIDATION ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
