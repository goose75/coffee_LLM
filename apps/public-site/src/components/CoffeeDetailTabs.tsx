"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import type {
  Coffee, BeanPriceHistory, PriceSummaryStats,
  TasteProfile, SimilarCoffee
} from "@/lib/api";
import { Per100gBars, PriceHistoryChart, GoodValueAlts } from "@/components/PriceIntelligence";

// ── SVG Price Chart ─────────────────────────────────────────────────────────

function PriceLineChart({ history }: { history: BeanPriceHistory }) {
  const W = 500, H = 240, PAD = { t: 16, r: 12, b: 36, l: 56 };
  const all250 = history.variants.filter(v => v.weight_g != null && v.weight_g >= 200 && v.weight_g <= 300);
  const series = all250.length > 0 ? all250 : history.variants;
  if (series.length === 0) return null;
  const allPts = series.flatMap(v => v.history);
  if (allPts.length < 2) return null;
  const dates = allPts.map(p => new Date(p.recorded_at).getTime());
  const prices = allPts.map(p => p.price_gbp);
  const minDate = Math.min(...dates), maxDate = Math.max(...dates);
  const minP = Math.min(...prices) * 0.97, maxP = Math.max(...prices) * 1.03;
  const cx = (d: number) => PAD.l + ((d - minDate) / (maxDate - minDate || 1)) * (W - PAD.l - PAD.r);
  const cy = (p: number) => PAD.t + ((maxP - p) / (maxP - minP || 1)) * (H - PAD.t - PAD.b);
  const palette = ["var(--accent)", "#6b9e8c", "#8b6bab", "#5a7fa8", "#c4763a"];
  const yTicks = [minP, (minP + maxP) / 2, maxP];
  const fmt = (ts: number) => new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H, overflow: "visible" }}>
        {yTicks.map(t => (
          <g key={t}>
            <line x1={PAD.l} y1={cy(t)} x2={W - PAD.r} y2={cy(t)} stroke="var(--border-light)" strokeWidth="0.5" />
            <text x={PAD.l - 4} y={cy(t)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="var(--text)">£{t.toFixed(0)}</text>
          </g>
        ))}
        <text x={PAD.l} y={H - 2} fontSize="11" fill="var(--text)">{fmt(minDate)}</text>
        <text x={W - PAD.r} y={H - 2} fontSize="11" fill="var(--text)" textAnchor="end">{fmt(maxDate)}</text>
        {series.map((v, i) => {
          const pts = v.history.filter(p => p.price_gbp > 0).sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
          if (pts.length < 2) return null;
          const d = pts.map((p, j) => { const x = cx(new Date(p.recorded_at).getTime()), y = cy(p.price_gbp); return `${j === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`; }).join(" ");
          const col = palette[i % palette.length];
          const last = pts[pts.length - 1];
          return (
            <g key={v.variant_id}>
              <path d={d} fill="none" stroke={col} strokeWidth="1.5" strokeLinejoin="round" />
              <circle cx={cx(new Date(last.recorded_at).getTime())} cy={cy(last.price_gbp)} r="3" fill={col} />
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-3 mt-4">
        {series.map((v, i) => (
          <span key={v.variant_id} className="flex items-center gap-1.5 text-base" style={{ color: "var(--text)" }}>
            <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: palette[i % palette.length] }} />
            {v.store_name}{v.weight_g ? ` ${v.weight_g}g` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Provenance row ──────────────────────────────────────────────────────────

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-4 py-3" style={{ borderBottom: "1px solid var(--border-light)" }}>
      <span className="w-32 flex-shrink-0 text-sm uppercase tracking-wider pt-0.5 font-semibold" style={{ color: "var(--text-faint)" }}>{label}</span>
      <span className="text-base" style={{ color: "var(--text)" }}>{value}</span>
    </div>
  );
}

// ── Similar coffees ──────────────────────────────────────────────────────────

const FAMILY_EMOJI: Record<string, string> = {
  fruity: "🍋", floral: "🌸", sweet: "🍯", chocolate: "🍫",
  nutty: "🌰", spice: "🌶", earthy: "🌿", fermented: "🍷",
};

function SimilarSection({ similar }: { similar: SimilarCoffee[] }) {
  if (!similar.length) return null;

  // Group coffees by shared flavor families
  const groupedBySimilarity = similar.reduce((acc, coffee) => {
    const key = coffee.shared_families.sort().join(',');
    if (!acc[key]) {
      acc[key] = { families: coffee.shared_families, coffees: [] };
    }
    acc[key].coffees.push(coffee);
    return acc;
  }, {} as Record<string, { families: string[]; coffees: SimilarCoffee[] }>);

  return (
    <div className="space-y-8">
      {Object.entries(groupedBySimilarity).map(([familiesKey, { families, coffees }]) => (
        <div key={familiesKey}>
          {/* Shared flavor families header */}
          <div className="flex flex-wrap gap-2.5 mb-5">
            {families.map(f => (
              <span key={f} className="text-base px-3 py-1.5 rounded"
                style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)" }}>
                {FAMILY_EMOJI[f] ?? ""} {f}
              </span>
            ))}
          </div>

          {/* Coffees grouped under these families */}
          <div className="space-y-3">
            {coffees.map(s => (
              <Link key={s.bean_id} href={`/coffees/${s.bean_id}`}
                className="flex items-start gap-4 p-4 rounded-xl press-active"
                style={{ backgroundColor: "var(--bg-warm)", border: "1px solid var(--border-light)" }}>
                <div className="flex-1 min-w-0">
                  <div className="text-lg mb-1" style={{ color: "var(--text)" }}>
                    {[s.origin_country, s.process?.replace(/_/g, " ")].filter(Boolean).join(" · ")}
                  </div>
                  <div className="text-base font-medium" style={{ fontFamily: "var(--font-display)", color: "var(--text)" }}>
                    {s.canonical_name}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <span className="text-base px-3 py-1.5 rounded-full font-semibold"
                    style={{ backgroundColor: "var(--accent-dim)", color: "var(--accent)" }}>
                    {(s.similarity_score * 100).toFixed(0)}%
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Flavour Intensity Bars ──────────────────────────────────────────────────

function FlavourBars({ profile }: { profile: TasteProfile }) {
  if (!profile.has_structured_tags) {
    return (
      <div className="flex flex-wrap gap-2">
        {profile.raw_notes.map(n => (
          <span key={n} className="text-sm px-3 py-1.5 rounded-full capitalize"
            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)", border: "1px solid var(--border-light)" }}>{n}</span>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {profile.families.map(f => {
        // Calculate intensity based on weight (0-1 scale)
        const intensity = Math.min(f.weight, 1);
        const intensityLabel = intensity >= 0.7 ? "Strong" : intensity >= 0.4 ? "Medium" : "Subtle";

        return (
          <div key={f.family_slug}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: f.colour }} />
                <span className="text-sm font-medium capitalize" style={{ color: "var(--text)" }}>{f.family_label}</span>
              </div>
              <span className="text-xs font-medium" style={{ color: "var(--text-faint)" }}>{intensityLabel}</span>
            </div>

            {/* Intensity bar */}
            <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-warm)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${intensity * 100}%`,
                  backgroundColor: f.colour,
                  opacity: 0.8,
                }}
              />
            </div>

            {/* Flavor notes under this family */}
            {f.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {f.tags.slice(0, 4).map(t => (
                  <span key={t.raw_note} className="text-sm px-2.5 py-1 rounded capitalize"
                    style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)" }}>
                    {t.raw_note}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Tab definitions ───────────────────────────────────────────────────────────

type TabId = "flavour" | "prices" | "provenance" | "stores";

const TABS: { id: TabId; label: string }[] = [
  { id: "flavour",    label: "Flavour" },
  { id: "prices",     label: "Prices" },
  { id: "provenance", label: "Origin" },
  { id: "stores",     label: "Stores" },
];

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  coffee: Coffee;
  history: BeanPriceHistory | null;
  stats: PriceSummaryStats[];
  taste: TasteProfile | null;
  similar: SimilarCoffee[];
  tasteWheelJsx: React.ReactNode;
}

export default function CoffeeDetailTabs({ coffee: c, history, stats, taste, similar, tasteWheelJsx }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("flavour");

  const primary = stats.find(s => s.weight_g === 250) ?? stats[0];

  return (
    <div>
      {/* Tab bar */}
      <div
        className="flex border-b sticky z-30"
        style={{
          top: 48,
          backgroundColor: "color-mix(in srgb, var(--bg) 90%, transparent)",
          backdropFilter: "blur(12px)",
          borderColor: "var(--border-light)",
        }}
      >
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="flex-1 py-3 text-base font-medium transition-colors press-active"
            style={{
              color: activeTab === tab.id ? "var(--accent)" : "var(--text-faint)",
              borderBottom: activeTab === tab.id ? "2px solid var(--accent)" : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="px-4 py-6">

        {/* ── Flavour ─────────────────────────────────────────────────────── */}
        {activeTab === "flavour" && (
          <div className="fade-in space-y-8">
            {/* Two-column: Flavour profile + About coffee */}
            <div className="flex gap-5">
              {/* Flavour intensity bars - Left column */}
              {taste ? (
                <div className="rounded-2xl p-5" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)", flex: "1 1 50%" }}>
                  <div className="text-sm uppercase tracking-wider mb-5 font-semibold" style={{ color: "var(--text)" }}>Flavor Profile</div>
                  <FlavourBars profile={taste} />
                </div>
              ) : c.flavour_notes.length > 0 && (
                <div style={{ flex: "1 1 50%" }}>
                  <div className="text-sm uppercase tracking-wider mb-4 font-semibold" style={{ color: "var(--text)" }}>Tasting Notes</div>
                  <div className="flex flex-wrap gap-2">
                    {c.flavour_notes.map(n => (
                      <span key={n} className="text-sm px-3 py-1.5 rounded-full capitalize"
                        style={{ backgroundColor: "var(--bg-warm)", color: "var(--text)", border: "1px solid var(--border-light)" }}>{n}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Flavor description - Right column */}
              {taste && taste.raw_notes.length > 0 && (
                <div className="rounded-2xl p-5" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)", flex: "1 1 50%" }}>
                  <div className="text-sm uppercase tracking-wider mb-3 font-semibold" style={{ color: "var(--text)" }}>About this coffee</div>
                  <p className="text-base leading-relaxed" style={{ color: "var(--text)" }}>
                    This coffee features {taste.raw_notes.slice(0, 3).join(", ")} characteristics.
                    {taste.families.length > 0 && ` The dominant flavor families are ${taste.families.slice(0, 2).map(f => f.family_label.toLowerCase()).join(" and ")}.`}
                    Best enjoyed with pour-over or espresso to fully appreciate the complex flavor profile.
                  </p>
                </div>
              )}
            </div>

            {/* Similar coffees - Full width below */}
            {similar.length > 0 && (
              <div>
                <div className="text-sm uppercase tracking-wider mb-4 font-semibold" style={{ color: "var(--text)" }}>Similar Taste Profiles</div>
                <SimilarSection similar={similar} />
              </div>
            )}
          </div>
        )}

        {/* ── Prices ──────────────────────────────────────────────────────── */}
        {activeTab === "prices" && (
          <div className="fade-in space-y-6">
            {/* Summary stats */}
            {primary && (
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Lowest", value: primary.min_price_gbp },
                  { label: "Median", value: primary.median_price_gbp },
                  { label: "Best/100g", value: primary.min_per_100g },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-2xl p-4 text-center"
                    style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                    <div className="text-xs uppercase tracking-widest mb-2 font-medium" style={{ color: "var(--text)" }}>{label}</div>
                    <div className="text-2xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                      {value != null ? `£${value.toFixed(2)}` : "—"}
                    </div>
                    {primary.weight_g && <div className="text-xs mt-1" style={{ color: "var(--text)" }}>{primary.weight_g}g</div>}
                  </div>
                ))}
              </div>
            )}

            {/* Price per 100g comparison bars */}
            {history && history.variants.length > 0 && (
              <div className="rounded-2xl p-5" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                <Per100gBars variants={history.variants} />
              </div>
            )}

            {/* Price history chart */}
            {history && history.variants.length > 0 && (
              <div>
                <div className="text-sm uppercase tracking-wider mb-4 font-semibold" style={{ color: "var(--text)" }}>Price History</div>
                <div className="rounded-2xl p-5" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                  <PriceLineChart history={history} />
                </div>
              </div>
            )}

            {/* Good value alternatives */}
            <GoodValueAlts coffeeId={c.id} maxPrice={primary?.min_price_gbp ?? null} />

            {(!history || history.variants.length === 0) && stats.length === 0 && (
              <div className="py-10 text-center">
                <div className="text-4xl mb-3">📊</div>
                <p className="text-base" style={{ color: "var(--text-muted)" }}>No price data yet</p>
              </div>
            )}
          </div>
        )}

        {/* ── Provenance ──────────────────────────────────────────────────── */}
        {activeTab === "provenance" && (
          <div className="fade-in">
            <Row label="Country" value={c.origin_country} />
            <Row label="Region" value={c.origin_region} />
            <Row label="Farm" value={c.farm_or_estate} />
            <Row label="Station" value={c.washing_station} />
            <Row label="Producer" value={c.producer} />
            <Row label="Varietal" value={c.varietal.length ? c.varietal.join(", ") : null} />
            <Row label="Process" value={c.process?.replace(/_/g, " ")} />
            <Row label="Roast" value={c.roast_level?.replace(/_/g, " ")} />
            <Row label="Harvest" value={c.harvest_year?.toString()} />
            <Row label="Altitude" value={c.altitude_masl_min != null ? `${c.altitude_masl_min}–${c.altitude_masl_max ?? "?"}m` : null} />

            {/* Empty state */}
            {!c.origin_country && !c.process && !c.roast_level && (
              <div className="py-10 text-center">
                <div className="text-4xl mb-3">🗺</div>
                <p className="text-base" style={{ color: "var(--text-muted)" }}>Provenance details unavailable</p>
              </div>
            )}
          </div>
        )}

        {/* ── Stores ──────────────────────────────────────────────────────── */}
        {activeTab === "stores" && (
          <div className="fade-in">
            {c.listings && c.listings.length > 0 ? (
              <>
                <div className="text-sm uppercase tracking-wider mb-4 font-semibold" style={{ color: "var(--text)" }}>
                  Available from {c.listings.length} {c.listings.length === 1 ? "store" : "stores"}
                </div>

                {/* Improved stores grid - WEIGHT-BASED COLUMNS */}
                <div className="space-y-5">
                  {/* Collect all unique weights across all stores */}
                  {(() => {
                    const allWeights = new Set<number>();
                    c.listings.forEach(l => {
                      l.variants.forEach(v => {
                        if (v.weight_g !== null) allWeights.add(v.weight_g);
                      });
                    });
                    const weights = Array.from(allWeights).sort((a, b) => a - b);

                    return (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr style={{ borderBottom: "2px solid var(--border-light)", backgroundColor: "var(--bg-warm)" }}>
                              <th className="px-4 py-3 text-left text-sm font-semibold" style={{ color: "var(--text-faint)" }}>Store</th>
                              {weights.map(w => (
                                <th key={w} className="px-3 py-3 text-center whitespace-nowrap text-sm font-semibold" style={{ color: "var(--text-faint)" }}>
                                  {w >= 1000 ? `${(w / 1000).toFixed(1)}kg` : `${w}g`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {c.listings.map((listing) => (
                              <tr key={listing.id} style={{ borderBottom: "1px solid var(--border-light)" }}>
                                <td className="px-4 py-3">
                                  <div className="text-sm font-medium" style={{ fontFamily: "var(--font-display)", color: "var(--text)" }}>
                                    {listing.store_name}
                                  </div>
                                  <div className="text-xs mt-0.5" style={{ color: "var(--text)" }}>
                                    {listing.store_domain}
                                  </div>
                                </td>
                                {weights.map(w => {
                                  // Find the best price for this weight at this store
                                  const variantsForWeight = listing.variants.filter(v => v.weight_g === w);
                                  const bestVariant = variantsForWeight.reduce((best, current) => {
                                    if (current.availability_status === "out_of_stock") return best;
                                    if (!best || current.price_gbp < best.price_gbp) return current;
                                    return best;
                                  }, variantsForWeight[0] || null);

                                  const isOutOfStock = bestVariant?.availability_status === "out_of_stock";

                                  if (!bestVariant) {
                                    return (
                                      <td key={w} className="px-3 py-3 text-center" style={{ color: "var(--text-faint)" }}>
                                        —
                                      </td>
                                    );
                                  }

                                  return (
                                    <td key={w} className="px-3 py-3 text-center" style={{ opacity: isOutOfStock ? 0.5 : 1 }}>
                                      <div className="text-sm font-medium" style={{ color: isOutOfStock ? "var(--text-faint)" : "var(--accent)" }}>
                                        £{bestVariant.price_gbp.toFixed(2)}
                                      </div>
                                      {bestVariant.price_per_100g_gbp && (
                                        <div className="text-xs mt-0.5" style={{ color: "var(--text)" }}>
                                          £{bestVariant.price_per_100g_gbp.toFixed(2)}/100g
                                        </div>
                                      )}
                                      {isOutOfStock ? (
                                        <div className="text-xs mt-1 font-medium" style={{ color: "var(--text-faint)" }}>Out of Stock</div>
                                      ) : (
                                        <div className="text-xs mt-1" style={{ color: "var(--accent)" }}>✓ In stock</div>
                                      )}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    );
                  })()}
                </div>

                {/* Buy buttons */}
                <div className="mt-6 space-y-2">
                  {c.listings.filter(l => l.product_url).map(l => (
                    <a key={l.id} href={l.product_url || undefined} target="_blank" rel="noopener"
                      className="block text-center text-sm px-4 py-2.5 rounded-lg press-active"
                      style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>
                      Shop at {l.store_name} ↗
                    </a>
                  ))}
                </div>

                <p className="text-xs pt-4 mt-4" style={{ color: "var(--text-faint)", borderTop: "1px solid var(--border-light)" }}>
                  Prices updated daily. Always verify availability and price before purchasing.
                </p>
              </>
            ) : (
              <div className="py-10 text-center">
                <div className="text-4xl mb-3">🏪</div>
                <p className="text-base" style={{ color: "var(--text-muted)" }}>No store listings yet</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
