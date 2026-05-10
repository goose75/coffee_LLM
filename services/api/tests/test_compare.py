"""
test_compare.py — Tests for coffee comparison logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# ── Inline compare logic for standalone testing ───────────────────────────────

ROAST_SCORES = {"light": 20, "medium_light": 38, "medium": 55, "medium_dark": 72, "dark": 90}
PROCESS_BODY_BOOST = {"natural": 15, "honey": 8, "anaerobic": 12, "washed": 0, "wet_hulled": 5}
PROCESS_ACIDITY_BOOST = {"washed": 15, "honey": 5, "natural": -5, "anaerobic": 8, "wet_hulled": -8}
ORIGIN_ACIDITY = {
    "Ethiopia": 20, "Kenya": 22, "Colombia": 12, "Brazil": -10, "Indonesia": -15,
}

@dataclass
class FakeBean:
    id: str = "abc"
    canonical_name: str = "Test Coffee"
    roast_level: str | None = "medium"
    process: str | None = "washed"
    origin_country: str | None = None
    origin_region: str | None = None
    espresso_suitable_flag: bool = True
    filter_suitable_flag: bool = True
    decaf_flag: bool = False
    flavour_notes: list[str] = field(default_factory=list)
    harvest_year: int | None = None
    altitude_masl_min: int | None = None
    altitude_masl_max: int | None = None
    varietal: list[str] = field(default_factory=list)
    data_completeness_score: float = 0.5

def compute_sensory(bean, family_weights):
    roast = bean.roast_level or "medium"
    process = bean.process or "washed"
    origin = bean.origin_country or ""
    roast_score = ROAST_SCORES.get(roast, 55)
    body = 30 + (roast_score * 0.4) + PROCESS_BODY_BOOST.get(process, 0)
    body = max(5, min(95, body))
    acidity = 80 - (roast_score * 0.6) + PROCESS_ACIDITY_BOOST.get(process, 0)
    acidity += ORIGIN_ACIDITY.get(origin, 0)
    acidity = max(5, min(95, acidity))
    sweetness = 50 + PROCESS_BODY_BOOST.get(process, 0) * 1.5 - (roast_score - 55) * 0.3
    sweetness = max(5, min(95, sweetness))
    family_count = len([v for v in family_weights.values() if v > 0])
    complexity = 20 + family_count * 10 + (15 if process == "anaerobic" else 0)
    complexity = max(5, min(95, complexity))
    return {
        "roast": round(roast_score),
        "body": round(body),
        "acidity": round(acidity),
        "sweetness": round(sweetness),
        "complexity": round(complexity),
    }

def generate_contrast(coffees):
    if len(coffees) < 2:
        return ""
    a, b = coffees[0], coffees[1]
    a_name = a["canonical_name"].split(",")[0].strip()
    b_name = b["canonical_name"].split(",")[0].strip()
    parts = []
    ra, rb = a["sensory"]["roast"], b["sensory"]["roast"]
    if abs(ra - rb) >= 20:
        lighter = a_name if ra < rb else b_name
        darker = b_name if ra < rb else a_name
        parts.append(f"{lighter} is lighter roasted, {darker} is darker and more intense")
    aa, ab = a["sensory"]["acidity"], b["sensory"]["acidity"]
    if abs(aa - ab) >= 15:
        brighter = a_name if aa > ab else b_name
        softer = b_name if aa > ab else a_name
        parts.append(f"{brighter} has brighter acidity while {softer} is smoother")
    a_families = sorted(a["family_weights"].items(), key=lambda x: -x[1])
    b_families = sorted(b["family_weights"].items(), key=lambda x: -x[1])
    a_top = a_families[0][0] if a_families and a_families[0][1] > 0 else None
    b_top = b_families[0][0] if b_families and b_families[0][1] > 0 else None
    if a_top and b_top and a_top != b_top:
        parts.append(f"{a_name} leans {a_top} while {b_name} is more {b_top}-led")
    elif a_top and b_top and a_top == b_top:
        parts.append(f"both share {a_top} character")
    pa, pb = a.get("process"), b.get("process")
    if pa and pb and pa != pb:
        parts.append(f"{a_name} is {pa}-processed giving it different structure to the {pb} {b_name}")
    if not parts:
        return f"{a_name} and {b_name} share a similar profile."
    return ". ".join(parts[:3]) + "."

# ── Tests ──────────────────────────────────────────────────────────────────────
TOTAL = 0; PASSED = 0

def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED
    TOTAL += 1
    if condition:
        print(f"  ✓ {name}"); PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None: print(f"      got={got!r}, expected={expected!r}")

print("\n── Roast score mapping ───────────────────────────────────────────")
check("light → 20", ROAST_SCORES["light"] == 20)
check("medium → 55", ROAST_SCORES["medium"] == 55)
check("dark → 90", ROAST_SCORES["dark"] == 90)

print("\n── compute_sensory ───────────────────────────────────────────────")
light_washed = FakeBean(roast_level="light", process="washed", origin_country="Ethiopia")
dark_natural = FakeBean(roast_level="dark", process="natural", origin_country="Brazil")

ls = compute_sensory(light_washed, {})
ds = compute_sensory(dark_natural, {})

check("light washed has lower roast than dark natural", ls["roast"] < ds["roast"])
check("light washed has higher acidity than dark natural", ls["acidity"] > ds["acidity"])
check("dark natural has higher body than light washed", ds["body"] > ls["body"])
check("all scores 0–100", all(0 <= v <= 100 for v in ls.values()))
check("all scores 0–100 dark", all(0 <= v <= 100 for v in ds.values()))

# Anaerobic process gets complexity boost
anaerobic = FakeBean(roast_level="medium", process="anaerobic")
family_weights = {"fruity": 3, "floral": 2}
s = compute_sensory(anaerobic, family_weights)
simple = compute_sensory(FakeBean(roast_level="medium", process="washed"), {})
check("anaerobic with families more complex", s["complexity"] > simple["complexity"])

# Natural process has higher body
nat = compute_sensory(FakeBean(process="natural"), {})
was = compute_sensory(FakeBean(process="washed"), {})
check("natural higher body than washed", nat["body"] > was["body"])
check("washed higher acidity than natural", was["acidity"] > nat["acidity"])

# Origin influences acidity
eth = compute_sensory(FakeBean(origin_country="Ethiopia", process="washed", roast_level="light"), {})
bra = compute_sensory(FakeBean(origin_country="Brazil", process="washed", roast_level="light"), {})
check("Ethiopian higher acidity than Brazilian", eth["acidity"] > bra["acidity"])

print("\n── generate_contrast ─────────────────────────────────────────────")

def make_item(name, roast, process, origin, families):
    bean = FakeBean(canonical_name=name, roast_level=roast, process=process, origin_country=origin)
    fw = {k: v for k, v in families.items()}
    s = compute_sensory(bean, fw)
    return {"canonical_name": name, "sensory": s, "family_weights": fw, "process": process}

eth_item = make_item("Ethiopia Yirgacheffe", "light", "natural", "Ethiopia", {"fruity": 5, "floral": 3})
bra_item = make_item("Brazil Santos", "dark", "natural", "Brazil", {"chocolate": 4, "nutty": 3})

contrast = generate_contrast([eth_item, bra_item])
check("contrast is non-empty", len(contrast) > 0, contrast)
check("contrast ends with period", contrast.endswith("."), contrast)
check("contrast mentions lighter/darker", "lighter" in contrast or "darker" in contrast or "roast" in contrast.lower(), contrast)

# Same roast, same process — should still generate output
a = make_item("Coffee A", "medium", "washed", "Kenya", {"fruity": 4, "floral": 2})
b = make_item("Coffee B", "medium", "washed", "Colombia", {"chocolate": 4, "nutty": 2})
contrast2 = generate_contrast([a, b])
check("different families generates contrast", "fruity" in contrast2 or "chocolate" in contrast2, contrast2)

# Single coffee — no contrast
single = generate_contrast([eth_item])
check("single coffee no contrast", single == "", single)

# Identical coffees
same = generate_contrast([eth_item, eth_item])
check("identical coffees → 'share' language", "share" in same or "similar" in same, same)

print("\n── Shared notes ──────────────────────────────────────────────────")
a_notes = ["cherry", "lemon", "jasmine"]
b_notes = ["cherry", "chocolate", "jasmine"]
shared = list(set(a_notes) & set(b_notes))
check("shared notes found", sorted(shared) == ["cherry", "jasmine"], shared)

a_notes2 = ["vanilla"]
b_notes2 = ["chocolate"]
shared2 = list(set(a_notes2) & set(b_notes2))
check("no shared notes → empty", shared2 == [], shared2)

print("\n── Edge cases ────────────────────────────────────────────────────")
no_roast = FakeBean(roast_level=None, process=None)
s = compute_sensory(no_roast, {})
check("None roast/process no crash", all(0 <= v <= 100 for v in s.values()))

# Unknown roast level defaults gracefully
unknown = FakeBean(roast_level="espresso_light", process="washed")
s2 = compute_sensory(unknown, {})
check("unknown roast defaults to 55", s2["roast"] == 55)

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
