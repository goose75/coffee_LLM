"""test_explain.py — Tests for the explanation service."""
from __future__ import annotations
import asyncio, hashlib, json, time

_CACHE: dict = {}
_CACHE_TTL_SECONDS = 3600

def _cache_key(t, data):
    payload = json.dumps({"type": t, "data": data}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

def _cache_get(key):
    entry = _CACHE.get(key)
    if entry and time.time() - entry[1] < _CACHE_TTL_SECONDS:
        return entry[0]
    return None

def _cache_set(key, value):
    _CACHE[key] = (value, time.time())

TEMPLATES = {
    "coffee_profile": "data:{data_json}\nWrite 1-2 sentences.",
    "coffee_compare": "data:{data_json}\nCompare these coffees.",
    "origin_character": "data:{data_json}\nDescribe this origin.",
    "roaster_style": "data:{data_json}\nDescribe this roaster.",
    "search_match": "data:{data_json}\nExplain the match.",
}

def build_coffee_profile_data(coffee):
    return {
        "canonical_name": coffee.get("canonical_name", ""),
        "origin_country": coffee.get("origin_country"),
        "process": coffee.get("process"),
        "roast_level": coffee.get("roast_level"),
        "flavour_notes": (coffee.get("flavour_notes") or [])[:6],
        "altitude_masl_min": coffee.get("altitude_masl_min"),
        "espresso_suitable": coffee.get("espresso_suitable_flag", False),
        "filter_suitable": coffee.get("filter_suitable_flag", False),
        "varietal": (coffee.get("varietal") or [])[:2],
    }

def build_compare_data(coffees):
    return {"coffees": [
        {"canonical_name": c.get("canonical_name",""), "origin_country": c.get("origin_country"),
         "process": c.get("process"), "roast_level": c.get("roast_level"),
         "flavour_notes": (c.get("flavour_notes") or [])[:4]}
        for c in coffees[:3]
    ]}

def build_origin_data(origin):
    return {
        "country": origin.get("country",""),
        "coffee_count": origin.get("coffee_count",0),
        "dominant_process": (origin.get("processes") or [{"process":None}])[0].get("process"),
        "top_flavour_families": [f.get("label","") for f in (origin.get("flavour_families") or [])[:3]],
        "altitude_range": (
            f"{origin.get('altitude_min')}–{origin.get('altitude_max')}m"
            if origin.get("altitude_min") and origin.get("altitude_max") else None
        ),
    }

def build_roaster_data(fp):
    processes = fp.get("processes") or []
    roasts = fp.get("roast_levels") or []
    families = fp.get("flavour_families") or []
    origins = fp.get("origins") or []
    return {
        "name": fp.get("name",""),
        "coffee_count": fp.get("coffee_count",0),
        "dominant_process": processes[0].get("process") if processes else None,
        "dominant_roast": roasts[0].get("roast_level") if roasts else None,
        "top_flavour_families": [f.get("label","") for f in families[:3]],
        "top_origins": [o.get("country","") for o in origins[:3]],
    }

def _fallback_coffee_profile(data):
    notes = data.get("flavour_notes", [])
    process = data.get("process","")
    roast = (data.get("roast_level","") or "").replace("_"," ")
    origin = data.get("origin_country","")
    parts = []
    if notes:
        parts.append("Expect " + ", ".join(notes[:3]).lower() + " notes")
    if process == "washed" and roast in ("light","medium light"):
        parts.append("suits those who prefer clarity and brightness")
    elif process == "natural":
        parts.append("suits those who enjoy fruit-forward cups")
    elif roast in ("dark","medium dark"):
        parts.append("suits those who prefer body and intensity")
    if origin:
        parts.append("from " + origin)
    return ". ".join(parts[:2]) + "." if parts else "Tasting notes are being added."

def _fallback_coffee_compare(data):
    coffees = data.get("coffees",[])
    if len(coffees) < 2: return ""
    a, b = coffees[0], coffees[1]
    a_name = a.get("canonical_name","Coffee A").split(",")[0]
    b_name = b.get("canonical_name","Coffee B").split(",")[0]
    a_roast = (a.get("roast_level") or "").replace("_"," ")
    b_roast = (b.get("roast_level") or "").replace("_"," ")
    if a_roast and b_roast and a_roast != b_roast:
        return f"{a_name} is {a_roast} roasted while {b_name} is {b_roast}."
    return f"{a_name} and {b_name} share a similar profile but differ in origin character."

def _fallback_roaster(data):
    name = data.get("name","This roaster")
    process = data.get("dominant_process","")
    roast = (data.get("dominant_roast","") or "").replace("_"," ")
    families = data.get("top_flavour_families",[])
    parts = [name]
    if process and roast:
        parts.append(f"tends toward {process}-process, {roast}-roasted coffees")
    elif process:
        parts.append(f"specialises in {process}-process coffees")
    if families:
        parts.append(f"with {families[0].lower()} character")
    return " ".join(parts) + "." if len(parts) > 1 else "Roaster profile is being built."

_FALLBACKS = {
    "coffee_profile": _fallback_coffee_profile,
    "coffee_compare": _fallback_coffee_compare,
    "roaster_style": _fallback_roaster,
}

async def explain(explanation_type, data, api_key=""):
    if explanation_type not in TEMPLATES: return ""
    key = _cache_key(explanation_type, data)
    cached = _cache_get(key)
    if cached: return cached
    fallback_fn = _FALLBACKS.get(explanation_type)
    result = fallback_fn(data) if fallback_fn else ""
    if result: _cache_set(key, result)
    return result

# ── Tests ──────────────────────────────────────────────────────────────────────
TOTAL=0; PASSED=0

def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED
    TOTAL += 1
    if condition:
        print(f"  ✓ {name}"); PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None: print(f"      got={got!r} expected={expected!r}")

print("\n── build_coffee_profile_data ─────────────────────────────────────")
coffee = {"canonical_name":"Ethiopia Yirgacheffe","origin_country":"Ethiopia",
          "process":"washed","roast_level":"light",
          "flavour_notes":["jasmine","lemon","bergamot","peach","plum","cherry","vanilla"],
          "altitude_masl_min":1800,"espresso_suitable_flag":False,
          "filter_suitable_flag":True,"varietal":["Heirloom","Gesha","Bourbon"]}
d = build_coffee_profile_data(coffee)
check("name preserved", d["canonical_name"] == "Ethiopia Yirgacheffe")
check("flavour_notes capped at 6", len(d["flavour_notes"]) == 6)
check("varietal capped at 2", len(d["varietal"]) == 2)
check("no extra fields", "harvest_year" not in d)
check("process included", d["process"] == "washed")

print("\n── build_compare_data ────────────────────────────────────────────")
coffees = [
    {"canonical_name":"A","process":"washed","roast_level":"light",
     "flavour_notes":["jasmine","lemon"],"origin_country":"Ethiopia"},
    {"canonical_name":"B","process":"natural","roast_level":"dark",
     "flavour_notes":["chocolate","caramel"],"origin_country":"Brazil"},
    {"canonical_name":"C","process":"honey","roast_level":"medium",
     "flavour_notes":["cherry"],"origin_country":"Colombia"},
    {"canonical_name":"D"},
]
d = build_compare_data(coffees)
check("capped at 3 coffees", len(d["coffees"]) == 3)
check("D excluded", all(c["canonical_name"] != "D" for c in d["coffees"]))
check("notes preserved", d["coffees"][0]["flavour_notes"] == ["jasmine","lemon"])

print("\n── build_origin_data ─────────────────────────────────────────────")
origin = {"country":"Ethiopia","coffee_count":15,
          "processes":[{"process":"washed","pct":70},{"process":"natural","pct":30}],
          "flavour_families":[{"label":"Fruity","count":10},{"label":"Floral","count":6}],
          "altitude_min":1600,"altitude_max":2200}
d = build_origin_data(origin)
check("country preserved", d["country"] == "Ethiopia")
check("dominant_process=washed", d["dominant_process"] == "washed")
check("top families extracted", d["top_flavour_families"] == ["Fruity","Floral"])
check("altitude_range formatted", d["altitude_range"] == "1600–2200m")

print("\n── build_roaster_data ────────────────────────────────────────────")
fp = {"name":"Darkwoods","coffee_count":20,
      "processes":[{"process":"natural","pct":57},{"process":"washed","pct":43}],
      "roast_levels":[{"roast_level":"light","pct":60},{"roast_level":"medium","pct":40}],
      "flavour_families":[{"label":"Fruity","count":15},{"label":"Floral","count":5}],
      "origins":[{"country":"Colombia","count":5},{"country":"Ethiopia","count":4}]}
d = build_roaster_data(fp)
check("name preserved", d["name"] == "Darkwoods")
check("dominant_process=natural", d["dominant_process"] == "natural")
check("dominant_roast=light", d["dominant_roast"] == "light")
check("top families", d["top_flavour_families"] == ["Fruity","Floral"])
check("top origins ≤3", len(d["top_origins"]) <= 3)

print("\n── fallback_coffee_profile ───────────────────────────────────────")
d = build_coffee_profile_data({"canonical_name":"Test","origin_country":"Ethiopia",
    "process":"washed","roast_level":"light","flavour_notes":["jasmine","lemon"]})
r = _fallback_coffee_profile(d)
check("non-empty result", len(r) > 0)
check("ends with period", r.endswith("."))
check("contains jasmine", "jasmine" in r.lower())

r2 = _fallback_coffee_profile(build_coffee_profile_data({"canonical_name":"Test"}))
check("no-data fallback safe", isinstance(r2, str) and len(r2) > 0)

print("\n── fallback_coffee_compare ───────────────────────────────────────")
d = build_compare_data([
    {"canonical_name":"Light Eth","roast_level":"light","process":"washed","origin_country":"Ethiopia","flavour_notes":[]},
    {"canonical_name":"Dark Brazil","roast_level":"dark","process":"natural","origin_country":"Brazil","flavour_notes":[]},
])
r = _fallback_coffee_compare(d)
check("mentions both names", "Light Eth" in r and "Dark Brazil" in r)
check("mentions roast diff", "light" in r.lower() or "dark" in r.lower())
check("single coffee empty", _fallback_coffee_compare({"coffees":[{"canonical_name":"A"}]}) == "")

print("\n── fallback_roaster ──────────────────────────────────────────────")
r = _fallback_roaster({"name":"Rave","dominant_process":"washed","dominant_roast":"light",
                        "top_flavour_families":["Fruity"],"top_origins":[]})
check("mentions Rave", "Rave" in r)
check("mentions washed", "washed" in r.lower())
check("ends with period", r.endswith("."))

print("\n── caching ───────────────────────────────────────────────────────")
data1 = {"canonical_name":"Test","flavour_notes":["cherry"]}
key1 = _cache_key("coffee_profile", data1)
check("cache miss initially", _cache_get(key1) is None)
_cache_set(key1, "Test explanation.")
check("cache hit after set", _cache_get(key1) == "Test explanation.")
data2 = {"canonical_name":"Different","flavour_notes":["lemon"]}
key2 = _cache_key("coffee_profile", data2)
check("different data = different key", key1 != key2)
check("different key is cache miss", _cache_get(key2) is None)

print("\n── explain async (no API key) ────────────────────────────────────")
data = build_coffee_profile_data({"canonical_name":"Kenya AA","origin_country":"Kenya",
    "process":"washed","roast_level":"light","flavour_notes":["blackcurrant","lemon"]})
result = asyncio.run(explain("coffee_profile", data, api_key=""))
check("returns string without API key", isinstance(result, str) and len(result) > 0)
check("result ends with period", result.endswith("."))
result2 = asyncio.run(explain("unknown_type", {}, api_key=""))
check("unknown type returns empty", result2 == "")

print("\n── prompt template completeness ──────────────────────────────────")
for t in ["coffee_profile","coffee_compare","origin_character","roaster_style","search_match"]:
    check(f"template exists: {t}", t in TEMPLATES)
    check(f"has data_json placeholder: {t}", "{data_json}" in TEMPLATES[t])

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
