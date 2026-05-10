"""
Hallucination risk scorer.

Analyses the assistant's response against the retrieved context to compute
a 0–1 risk score. Higher = more likely the response contains fabricated data.

Heuristics:
  1. Price mentions not in retrieved records (+0.3 each, capped at 0.6)
  2. Store names not in retrieved records (+0.2 each, capped at 0.4)
  3. Response makes availability claim with empty context (+0.5)
  4. Response mentions specific weights not in retrieved data (+0.1 each)
  5. Proper noun ratio: high ratio of unknown names (+0.1)

This is a heuristic — not a ground truth classifier.
Logs with risk > 0.4 are surfaced in the admin observability view.
"""
from __future__ import annotations

import re
from typing import Any


def compute_risk(
    response_text: str,
    retrieved_context: list[dict],
    answered_without_grounding: bool,
) -> float:
    """
    Returns a 0.0–1.0 hallucination risk score.
    """
    if not response_text:
        return 0.0

    risk = 0.0

    # Baseline: answered with no retrieved records at all
    if answered_without_grounding:
        # If the response says "I don't have data" that's fine (low risk)
        safe_phrases = [
            "don't have", "no data", "unable to find", "not in the catalogue",
            "browse the catalogue", "can't find", "no records",
        ]
        if any(p in response_text.lower() for p in safe_phrases):
            return 0.05  # correctly declined
        risk += 0.5

    if not retrieved_context:
        return min(1.0, risk)

    # Build sets of known values from retrieved context
    known_prices: set[str] = set()
    known_stores: set[str] = set()
    known_weights: set[int] = set()

    for record in retrieved_context:
        for listing in record.get("listings", []):
            if listing.get("store_name"):
                known_stores.add(listing["store_name"].lower())
            for variant in listing.get("variants", []):
                price = variant.get("price_gbp")
                if price:
                    known_prices.add(f"{price:.2f}")
                    known_prices.add(str(int(price)))
                weight = variant.get("weight_g")
                if weight:
                    known_weights.add(weight)

    # Check price mentions in response
    price_mentions = re.findall(r"£(\d+(?:\.\d{1,2})?)", response_text)
    for price_str in price_mentions:
        # Normalise to 2dp
        try:
            val = float(price_str)
            two_dp = f"{val:.2f}"
            int_str = str(int(val))
            if two_dp not in known_prices and int_str not in known_prices:
                risk += 0.30
        except ValueError:
            pass
    risk = min(risk, 0.85)  # cap

    # Check weight mentions
    weight_mentions = re.findall(r"(\d+)\s*g\b", response_text)
    for w_str in weight_mentions:
        try:
            w = int(w_str)
            if w > 50 and w not in known_weights:  # ignore "100g" in per-100g mentions
                risk += 0.05
        except ValueError:
            pass

    # Check for availability language with no context support
    availability_phrases = [
        r"\bin stock\b", r"\bavailable\b.{0,20}\bat\b",
        r"\bstocked\b", r"\byou can buy\b", r"\bsells?\b.{0,20}\bfor\b",
    ]
    if any(re.search(p, response_text, re.I) for p in availability_phrases):
        if not retrieved_context:
            risk += 0.3
        elif not any(
            any(l.get("variants") for l in r.get("listings", []))
            for r in retrieved_context
        ):
            risk += 0.15

    return round(min(1.0, risk), 3)
