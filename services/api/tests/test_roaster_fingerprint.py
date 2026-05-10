"""test_roaster_fingerprint.py — Tests for roaster fingerprint aggregation."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field

@dataclass
class FakeBean:
    id: str
    origin_country: str | None = None
    process: str | None = None
    roast_level: str | None = None
    flavour_notes: list[str] = field(default_factory=list)

PROCESS_COLOURS = {"washed":"#6b9e8c","natural":"#c4763a","honey":"#d4a84b","anaerobic":"#8b6bab"}

def dominant_process(beans):
    c = Counter(b.process for b in beans if b.process)
    return c.most_common(1)[0][0] if c else None

def process_stats(beans):
    c = Counter(b.process for b in beans if b.process)
    total = sum(c.values())
    return [{"process":p,"count":n,"pct":round(n/total*100)} for p,n in c.most_common()]

def origin_stats(beans):
    c = Counter(b.origin_country for b in beans if b.origin_country)
    total = sum(c.values())
    return [{"country":o,"count":n,"pct":round(n/total*100)} for o,n in c.most_common(8)]

def roast_stats(beans):
    c = Counter(b.roast_level for b in beans if b.roast_level)
    order = ["light","medium_light","medium","medium_dark","dark"]
    total = sum(c.values())
    return [{"roast_level":r,"count":c[r],"pct":round(c[r]/total*100)} for r in order if r in c]

def style_summary(top_families, top_process, dominant_roast, top_origins, avg_price):
    parts = []
    if top_process == "washed": parts.append("clean, washed-process coffees")
    elif top_process == "natural": parts.append("expressive natural-process coffees")
    if dominant_roast in ("light","medium_light"): parts.append("roasted light to preserve origin character")
    elif dominant_roast == "dark": parts.append("roasted darker for body and intensity")
    if top_origins: parts.append(f"sourced primarily from {top_origins[0]}" if len(top_origins)==1 else f"spanning {len(top_origins)} origins")
    if not parts: return "A specialty roaster with a diverse range of coffees."
    s = "This roaster tends toward " + ", ".join(parts[:3]) + "."
    return s[0].upper() + s[1:]

TOTAL = 0; PASSED = 0
def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED; TOTAL += 1
    if condition: print(f"  ✓ {name}"); PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None: print(f"      got={got!r} expected={expected!r}")

print("\n── process_stats ─────────────────────────────────────────────────")
beans = [FakeBean("1",process="washed"),FakeBean("2",process="washed"),FakeBean("3",process="natural")]
ps = process_stats(beans)
check("washed is first", ps[0]["process"] == "washed")
check("washed pct = 67", ps[0]["pct"] == 67)
check("natural pct = 33", ps[1]["pct"] == 33)
check("pcts sum to 100", sum(p["pct"] for p in ps) == 100)

print("\n── origin_stats ──────────────────────────────────────────────────")
beans = [FakeBean("1","Ethiopia"),FakeBean("2","Ethiopia"),FakeBean("3","Kenya"),FakeBean("4","Ethiopia")]
os_ = origin_stats(beans)
check("Ethiopia first", os_[0]["country"] == "Ethiopia")
check("Ethiopia count 3", os_[0]["count"] == 3)
check("Kenya count 1", os_[1]["count"] == 1)
check("pcts sum to 100", sum(o["pct"] for o in os_) == 100)

print("\n── roast_stats ───────────────────────────────────────────────────")
beans = [FakeBean("1",roast_level="light"),FakeBean("2",roast_level="light"),
         FakeBean("3",roast_level="medium"),FakeBean("4",roast_level=None)]
rs = roast_stats(beans)
check("light first", rs[0]["roast_level"] == "light")
check("light pct = 67", rs[0]["pct"] == 67)
check("medium pct = 33", rs[1]["pct"] == 33)
check("None excluded", len(rs) == 2)

print("\n── style_summary ─────────────────────────────────────────────────")
s = style_summary(["fruity","floral"],"washed","light",["Ethiopia","Kenya"],12.0)
check("mentions washed", "washed" in s)
check("mentions light", "light" in s)
check("starts uppercase", s[0].isupper())
check("ends period", s.endswith("."))

s2 = style_summary([],"natural","dark",["Brazil"],8.0)
check("natural mentioned", "natural" in s2)
check("dark mentioned", "dark" in s2)

s3 = style_summary([],None,None,[],None)
check("empty → default", "specialty roaster" in s3)

print("\n── dominant_process ──────────────────────────────────────────────")
check("washed dominant", dominant_process([FakeBean("1",process="washed"),FakeBean("2",process="washed"),FakeBean("3",process="natural")]) == "washed")
check("all None → None", dominant_process([FakeBean("1")]) is None)

print("\n── edge cases ────────────────────────────────────────────────────")
check("empty beans", process_stats([]) == [])
check("empty origins", origin_stats([]) == [])
check("empty roasts", roast_stats([]) == [])
check("single bean process", process_stats([FakeBean("1",process="honey")])[0]["pct"] == 100)

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
