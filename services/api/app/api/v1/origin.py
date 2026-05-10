"""
origin.py — Origin Explorer API endpoints.

GET /api/v1/origins
  Returns all countries with coffees, with aggregate stats.

GET /api/v1/origins/{country}
  Returns full stats for one country: flavour families, processes,
  regions, price range, altitude range, and matching coffees.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.canonical_bean import CanonicalBean
from app.models.bean_listing import BeanListing
from app.models.pricing import ListingVariant
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.models.enums import ReviewStatus

router = APIRouter()

# ── Country metadata ──────────────────────────────────────────────────────────
# Hardcoded flavour tendency descriptions grounded in coffee science.
# Kept conservative — these describe tendencies, not guarantees.

COUNTRY_META: dict[str, dict] = {
    "Ethiopia": {
        "emoji": "🇪🇹",
        "tendency": "Bright, floral, and fruit-forward. Ethiopian coffees often show jasmine, bergamot, and stone fruit — especially from washed Yirgacheffe lots. Natural processing adds wild berry intensity.",
        "altitude_note": "High altitude (1,500–2,200m) slows cherry development, concentrating sugars and acids.",
        "notable_regions": ["Yirgacheffe", "Sidamo", "Guji", "Harrar"],
    },
    "Kenya": {
        "emoji": "🇰🇪",
        "tendency": "Bold, wine-like, and intensely fruity. SL28 and SL34 varietals give a distinctive blackcurrant and tomato acidity that divides coffee drinkers.",
        "altitude_note": "Grown at 1,400–2,000m. Central highlands around Kirinyaga and Nyeri produce the most celebrated lots.",
        "notable_regions": ["Kirinyaga", "Nyeri", "Murang'a", "Embu"],
    },
    "Colombia": {
        "emoji": "🇨🇴",
        "tendency": "Balanced and approachable. Colombian coffees are often medium-bodied with red fruit, caramel, and mild acidity — a reliable benchmark for washed Arabica.",
        "altitude_note": "Three mountain ranges (cordilleras) at 1,200–2,000m create diverse microclimates.",
        "notable_regions": ["Huila", "Nariño", "Cauca", "Antioquia"],
    },
    "Brazil": {
        "emoji": "🇧🇷",
        "tendency": "Low acidity, heavy body, chocolate and nut-forward. Brazil dominates espresso blend bases for good reason — it provides sweetness and body without sharp edges.",
        "altitude_note": "Lower altitude (800–1,200m) than East African origins, contributing to the smoother, less acidic profile.",
        "notable_regions": ["Minas Gerais", "São Paulo", "Bahia", "Espírito Santo"],
    },
    "Guatemala": {
        "emoji": "🇬🇹",
        "tendency": "Complex and varied. Guatemalan coffees often show dark chocolate, brown spice, and subtle fruit. Volcanic soil adds mineral depth.",
        "altitude_note": "Grown on volcanic slopes at 1,300–1,800m across eight distinct growing regions.",
        "notable_regions": ["Huehuetenango", "Antigua", "Atitlán", "Cobán"],
    },
    "Rwanda": {
        "emoji": "🇷🇼",
        "tendency": "Delicate and tea-like with bright acidity. Rwanda's best lots show hibiscus, peach, and honey — sometimes with a distinctive 'potato defect' that careful sorting eliminates.",
        "altitude_note": "High plateau at 1,500–2,000m. Thousands of smallholder farmers deliver to central washing stations.",
        "notable_regions": ["Nyamasheke", "Huye", "Rulindo"],
    },
    "Panama": {
        "emoji": "🇵🇦",
        "tendency": "Exotic and high-value. Panama is famous for Gesha/Geisha, which commands premium prices for its jasmine, peach, and bergamot complexity.",
        "altitude_note": "Boquete and Volcán regions sit on slopes of Barú volcano at 1,600–2,000m.",
        "notable_regions": ["Boquete", "Volcán", "Chiriquí"],
    },
    "Honduras": {
        "emoji": "🇭🇳",
        "tendency": "Underrated and versatile. Honduran coffees range from clean and mild to fruit-forward and syrupy depending on altitude and process.",
        "altitude_note": "Six coffee-growing regions at 1,000–1,600m. Quality has improved dramatically since the 2000s.",
        "notable_regions": ["Copán", "Montecillos", "Comayagua", "Agalta"],
    },
    "Peru": {
        "emoji": "🇵🇪",
        "tendency": "Soft and clean with mild acidity. Peruvian coffees often show gentle fruit and caramel — reliable but rarely exceptional, with some standout lots from high-altitude farms.",
        "altitude_note": "Grown in the Andes at 1,200–2,000m, often in remote areas with limited infrastructure.",
        "notable_regions": ["Cajamarca", "Puno", "Amazonas", "San Martín"],
    },
    "Indonesia": {
        "emoji": "🇮🇩",
        "tendency": "Earthy, full-bodied, and low-acid. The wet-hulling process (Giling Basah) gives Indonesian coffees their characteristic musty, forest-floor complexity.",
        "altitude_note": "Grown across multiple islands (Sumatra, Sulawesi, Flores) at 1,000–1,700m.",
        "notable_regions": ["Sumatra", "Sulawesi", "Flores", "Java"],
    },
    "India": {
        "emoji": "🇮🇳",
        "tendency": "Spicy and full-bodied with low acidity. Indian coffees often have a distinctive pepper and earthy character, particularly from the Malabar coast.",
        "altitude_note": "Grown in the Western Ghats and Nilgiri Hills at 600–1,500m under shade cover.",
        "notable_regions": ["Coorg", "Chikmagalur", "Nilgiris", "Malabar"],
    },
    "Yemen": {
        "emoji": "🇾🇪",
        "tendency": "Ancient, complex, and wine-like. Yemeni coffees are among the oldest cultivated Arabicas — wild and funky with chocolate, dried fruit, and spice.",
        "altitude_note": "Grown in terraced mountain gardens at 1,500–2,500m in one of the world's most challenging farming environments.",
        "notable_regions": ["Haraaz", "Bani Matar", "Ibb"],
    },
    "Costa Rica": {
        "emoji": "🇨🇷",
        "tendency": "Clean, bright, and sweet. Costa Rica pioneered honey processing, and its coffees often show brown sugar, apple, and citrus with exceptional clarity.",
        "altitude_note": "Central Valley and Tarrazú regions at 1,200–1,900m. Small micro-mill revolution improved quality dramatically.",
        "notable_regions": ["Tarrazú", "Central Valley", "Tres Ríos", "Brunca"],
    },
    "Bolivia": {
        "emoji": "🇧🇴",
        "tendency": "Delicate and complex with vibrant acidity. Bolivia produces excellent coffees at very high altitude but export infrastructure challenges mean they're rarely seen.",
        "altitude_note": "Some of the highest coffee farms in the world at 1,200–2,300m in the Yungas region.",
        "notable_regions": ["Yungas", "Caranavi"],
    },
    "Ecuador": {
        "emoji": "🇪🇨",
        "tendency": "Diverse and emerging. Ecuador produces both washed and natural coffees with floral and fruity profiles, increasingly seen in specialty markets.",
        "altitude_note": "Grown across multiple regions from 600–2,000m, including Galápagos island coffees.",
        "notable_regions": ["Loja", "Pichincha", "Carchi"],
    },
    "Burundi": {
        "emoji": "🇧🇮",
        "tendency": "Bright and juicy with complex fruit. Burundian coffees often rival Kenya for their black fruit intensity and tea-like delicacy.",
        "altitude_note": "Highland plateau at 1,200–2,000m. Washing stations process cherries from thousands of smallholder farmers.",
        "notable_regions": ["Kayanza", "Ngozi", "Kirundo"],
    },
    "Tanzania": {
        "emoji": "🇹🇿",
        "tendency": "Full-bodied with bright acidity and black fruit. Tanzanian peaberries are especially prized for their concentrated, round flavour.",
        "altitude_note": "Grown on the slopes of Kilimanjaro, Meru, and in the Southern Highlands at 1,400–2,000m.",
        "notable_regions": ["Kilimanjaro", "Mbeya", "Arusha", "Kigoma"],
    },
    "Uganda": {
        "emoji": "🇺🇬",
        "tendency": "Robust and full-bodied. Uganda produces both Arabica and Robusta — specialty Arabica from Mount Elgon shows fruit and floral notes.",
        "altitude_note": "Mount Elgon's slopes at 1,500–2,200m produce the best Ugandan Arabica.",
        "notable_regions": ["Mount Elgon", "Rwenzori", "Sipi Falls"],
    },
    "Nicaragua": {
        "emoji": "🇳🇮",
        "tendency": "Mild and balanced with caramel sweetness. Nicaraguan coffees are approachable and food-friendly — similar profile to Honduras but often with more body.",
        "altitude_note": "Northern highlands (Matagalpa, Jinotega) at 800–1,500m produce most of the country's specialty coffee.",
        "notable_regions": ["Matagalpa", "Jinotega", "Segovia"],
    },
    "Mexico": {
        "emoji": "🇲🇽",
        "tendency": "Light-bodied and nutty with mild acidity. Mexican coffees are often used in blends but high-altitude lots from Chiapas and Oaxaca can be exceptional.",
        "altitude_note": "Grown in southern states (Chiapas, Oaxaca, Veracruz) at 900–1,800m.",
        "notable_regions": ["Chiapas", "Oaxaca", "Veracruz", "Puebla"],
    },
    "El Salvador": {
        "emoji": "🇸🇻",
        "tendency": "Sweet and balanced with stone fruit and chocolate. El Salvador's Bourbon variety coffees have a distinctive round sweetness.",
        "altitude_note": "Grown at 500–1,500m. Santa Ana volcano region produces the most celebrated lots.",
        "notable_regions": ["Santa Ana", "Apaneca-Ilamatepec", "Metapán"],
    },
}


# ── Response models ───────────────────────────────────────────────────────────

class OriginSummary(BaseModel):
    country: str
    emoji: str
    coffee_count: int
    listing_count: int
    dominant_process: str | None
    avg_price_gbp: float | None
    top_flavour_families: list[dict]  # [{slug, label, colour, count}]
    regions: list[str]


class OriginDetail(BaseModel):
    country: str
    emoji: str
    tendency: str
    altitude_note: str
    notable_regions: list[str]
    coffee_count: int
    listing_count: int
    processes: list[dict]       # [{process, count, pct}]
    flavour_families: list[dict] # [{slug, label, colour, count, pct}]
    regions: list[dict]          # [{region, count}]
    price_min: float | None
    price_max: float | None
    price_avg: float | None
    altitude_min: int | None
    altitude_max: int | None
    coffees: list[dict]          # brief coffee list


class OriginsResponse(BaseModel):
    origins: list[OriginSummary]
    total_countries: int
    total_coffees: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ev(val) -> str | None:
    if val is None: return None
    return val.value if hasattr(val, "value") else str(val)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/origins", response_model=OriginsResponse)
async def list_origins(db: AsyncSession = Depends(get_db)) -> OriginsResponse:
    """Return all countries with coffees and aggregate stats."""

    # All beans with origin
    beans = (await db.execute(
        select(CanonicalBean).where(CanonicalBean.origin_country.isnot(None))
    )).scalars().all()

    if not beans:
        return OriginsResponse(origins=[], total_countries=0, total_coffees=0)

    bean_ids = [b.id for b in beans]

    # Listing counts per bean
    listing_counts = dict((await db.execute(
        select(BeanListing.canonical_bean_id, func.count(BeanListing.id))
        .where(BeanListing.canonical_bean_id.in_(bean_ids), BeanListing.active_flag.is_(True))
        .group_by(BeanListing.canonical_bean_id)
    )).all())

    # Average prices per bean
    avg_prices = dict((await db.execute(
        select(BeanListing.canonical_bean_id, func.avg(ListingVariant.price_gbp))
        .join(ListingVariant, ListingVariant.bean_listing_id == BeanListing.id)
        .where(BeanListing.canonical_bean_id.in_(bean_ids))
        .group_by(BeanListing.canonical_bean_id)
    )).all())

    # Flavour families per bean
    fam_rows = (await db.execute(
        select(BeanFlavourTag.bean_id, FlavourTaxonomy.slug, FlavourTaxonomy.label, FlavourTaxonomy.colour)
        .join(FlavourTaxonomy, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id.in_(bean_ids),
            BeanFlavourTag.review_status == ReviewStatus.accepted,
            FlavourTaxonomy.depth == 0,
        )
    )).all()

    bean_families: dict = {}
    for bid, slug, label, colour in fam_rows:
        bean_families.setdefault(str(bid), []).append((slug, label, colour or "#888"))

    # Group by country
    from collections import Counter, defaultdict
    country_beans: dict[str, list] = defaultdict(list)
    for b in beans:
        country_beans[b.origin_country].append(b)

    origins: list[OriginSummary] = []
    for country, cbeans in sorted(country_beans.items(), key=lambda x: x[0]):
        meta = COUNTRY_META.get(country, {})
        cbean_ids = [str(b.id) for b in cbeans]

        # Dominant process
        processes = Counter(_ev(b.process) for b in cbeans if b.process)
        dominant_process = processes.most_common(1)[0][0] if processes else None

        # Avg price
        prices = [float(avg_prices[b.id]) for b in cbeans if b.id in avg_prices and avg_prices[b.id]]
        avg_price = sum(prices) / len(prices) if prices else None

        # Top flavour families
        fam_counter: Counter = Counter()
        for bid in cbean_ids:
            for slug, label, colour in bean_families.get(bid, []):
                fam_counter[slug] += 1

        top_families = [
            {"slug": s, "label": next((l for sl,l,c in bean_families.get(cbean_ids[0],[]) if sl==s), s),
             "colour": "#888", "count": cnt}
            for s, cnt in fam_counter.most_common(4)
        ]

        # Regions
        regions = sorted({b.origin_region for b in cbeans if b.origin_region})

        total_listings = sum(listing_counts.get(b.id, 0) for b in cbeans)

        origins.append(OriginSummary(
            country=country,
            emoji=meta.get("emoji", "☕"),
            coffee_count=len(cbeans),
            listing_count=total_listings,
            dominant_process=dominant_process,
            avg_price_gbp=round(avg_price, 2) if avg_price else None,
            top_flavour_families=top_families[:4],
            regions=regions[:6],
        ))

    return OriginsResponse(
        origins=origins,
        total_countries=len(origins),
        total_coffees=len(beans),
    )


@router.get("/origins/{country}", response_model=OriginDetail)
async def get_origin(country: str, db: AsyncSession = Depends(get_db)) -> OriginDetail:
    """Return full stats for one origin country."""
    from urllib.parse import unquote
    country = unquote(country)

    beans = (await db.execute(
        select(CanonicalBean)
        .where(func.lower(CanonicalBean.origin_country) == country.lower())
    )).scalars().all()

    if not beans:
        raise HTTPException(status_code=404, detail=f"No coffees found for origin: {country}")

    meta = COUNTRY_META.get(country, COUNTRY_META.get(
        next((k for k in COUNTRY_META if k.lower() == country.lower()), ""), {}
    ))

    bean_ids = [b.id for b in beans]

    # Listings
    listing_rows = (await db.execute(
        select(BeanListing.canonical_bean_id, func.count(BeanListing.id))
        .where(BeanListing.canonical_bean_id.in_(bean_ids), BeanListing.active_flag.is_(True))
        .group_by(BeanListing.canonical_bean_id)
    )).all()
    listing_counts = dict(listing_rows)

    # Prices
    price_rows = (await db.execute(
        select(func.min(ListingVariant.price_gbp), func.max(ListingVariant.price_gbp), func.avg(ListingVariant.price_gbp))
        .join(BeanListing, BeanListing.id == ListingVariant.bean_listing_id)
        .where(BeanListing.canonical_bean_id.in_(bean_ids))
    )).one()
    price_min, price_max, price_avg = price_rows

    # Altitude range
    alt_rows = (await db.execute(
        select(func.min(CanonicalBean.altitude_masl_min), func.max(CanonicalBean.altitude_masl_max))
        .where(CanonicalBean.id.in_(bean_ids))
    )).one()

    # Processes
    from collections import Counter, defaultdict
    proc_counter: Counter = Counter()
    for b in beans:
        p = _ev(b.process)
        if p: proc_counter[p] += 1

    total_with_process = sum(proc_counter.values())
    processes = [
        {"process": p, "count": c, "pct": round(c / total_with_process * 100) if total_with_process else 0}
        for p, c in proc_counter.most_common()
    ]

    # Flavour families
    fam_rows = (await db.execute(
        select(FlavourTaxonomy.slug, FlavourTaxonomy.label, FlavourTaxonomy.colour,
               func.count(func.distinct(BeanFlavourTag.bean_id)))
        .join(BeanFlavourTag, BeanFlavourTag.taxonomy_id == FlavourTaxonomy.id)
        .where(
            BeanFlavourTag.bean_id.in_(bean_ids),
            BeanFlavourTag.review_status == ReviewStatus.accepted,
            FlavourTaxonomy.depth == 0,
        )
        .group_by(FlavourTaxonomy.slug, FlavourTaxonomy.label, FlavourTaxonomy.colour)
        .order_by(func.count(func.distinct(BeanFlavourTag.bean_id)).desc())
    )).all()

    total_tagged = len([b for b in beans if b.flavour_notes])
    flavour_families = [
        {"slug": s, "label": l, "colour": c or "#888",
         "count": cnt, "pct": round(cnt / max(len(beans), 1) * 100)}
        for s, l, c, cnt in fam_rows
    ]

    # Regions
    region_counter: Counter = Counter()
    for b in beans:
        if b.origin_region: region_counter[b.origin_region] += 1

    regions = [{"region": r, "count": c} for r, c in region_counter.most_common(8)]

    # Coffees list
    coffees = [
        {
            "id": str(b.id),
            "canonical_name": b.canonical_name,
            "origin_region": b.origin_region,
            "process": _ev(b.process),
            "roast_level": _ev(b.roast_level),
            "flavour_notes": (b.flavour_notes or [])[:4],
            "listing_count": listing_counts.get(b.id, 0),
        }
        for b in sorted(beans, key=lambda b: -(listing_counts.get(b.id, 0)))
    ]

    return OriginDetail(
        country=country,
        emoji=meta.get("emoji", "☕"),
        tendency=meta.get("tendency", ""),
        altitude_note=meta.get("altitude_note", ""),
        notable_regions=meta.get("notable_regions", []),
        coffee_count=len(beans),
        listing_count=sum(listing_counts.values()),
        processes=processes,
        flavour_families=flavour_families,
        regions=regions,
        price_min=float(price_min) if price_min else None,
        price_max=float(price_max) if price_max else None,
        price_avg=round(float(price_avg), 2) if price_avg else None,
        altitude_min=alt_rows[0],
        altitude_max=alt_rows[1],
        coffees=coffees,
    )
