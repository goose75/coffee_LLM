"use client";

/**
 * /coffees/compare — Coffee comparison page.
 *
 * Visual model: Sensory Ribbons
 *
 * Each dimension (roast, body, acidity, sweetness, complexity) is shown
 * as a horizontal lane. Each coffee gets a filled band within that lane,
 * positioned by its score. Coffees are colour-coded. The result reads
 * like a sheet of music — horizontal lines with marks at different positions —
 * making it immediately clear which coffee is brighter, heavier, darker.
 *
 * Flavour families use a mirrored bar approach: each family radiates outward
 * from a central axis, one direction per coffee. Overlap is shown as shared fill.
 *
 * This avoids the radar chart entirely. No angular geometry, no area encoding.
 * Every visual element maps directly to a readable fact.
 */

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { ExplanationBlurb } from "@/components/ExplanationBlurb";
import { useSearchParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Colour palette for compared coffees ───────────────────────────────────────
const COFFEE_COLOURS = ["#c4763a", "#6b9e8c", "#8b6bab"];
const COFFEE_BG = ["#c4763a22", "#6b9e8c22", "#8b6bab22"];

// ── Types ─────────────────────────────────────────────────────────────────────

interface FamilyMeta { slug: string; label: string; colour: string; }

interface CoffeeItem {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  farm_or_estate: string | null;
  process: string | null;
  roast_level: string | null;
  varietal: string[];
  harvest_year: number | null;
  altitude_masl_min: number | null;
  altitude_masl_max: number | null;
  decaf_flag: boolean;
  espresso_suitable_flag: boolean;
  filter_suitable_flag: boolean;
  flavour_notes: string[];
  data_completeness_score: number;
  min_price_gbp: number | null;
  price_per_100g_gbp: number | null;
  listing_count: number;
  sensory: Record<string, number>;
  family_weights: Record<string, number>;
  family_meta: FamilyMeta[];
}

interface CompareResponse {
  coffees: CoffeeItem[];
  contrast: string;
  shared_notes: string[];
  family_slugs: string[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function shortName(name: string) {
  return name.split(",")[0].trim();
}

function capFirst(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ComparePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const idsParam = searchParams.get("ids") ?? "";

  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!idsParam) return;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/v1/coffees/compare-multi?ids=${encodeURIComponent(idsParam)}`)
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then((d: CompareResponse) => { setData(d); setLoading(false); })
      .catch((e) => { setError(`Failed to load comparison: ${e.message}`); setLoading(false); });
  }, [idsParam]);

  if (!idsParam) return <NoSelection />;
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  const coffees = data.coffees;

  return (
    <div className="cmp-root">
      {/* Header */}
      <header className="cmp-header">
        <div className="cmp-header-inner">
          <Link href="/coffees" className="cmp-back">← Browse</Link>
          <p className="cmp-eyebrow">Comparison</p>
          <h1 className="cmp-title">
            {coffees.map((c, i) => (
              <span key={c.id}>
                {i > 0 && <span className="cmp-title-sep"> vs </span>}
                <span style={{ color: COFFEE_COLOURS[i] }}>{shortName(c.canonical_name)}</span>
              </span>
            ))}
          </h1>
        </div>
      </header>

      {/* Contrast summary */}
      {data.contrast && (
        <div className="cmp-contrast">
          <p className="cmp-contrast-text">{data.contrast}</p>
          {data.shared_notes.length > 0 && (
            <p className="cmp-shared">
              Shared: {data.shared_notes.join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Grounded comparison explanation */}
      <div className="cmp-explanation">
        <ExplanationBlurb
          type="compare"
          params={{ ids: coffees.map((c) => c.id).join(",") }}
        />
      </div>

      {/* Legend */}
      <div className="cmp-legend">
        {coffees.map((c, i) => (
          <div key={c.id} className="cmp-legend-item">
            <span className="cmp-legend-dot" style={{ background: COFFEE_COLOURS[i] }} />
            <span className="cmp-legend-name">{shortName(c.canonical_name)}</span>
          </div>
        ))}
      </div>

      {/* ── Sensory ribbons & Flavour families (side by side) ── */}
      <div className="cmp-two-col">
        <section className="cmp-section">
          <h2 className="cmp-section-title">Sensory Profile</h2>
          <SensoryRibbons coffees={coffees} />
        </section>

        <section className="cmp-section">
          <h2 className="cmp-section-title">Flavour Families</h2>
          <FlavourFamilyBands coffees={coffees} />
        </section>
      </div>

      {/* ── Fact grid & Price (side by side) ── */}
      <div className="cmp-two-col">
        <section className="cmp-section">
          <h2 className="cmp-section-title">Details</h2>
          <FactGrid coffees={coffees} />
        </section>

        <section className="cmp-section">
          <h2 className="cmp-section-title">Price</h2>
          <PriceComparison coffees={coffees} />
        </section>
      </div>

      {/* ── Brew suitability & Coffee links (side by side) ── */}
      <div className="cmp-two-col">
        <section className="cmp-section">
          <h2 className="cmp-section-title">Brew Suitability</h2>
          <BrewSuitability coffees={coffees} />
        </section>

        <div>
          <h2 className="cmp-section-title">View Coffees</h2>
          <div className="cmp-links-vertical">
            {coffees.map((c, i) => (
              <Link key={c.id} href={`/coffees/${c.id}`} className="cmp-link"
                style={{ borderColor: COFFEE_COLOURS[i] + "44", color: COFFEE_COLOURS[i] }}>
                View {shortName(c.canonical_name)} →
              </Link>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{styles}</style>
    </div>
  );
}

// ── Sensory Ribbons ───────────────────────────────────────────────────────────

const DIMENSIONS = [
  { key: "roast",      label: "Roast",      low: "Light",    high: "Dark"    },
  { key: "body",       label: "Body",       low: "Delicate", high: "Full"    },
  { key: "acidity",    label: "Acidity",    low: "Smooth",   high: "Bright"  },
  { key: "sweetness",  label: "Sweetness",  low: "Dry",      high: "Sweet"   },
  { key: "complexity", label: "Complexity", low: "Simple",   high: "Complex" },
];

function SensoryRibbons({ coffees }: { coffees: CoffeeItem[] }) {
  return (
    <div className="ribbons-wrap">
      {DIMENSIONS.map((dim) => (
        <div key={dim.key} className="ribbon-row">
          <span className="ribbon-label">{dim.label}</span>
          <div className="ribbon-track">
            <span className="ribbon-low">{dim.low}</span>
            <div className="ribbon-bar">
              {/* Tick marks */}
              {[0, 25, 50, 75, 100].map((pct) => (
                <div key={pct} className="ribbon-tick" style={{ left: `${pct}%` }} />
              ))}
              {/* Coffee markers */}
              {coffees.map((c, i) => {
                const score = c.sensory[dim.key] ?? 50;
                return (
                  <div
                    key={c.id}
                    className="ribbon-marker"
                    style={{
                      left: `${score}%`,
                      background: COFFEE_COLOURS[i],
                      transform: `translateX(-50%) translateY(${i * 6 - (coffees.length - 1) * 3}px)`,
                      zIndex: coffees.length - i,
                    }}
                    title={`${shortName(c.canonical_name)}: ${score}/100`}
                  />
                );
              })}
              {/* Connecting line between markers if 2 coffees */}
              {coffees.length === 2 && (() => {
                const s0 = coffees[0].sensory[dim.key] ?? 50;
                const s1 = coffees[1].sensory[dim.key] ?? 50;
                const left = Math.min(s0, s1);
                const width = Math.abs(s0 - s1);
                return (
                  <div
                    className="ribbon-span"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                    }}
                  />
                );
              })()}
            </div>
            <span className="ribbon-high">{dim.high}</span>
          </div>
          {/* Score labels */}
          <div className="ribbon-scores">
            {coffees.map((c, i) => (
              <span key={c.id} style={{ color: COFFEE_COLOURS[i] }}>
                {c.sensory[dim.key] ?? "—"}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Flavour Family Bands ──────────────────────────────────────────────────────

function FlavourFamilyBands({ coffees }: { coffees: CoffeeItem[] }) {
  const families = coffees[0]?.family_meta ?? [];
  const maxWeight = Math.max(
    1,
    ...coffees.flatMap((c) => Object.values(c.family_weights))
  );

  return (
    <div className="bands-wrap">
      {families.map((fam) => {
        const weights = coffees.map((c) => c.family_weights[fam.slug] ?? 0);
        const hasAny = weights.some((w) => w > 0);
        return (
          <div key={fam.slug} className={`band-row ${!hasAny ? "band-empty" : ""}`}>
            <span className="band-label" style={{ color: hasAny ? fam.colour : "var(--text-faint)" }}>
              {fam.label}
            </span>
            <div className="band-bars">
              {coffees.map((c, i) => {
                const w = c.family_weights[fam.slug] ?? 0;
                const pct = (w / maxWeight) * 100;
                return (
                  <div key={c.id} className="band-bar-wrap">
                    <div
                      className="band-bar-fill"
                      style={{
                        width: `${pct}%`,
                        background: pct > 0 ? COFFEE_COLOURS[i] : "transparent",
                        opacity: pct > 0 ? 1 : 0.15,
                      }}
                    />
                    <span className="band-bar-val" style={{ color: COFFEE_COLOURS[i] }}>
                      {w > 0 ? w : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Fact Grid ─────────────────────────────────────────────────────────────────

function FactGrid({ coffees }: { coffees: CoffeeItem[] }) {
  const rows = [
    { label: "Origin",   vals: coffees.map((c) => [c.origin_country, c.origin_region].filter(Boolean).join(", ") || "—") },
    { label: "Process",  vals: coffees.map((c) => capFirst(c.process ?? "") || "—") },
    { label: "Roast",    vals: coffees.map((c) => capFirst(c.roast_level ?? "") || "—") },
    { label: "Varietal", vals: coffees.map((c) => c.varietal.join(", ") || "—") },
    { label: "Harvest",  vals: coffees.map((c) => c.harvest_year?.toString() ?? "—") },
    { label: "Altitude", vals: coffees.map((c) =>
        c.altitude_masl_min ? `${c.altitude_masl_min}–${c.altitude_masl_max ?? "?"}m` : "—"
    )},
  ];

  return (
    <div className="fact-grid">
      {rows.map((row) => (
        <div key={row.label} className="fact-row">
          <span className="fact-label">{row.label}</span>
          {row.vals.map((v, i) => (
            <span key={i} className="fact-val" style={{ borderColor: COFFEE_COLOURS[i] + "33" }}>
              {v}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Price Comparison ──────────────────────────────────────────────────────────

function PriceComparison({ coffees }: { coffees: CoffeeItem[] }) {
  const maxP100g = Math.max(1, ...coffees.map((c) => c.price_per_100g_gbp ?? 0));

  return (
    <div className="price-wrap">
      {coffees.map((c, i) => (
        <div key={c.id} className="price-row">
          <span className="price-name" style={{ color: COFFEE_COLOURS[i] }}>
            {shortName(c.canonical_name)}
          </span>
          <div className="price-bar-wrap">
            <div
              className="price-bar"
              style={{
                width: `${((c.price_per_100g_gbp ?? 0) / maxP100g) * 100}%`,
                background: COFFEE_COLOURS[i],
              }}
            />
          </div>
          <span className="price-val">
            {c.price_per_100g_gbp
              ? `£${c.price_per_100g_gbp.toFixed(2)}/100g`
              : c.min_price_gbp
              ? `from £${c.min_price_gbp.toFixed(2)}`
              : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Brew Suitability ──────────────────────────────────────────────────────────

function BrewSuitability({ coffees }: { coffees: CoffeeItem[] }) {
  const methods = [
    { key: "espresso_suitable_flag", label: "Espresso", icon: "☕" },
    { key: "filter_suitable_flag",   label: "Filter",   icon: "🫗" },
  ];

  return (
    <div className="brew-grid">
      {methods.map((m) => (
        <div key={m.key} className="brew-row">
          <span className="brew-icon">{m.icon}</span>
          <span className="brew-label">{m.label}</span>
          {coffees.map((c, i) => {
            const ok = (c as unknown as Record<string, unknown>)[m.key] as boolean;
            return (
              <span
                key={c.id}
                className={`brew-badge ${ok ? "brew-yes" : "brew-no"}`}
                style={ok ? { background: COFFEE_COLOURS[i] + "22", color: COFFEE_COLOURS[i], borderColor: COFFEE_COLOURS[i] + "44" } : {}}
              >
                {ok ? "✓" : "—"}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── States ────────────────────────────────────────────────────────────────────

function NoSelection() {
  return (
    <div className="cmp-empty">
      <p className="cmp-empty-title">No coffees selected</p>
      <p>Add coffees to compare from the browse page or coffee detail pages.</p>
      <Link href="/coffees" className="cmp-empty-btn">Browse coffees</Link>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="cmp-loading">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="cmp-skeleton" style={{ animationDelay: `${i * 0.1}s` }} />
      ))}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="cmp-error">
      <p>{message}</p>
      <Link href="/coffees">← Back to browse</Link>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = `
  .cmp-root {
    min-height: 100vh;
    background: var(--bg);
    padding-bottom: 120px;
  }

  /* Header */
  .cmp-header {
    padding: 48px 32px 24px;
    max-width: 860px;
    margin: 0 auto;
  }
  .cmp-back {
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--text);
    text-decoration: none;
    letter-spacing: 0.06em;
    display: block;
    margin-bottom: 12px;
    transition: color 0.15s;
    font-weight: 500;
  }
  .cmp-back:hover { color: var(--accent); }
  .cmp-eyebrow {
    font-family: var(--font-body);
    font-size: 13px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 8px;
    font-weight: 600;
  }
  .cmp-title {
    font-family: var(--font-display);
    font-size: clamp(26px, 4.5vw, 48px);
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0;
    line-height: 1.2;
  }
  .cmp-title-sep { color: var(--text-faint); font-style: normal; }

  /* Contrast */
  .cmp-contrast {
    max-width: 860px;
    margin: 0 auto 8px;
    padding: 0 32px;
  }
  .cmp-explanation {
    max-width: 860px;
    margin: 8px auto 0;
    padding: 0 32px;
  }
  .cmp-contrast-text {
    font-family: var(--font-body);
    font-size: 16px;
    font-style: normal;
    font-weight: 500;
    color: var(--text);
    margin: 0 0 8px;
    line-height: 1.5;
  }
  .cmp-shared {
    font-family: var(--font-body);
    font-size: 16px;
    color: var(--text);
    margin: 0;
    font-weight: 500;
  }

  /* Legend */
  .cmp-legend {
    max-width: 860px;
    margin: 16px auto 0;
    padding: 0 32px;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
  }
  .cmp-legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-body);
    font-size: 16px;
    color: var(--text);
    font-weight: 500;
  }
  .cmp-legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
  }
  .cmp-legend-name { font-weight: 600; }

  /* Sections */
  .cmp-two-col {
    max-width: 1280px;
    margin: 32px auto 0;
    padding: 0 32px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
  }
  .cmp-section {
    max-width: 860px;
    margin: 32px auto 0;
    padding: 0 32px;
  }
  .cmp-two-col .cmp-section {
    max-width: none;
    margin: 0;
    padding: 0;
  }
  .cmp-section-title {
    font-family: var(--font-body);
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-light);
  }

  /* Sensory ribbons */
  .ribbons-wrap { display: flex; flex-direction: column; gap: 14px; }
  .ribbon-row {
    display: grid;
    grid-template-columns: 90px 1fr 60px;
    align-items: center;
    gap: 12px;
  }
  .ribbon-label {
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
    text-align: right;
  }
  .ribbon-track {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }
  .ribbon-low, .ribbon-high {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text);
    white-space: nowrap;
    width: 44px;
    flex-shrink: 0;
  }
  .ribbon-high { text-align: right; }
  .ribbon-bar {
    flex: 1;
    height: 24px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 4px;
    position: relative;
    overflow: visible;
  }
  .ribbon-tick {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--border-light);
    transform: translateX(-50%);
  }
  .ribbon-tick:first-child, .ribbon-tick:last-child { display: none; }
  .ribbon-marker {
    position: absolute;
    top: 50%;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid var(--bg);
    transform: translateX(-50%) translateY(-50%);
    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: default;
  }
  .ribbon-span {
    position: absolute;
    top: 50%;
    height: 3px;
    transform: translateY(-50%);
    background: var(--border-light);
    border-radius: 2px;
    pointer-events: none;
  }
  .ribbon-scores {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 700;
    min-width: 52px;
  }

  /* Flavour bands */
  .bands-wrap { display: flex; flex-direction: column; gap: 10px; }
  .band-row {
    display: grid;
    grid-template-columns: 90px 1fr;
    align-items: center;
    gap: 12px;
  }
  .band-empty { opacity: 0.4; }
  .band-label {
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 600;
    text-align: right;
  }
  .band-bars {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .band-bar-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 16px;
  }
  .band-bar-fill {
    height: 100%;
    border-radius: 3px;
    min-width: 2px;
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;
  }
  .band-bar-val {
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 700;
    min-width: 16px;
  }

  /* Fact grid */
  .fact-grid { display: flex; flex-direction: column; gap: 0; }
  .fact-row {
    display: grid;
    align-items: center;
    gap: 0;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-light);
  }
  .fact-row {
    grid-template-columns: 90px repeat(var(--coffee-count, 2), 1fr);
  }
  .fact-label {
    font-family: var(--font-body);
    font-size: 13px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--text-faint);
  }
  .fact-val {
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--text);
    padding: 4px 10px;
    border-left: 2px solid;
    margin-left: 8px;
  }

  /* Price */
  .price-wrap { display: flex; flex-direction: column; gap: 12px; }
  .price-row {
    display: grid;
    grid-template-columns: 160px 1fr 120px;
    align-items: center;
    gap: 12px;
  }
  .price-name {
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .price-bar-wrap {
    height: 8px;
    background: var(--surface-raised);
    border-radius: 4px;
    overflow: hidden;
  }
  .price-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 2px;
  }
  .price-val {
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    text-align: right;
    white-space: nowrap;
  }

  /* Brew suitability */
  .brew-grid { display: flex; flex-direction: column; gap: 10px; }
  .brew-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-light);
  }
  .brew-icon { font-size: 18px; width: 24px; }
  .brew-label {
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--text);
    width: 64px;
    font-weight: 500;
  }
  .brew-badge {
    padding: 6px 14px;
    border-radius: 100px;
    font-family: var(--font-body);
    font-size: 14px;
    font-weight: 700;
    border: 1px solid var(--border-light);
  }
  .brew-yes { }
  .brew-no { color: var(--text-faint); background: transparent; }

  /* Links */
  .cmp-links {
    max-width: 860px;
    margin: 32px auto 0;
    padding: 0 32px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .cmp-links-vertical {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .cmp-link {
    padding: 12px 24px;
    border-radius: 100px;
    border: 1.5px solid;
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 500;
    text-decoration: none;
    transition: opacity 0.15s;
  }
  .cmp-link:hover { opacity: 0.7; }

  /* States */
  .cmp-empty, .cmp-error {
    max-width: 480px;
    margin: 80px auto;
    padding: 0 32px;
    text-align: center;
    font-family: var(--font-body);
    color: var(--text-muted);
  }
  .cmp-empty-title {
    font-family: var(--font-display);
    font-size: 24px;
    font-style: italic;
    color: var(--text);
    margin-bottom: 12px;
  }
  .cmp-empty-btn {
    display: inline-block;
    margin-top: 20px;
    padding: 12px 28px;
    border-radius: 100px;
    border: 1px solid var(--border);
    color: var(--text);
    text-decoration: none;
    font-size: 15px;
    font-weight: 500;
    transition: border-color 0.15s, color 0.15s;
  }
  .cmp-empty-btn:hover { border-color: var(--accent); color: var(--accent); }
  .cmp-loading {
    max-width: 860px;
    margin: 48px auto;
    padding: 0 32px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .cmp-skeleton {
    height: 120px;
    border-radius: 12px;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @media (max-width: 600px) {
    .cmp-header, .cmp-contrast, .cmp-legend, .cmp-section, .cmp-links { padding: 0 20px; }
    .cmp-header { padding-top: 32px; }
    .cmp-two-col { grid-template-columns: 1fr; gap: 32px; padding: 0 20px; }
    .ribbon-row { grid-template-columns: 72px 1fr 44px; }
    .ribbon-low, .ribbon-high { display: none; }
    .band-row { grid-template-columns: 72px 1fr; }
    .fact-label { font-size: 12px; }
    .price-row { grid-template-columns: 120px 1fr 90px; }
  }
`;
