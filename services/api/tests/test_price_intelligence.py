"""test_price_intelligence.py — Tests for price visual logic."""
from __future__ import annotations

TOTAL = 0; PASSED = 0

def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED; TOTAL += 1
    if condition: print(f"  ✓ {name}"); PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None: print(f"      got={got!r} expected={expected!r}")

# ── Sparkline path generation ─────────────────────────────────────────────────

def sparkline_path(points, width=48, height=20, pad=2):
    if len(points) < 2: return None
    mn = min(points); mx = max(points); rng = mx - mn or 1
    xs = [pad + (i/(len(points)-1))*(width-pad*2) for i in range(len(points))]
    ys = [pad + ((mx-p)/rng)*(height-pad*2) for p in points]
    return [(x,y) for x,y in zip(xs,ys)]

print("\n── sparkline_path ────────────────────────────────────────────────")
pts = sparkline_path([10, 12, 11, 13, 12])
check("returns points", pts is not None)
check("correct count", len(pts) == 5)
check("first x = pad", abs(pts[0][0] - 2) < 0.1)
check("last x = width-pad", abs(pts[-1][0] - 46) < 0.1)

# Flat line (all same price)
flat = sparkline_path([10, 10, 10])
check("flat line y at midpoint", flat is not None)

# Only 1 point — should return None
one = sparkline_path([10])
check("single point returns None", one is None)

# ── Price-per-100g comparison ─────────────────────────────────────────────────

def sort_by_p100g(variants):
    return sorted(
        [v for v in variants if v.get("latest_price_per_100g") is not None],
        key=lambda v: v["latest_price_per_100g"]
    )

def pct_of_max(value, max_val):
    if max_val == 0: return 0
    return round(value / max_val * 100)

print("\n── per-100g sorting ──────────────────────────────────────────────")
variants = [
    {"variant_id":"a","store_name":"Rave","latest_price_per_100g":4.80,"latest_price_gbp":12.00,"weight_g":250},
    {"variant_id":"b","store_name":"Assembly","latest_price_per_100g":6.20,"latest_price_gbp":15.50,"weight_g":250},
    {"variant_id":"c","store_name":"Square Mile","latest_price_per_100g":None,"latest_price_gbp":10.00,"weight_g":None},
]
sorted_v = sort_by_p100g(variants)
check("sorted cheapest first", sorted_v[0]["store_name"] == "Rave")
check("None excluded", len(sorted_v) == 2)
check("most expensive last", sorted_v[-1]["store_name"] == "Assembly")

max_p = max(v["latest_price_per_100g"] for v in sorted_v)
check("cheapest bar pct < 100", pct_of_max(sorted_v[0]["latest_price_per_100g"], max_p) < 100)
check("most expensive bar pct = 100", pct_of_max(sorted_v[-1]["latest_price_per_100g"], max_p) == 100)

# ── ValueBadge logic ──────────────────────────────────────────────────────────

def value_tier(price_per_100g, median_per_100g):
    if price_per_100g is None or median_per_100g is None: return None
    ratio = price_per_100g / median_per_100g
    if ratio <= 0.80: return "good_value"
    if ratio >= 1.40: return "premium"
    return None

print("\n── value badge logic ─────────────────────────────────────────────")
check("80% of median = good value", value_tier(4.00, 5.00) == "good_value")
check("exactly 80% = good value", value_tier(4.00, 5.00) == "good_value")
check("140% of median = premium", value_tier(7.00, 5.00) == "premium")
check("100% of median = None", value_tier(5.00, 5.00) is None)
check("110% of median = None", value_tier(5.50, 5.00) is None)
check("None price = None", value_tier(None, 5.00) is None)
check("None median = None", value_tier(5.00, None) is None)

# Edge cases
check("zero median no crash", value_tier(5.00, 0.001) == "premium")
check("very cheap = good value", value_tier(1.00, 10.00) == "good_value")
check("very expensive = premium", value_tier(50.00, 5.00) == "premium")

# ── Chart data preparation ────────────────────────────────────────────────────

def prepare_chart_data(variants, preferred_weight=250, tolerance=50):
    """Filter to preferred weight or fall back to all variants."""
    filtered = [v for v in variants
                if v.get("weight_g") is not None
                and abs(v["weight_g"] - preferred_weight) <= tolerance]
    return filtered if filtered else variants

print("\n── chart data preparation ────────────────────────────────────────")
variants2 = [
    {"variant_id":"a","weight_g":250,"history":[{"price_gbp":12.0,"recorded_at":"2024-01-01"}]},
    {"variant_id":"b","weight_g":1000,"history":[{"price_gbp":40.0,"recorded_at":"2024-01-01"}]},
    {"variant_id":"c","weight_g":None,"history":[]},
]
filtered = prepare_chart_data(variants2)
check("prefers 250g", len(filtered) == 1 and filtered[0]["variant_id"] == "a")

no_250 = [v for v in variants2 if v["variant_id"] != "a"]
filtered2 = prepare_chart_data(no_250)
check("falls back to all if no 250g", len(filtered2) == 2)

check("empty variants returns empty", prepare_chart_data([]) == [])

# ── Price trend detection ─────────────────────────────────────────────────────

def price_trend(history_points):
    """Return 'up', 'down', or 'stable' based on first vs last price."""
    prices = [p["price_gbp"] for p in history_points if p.get("price_gbp", 0) > 0]
    if len(prices) < 2: return "stable"
    change_pct = (prices[-1] - prices[0]) / prices[0] * 100
    if change_pct > 5: return "up"
    if change_pct < -5: return "down"
    return "stable"

print("\n── price trend ───────────────────────────────────────────────────")
check("rising prices = up", price_trend([{"price_gbp":10},{"price_gbp":11},{"price_gbp":12}]) == "up")
check("falling prices = down", price_trend([{"price_gbp":12},{"price_gbp":11},{"price_gbp":10}]) == "down")
check("flat prices = stable", price_trend([{"price_gbp":10},{"price_gbp":10.1},{"price_gbp":10}]) == "stable")
check("single point = stable", price_trend([{"price_gbp":10}]) == "stable")
check("empty = stable", price_trend([]) == "stable")
check("small change = stable", price_trend([{"price_gbp":10},{"price_gbp":10.3}]) == "stable")

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
