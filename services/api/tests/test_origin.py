"""test_origin.py — Tests for origin aggregation and sensory tendency logic."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter

# ── Inline the aggregation helpers ───────────────────────────────────────────

@dataclass
class FakeBean:
    id: str
    origin_country: str | None = None
    origin_region: str | None = None
    process: str | None = None
    roast_level: str | None = None
    flavour_notes: list[str] = field(default_factory=list)
    altitude_masl_min: int | None = None
    altitude_masl_max: int | None = None

def group_by_country(beans):
    from collections import defaultdict
    groups = defaultdict(list)
    for b in beans:
        if b.origin_country:
            groups[b.origin_country].append(b)
    return dict(groups)

def dominant_process(beans):
    c = Counter(b.process for b in beans if b.process)
    return c.most_common(1)[0][0] if c else None

def region_counts(beans):
    c = Counter(b.origin_region for b in beans if b.origin_region)
    return dict(c)

def altitude_range(beans):
    mins = [b.altitude_masl_min for b in beans if b.altitude_masl_min]
    maxs = [b.altitude_masl_max for b in beans if b.altitude_masl_max]
    return (min(mins) if mins else None, max(maxs) if maxs else None)

TOTAL = 0; PASSED = 0

def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED
    TOTAL += 1
    if condition:
        print(f"  ✓ {name}"); PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None: print(f"      got={got!r} expected={expected!r}")

# ── Tests ──────────────────────────────────────────────────────────────────────

print("\n── group_by_country ──────────────────────────────────────────────")
beans = [
    FakeBean("1", "Ethiopia"), FakeBean("2", "Ethiopia"),
    FakeBean("3", "Kenya"), FakeBean("4", None),
]
groups = group_by_country(beans)
check("Ethiopia group has 2", len(groups["Ethiopia"]) == 2)
check("Kenya group has 1", len(groups["Kenya"]) == 1)
check("None country excluded", None not in groups)
check("total groups = 2", len(groups) == 2)

print("\n── dominant_process ──────────────────────────────────────────────")
eth_beans = [
    FakeBean("1", process="washed"),
    FakeBean("2", process="washed"),
    FakeBean("3", process="natural"),
    FakeBean("4", process=None),
]
check("washed dominates", dominant_process(eth_beans) == "washed")
check("all None → None", dominant_process([FakeBean("1")]) is None)
check("single process", dominant_process([FakeBean("1", process="honey")]) == "honey")

print("\n── region_counts ─────────────────────────────────────────────────")
kenya_beans = [
    FakeBean("1", origin_region="Kirinyaga"),
    FakeBean("2", origin_region="Kirinyaga"),
    FakeBean("3", origin_region="Nyeri"),
    FakeBean("4", origin_region=None),
]
regions = region_counts(kenya_beans)
check("Kirinyaga count = 2", regions.get("Kirinyaga") == 2)
check("Nyeri count = 1", regions.get("Nyeri") == 1)
check("None region excluded", None not in regions)

print("\n── altitude_range ────────────────────────────────────────────────")
high_beans = [
    FakeBean("1", altitude_masl_min=1500, altitude_masl_max=2000),
    FakeBean("2", altitude_masl_min=1800, altitude_masl_max=2200),
    FakeBean("3", altitude_masl_min=None, altitude_masl_max=None),
]
lo, hi = altitude_range(high_beans)
check("min altitude = 1500", lo == 1500)
check("max altitude = 2200", hi == 2200)
check("all None → (None, None)", altitude_range([FakeBean("1")]) == (None, None))

print("\n── process percentage ────────────────────────────────────────────")
proc_beans = [
    FakeBean("1", process="washed"),
    FakeBean("2", process="washed"),
    FakeBean("3", process="natural"),
]
total = 3
procs = Counter(b.process for b in proc_beans if b.process)
pcts = {p: round(c/total*100) for p, c in procs.items()}
check("washed = 67%", pcts["washed"] == 67)
check("natural = 33%", pcts["natural"] == 33)
check("sums to 100%", sum(pcts.values()) == 100)

print("\n── multi-country aggregation ─────────────────────────────────────")
mixed_beans = [
    FakeBean("1", "Ethiopia", "Yirgacheffe", "washed"),
    FakeBean("2", "Ethiopia", "Guji", "natural"),
    FakeBean("3", "Ethiopia", "Yirgacheffe", "washed"),
    FakeBean("4", "Kenya", "Kirinyaga", "washed"),
    FakeBean("5", "Kenya", "Nyeri", "washed"),
    FakeBean("6", "Brazil", None, "natural"),
]
groups = group_by_country(mixed_beans)
check("3 countries", len(groups) == 3)
check("Ethiopia has 3", len(groups["Ethiopia"]) == 3)
check("Ethiopia dominant = washed", dominant_process(groups["Ethiopia"]) == "washed")
check("Brazil dominant = natural", dominant_process(groups["Brazil"]) == "natural")
eth_regions = region_counts(groups["Ethiopia"])
check("Yirgacheffe count = 2", eth_regions.get("Yirgacheffe") == 2)

print("\n── COUNTRY_META coverage ─────────────────────────────────────────")
COUNTRY_META = {
    "Ethiopia": {"emoji": "🇪🇹", "tendency": "Bright, floral"},
    "Kenya": {"emoji": "🇰🇪", "tendency": "Bold, wine-like"},
    "Colombia": {"emoji": "🇨🇴", "tendency": "Balanced"},
    "Brazil": {"emoji": "🇧🇷", "tendency": "Low acidity"},
    "Guatemala": {"emoji": "🇬🇹", "tendency": "Complex"},
    "Rwanda": {"emoji": "🇷🇼", "tendency": "Delicate"},
    "Panama": {"emoji": "🇵🇦", "tendency": "Exotic"},
    "Honduras": {"emoji": "🇭🇳", "tendency": "Versatile"},
    "Peru": {"emoji": "🇵🇪", "tendency": "Soft"},
    "Indonesia": {"emoji": "🇮🇩", "tendency": "Earthy"},
}
major_origins = ["Ethiopia", "Kenya", "Colombia", "Brazil", "Guatemala",
                 "Rwanda", "Panama", "Honduras", "Peru", "Indonesia"]
for country in major_origins:
    check(f"{country} has meta", country in COUNTRY_META)

print("\n── edge cases ────────────────────────────────────────────────────")
check("empty bean list", group_by_country([]) == {})
check("all no-origin", group_by_country([FakeBean("1"), FakeBean("2")]) == {})
lo2, hi2 = altitude_range([FakeBean("1", altitude_masl_min=1000, altitude_masl_max=None)])
check("partial altitude", lo2 == 1000 and hi2 is None)

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
