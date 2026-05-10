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
  const W = 340, H = 120, PAD = { t: 12, r: 8, b: 26, l: 40 };
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
            <text x={PAD.l - 4} y={cy(t)} textAnchor="end" dominantBaseline="middle" fontSize="8" fill="var(--text-faint)">£{t.toFixed(0)}</text>
          </g>
        ))}
        <text x={PAD.l} y={H - 2} fontSize="8" fill="var(--text-faint)">{fmt(minDate)}</text>
        <text x={W - PAD.r} y={H - 2} fontSize="8" fill="var(--text-faint)" textAnchor="end">{fmt(maxDate)}</text>
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
      <div className="flex flex-wrap gap-3 mt-2">
        {series.map((v, i) => (
          <span key={v.variant_id} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-faint)" }}>
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
      <span className="w-28 flex-shrink-0 text-[11px] uppercase tracking-wider pt-0.5" style={{ color: "var(--text-faint)" }}>{label}</span>
      <span className="text-sm" style={{ color: "var(--text)" }}>{value}</span>
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
  return (
    <div className="space-y-2">
      {similar.map(s => (
        <Link key={s.bean_id} href={`/coffees/${s.bean_id}`}
          className="flex items-center gap-3 p-3 rounded-2xl press-active"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium leading-snug mb-1" style={{ fontFamily: "var(--font-display)", fontSize: "0.95rem" }}>
              {s.canonical_name}
            </div>
            <div className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>
              {[s.origin_country, s.process?.replace(/_/g, " ")].filter(Boolean).join(" · ")}
            </div>
            <div className="flex flex-wrap gap-1">
              {s.shared_families.map(f => (
                <span key={f} className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-faint)" }}>
                  {FAMILY_EMOJI[f] ?? ""} {f}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 flex-shrink-0">
            <span className="text-[11px] px-2 py-0.5 rounded-full"
              style={{ backgroundColor: "var(--accent-dim)", color: "var(--accent)" }}>
              {(s.similarity_score * 100).toFixed(0)}%
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: "var(--text-faint)" }}>
              <path d="M9 18l6-6-6-6" />
            </svg>
          </div>
        </Link>
      ))}
    </div>
  );
}

// ── FlavourChips ─────────────────────────────────────────────────────────────

function FlavourChips({ profile }: { profile: TasteProfile }) {
  if (!profile.has_structured_tags) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {profile.raw_notes.map(n => (
          <span key={n} className="text-[11px] px-2.5 py-1 rounded-full capitalize"
            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)", border: "1px solid var(--border-light)" }}>{n}</span>
        ))}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {profile.families.map(f => (
        <div key={f.family_slug}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: f.colour }} />
            <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>{f.family_label}</span>
          </div>
          <div className="flex flex-wrap gap-1 pl-4">
            {f.tags.map(t => (
              <span key={t.raw_note} className="text-[11px] px-2 py-0.5 rounded-full capitalize"
                style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)", border: "1px solid var(--border-light)" }}>
                {t.raw_note}
              </span>
            ))}
          </div>
        </div>
      ))}
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
            className="flex-1 py-3 text-[13px] font-medium transition-colors press-active"
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
      <div className="px-4 py-5">

        {/* ── Flavour ─────────────────────────────────────────────────────── */}
        {activeTab === "flavour" && (
          <div className="fade-in space-y-6">
            {/* Taste wheel */}
            <div className="rounded-2xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
              <div className="text-[10px] uppercase tracking-widest mb-3 text-center" style={{ color: "var(--text-faint)" }}>Flavour profile</div>
              {tasteWheelJsx}
            </div>

            {/* Chips */}
            {taste ? (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>Notes</div>
                <FlavourChips profile={taste} />
              </div>
            ) : c.flavour_notes.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>Tasting notes</div>
                <div className="flex flex-wrap gap-1.5">
                  {c.flavour_notes.map(n => (
                    <span key={n} className="text-[11px] px-2.5 py-1 rounded-full capitalize"
                      style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)", border: "1px solid var(--border-light)" }}>{n}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Similar coffees */}
            {similar.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>Similar taste profiles</div>
                <SimilarSection similar={similar} />
              </div>
            )}
          </div>
        )}

        {/* ── Prices ──────────────────────────────────────────────────────── */}
        {activeTab === "prices" && (
          <div className="fade-in space-y-5">
            {/* Summary stats */}
            {primary && (
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Lowest", value: primary.min_price_gbp },
                  { label: "Median", value: primary.median_price_gbp },
                  { label: "Best/100g", value: primary.min_per_100g },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-2xl p-3 text-center"
                    style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                    <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--text-faint)" }}>{label}</div>
                    <div className="text-xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                      {value != null ? `£${value.toFixed(2)}` : "—"}
                    </div>
                    {primary.weight_g && <div className="text-[10px] mt-0.5" style={{ color: "var(--text-faint)" }}>{primary.weight_g}g</div>}
                  </div>
                ))}
              </div>
            )}

            {/* Price per 100g comparison bars */}
            {history && history.variants.length > 0 && (
              <div className="rounded-2xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                <Per100gBars variants={history.variants} />
              </div>
            )}

            {/* Price history chart */}
            {history && history.variants.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>Price history</div>
                <div className="rounded-2xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                  <PriceHistoryChart history={history} />
                </div>
              </div>
            )}

            {/* Good value alternatives */}
            <GoodValueAlts coffeeId={c.id} maxPrice={primary?.min_price_gbp ?? null} />

            {(!history || history.variants.length === 0) && stats.length === 0 && (
              <div className="py-10 text-center">
                <div className="text-3xl mb-2">📊</div>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No price data yet</p>
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
                <div className="text-3xl mb-2">🗺</div>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>Provenance details unavailable</p>
              </div>
            )}
          </div>
        )}

        {/* ── Stores ──────────────────────────────────────────────────────── */}
        {activeTab === "stores" && (
          <div className="fade-in space-y-3">
            {c.listings && c.listings.length > 0 ? (
              <>
                <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--text-faint)" }}>
                  Available from {c.listings.length} {c.listings.length === 1 ? "store" : "stores"}
                </div>
                {c.listings.map((l, li) => (
                  <div key={l.id} className="rounded-2xl overflow-hidden"
                    style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                    {/* Store header */}
                    <div className="flex items-center justify-between px-4 py-3"
                      style={{ borderBottom: "1px solid var(--border-light)", backgroundColor: li % 2 === 0 ? "var(--bg-warm)" : "transparent" }}>
                      <div>
                        <div className="text-sm font-medium" style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}>
                          {l.store_name}
                        </div>
                        <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>{l.store_domain}</div>
                      </div>
                      {l.product_url && (
                        <a href={l.product_url} target="_blank" rel="noopener"
                          className="text-[11px] px-3 py-1.5 rounded-full press-active"
                          style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                          Buy ↗
                        </a>
                      )}
                    </div>

                    {/* Variants */}
                    {l.variants.map(v => (
                      <div key={v.id} className="flex items-center justify-between px-4 py-2.5"
                        style={{ borderBottom: "1px solid var(--border-light)", opacity: v.availability_status === "out_of_stock" ? 0.45 : 1 }}>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] px-2 py-0.5 rounded-full capitalize"
                            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}>
                            {v.grind_type.replace(/_/g, " ")}
                          </span>
                          {v.availability_status === "out_of_stock" && <span className="text-[10px] text-red-500">OOS</span>}
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span style={{ color: "var(--text-muted)" }}>
                            {v.weight_g ? (v.weight_g >= 1000 ? `${v.weight_g / 1000}kg` : `${v.weight_g}g`) : "—"}
                          </span>
                          <span className="font-medium" style={{ color: "var(--text)" }}>£{v.price_gbp.toFixed(2)}</span>
                          <span className="text-xs" style={{ color: "var(--accent)" }}>
                            {v.price_per_100g_gbp ? `£${v.price_per_100g_gbp.toFixed(2)}/100g` : ""}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
                <p className="text-[11px] pt-1" style={{ color: "var(--text-faint)" }}>
                  Prices updated daily. Always verify before purchasing.
                </p>
              </>
            ) : (
              <div className="py-10 text-center">
                <div className="text-3xl mb-2">🏪</div>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No store listings yet</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
