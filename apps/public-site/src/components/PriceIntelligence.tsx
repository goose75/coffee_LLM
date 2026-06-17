"use client";

/**
 * PriceIntelligence.tsx — Price visual components for Grounds.
 *
 * Components:
 *   PriceSparkline    — mini 40×20px SVG sparkline for browse cards
 *   Per100gBars       — horizontal comparison bars for price-per-100g across stores
 *   PriceHistoryChart — upgraded line chart with area fill, cleaner axes
 *   ValueBadge        — "Good value" / "Premium" badge derived from median comparison
 *   GoodValueAlts     — "Similar coffees for less" suggestions
 *
 * Design principles:
 *   - No red/green finance colouring — use accent palette only
 *   - Price-per-100g is the primary metric, not pack price
 *   - Empty states are calm, not alarming
 *   - Works in both light and dark mode via CSS variables
 */

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";



// ── Types ─────────────────────────────────────────────────────────────────────

export interface PricePoint {
  recorded_at: string;
  price_gbp: number;
  price_per_100g_gbp: number | null;
}

export interface VariantHistory {
  variant_id: string;
  store_name: string;
  store_domain: string;
  weight_g: number | null;
  history: PricePoint[];
  latest_price_gbp: number | null;
  latest_price_per_100g: number | null;
}

export interface BeanPriceHistory {
  variants: VariantHistory[];
  min_current_price_gbp: number | null;
  min_current_per_100g: number | null;
}

export interface PriceSummaryStats {
  weight_g: number | null;
  min_price_gbp: number | null;
  max_price_gbp: number | null;
  median_price_gbp: number | null;
  mean_price_gbp: number | null;
  min_per_100g: number | null;
}

interface AltCoffee {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  process: string | null;
  min_price_gbp: number | null;
  flavour_notes: string[];
}

// ── PriceSparkline ────────────────────────────────────────────────────────────

export function PriceSparkline({
  points,
  width = 48,
  height = 20,
  colour = "var(--accent)",
}: {
  points: number[];
  width?: number;
  height?: number;
  colour?: string;
}) {
  if (points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = 2;

  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (width - pad * 2));
  const ys = points.map((p) => pad + ((max - p) / range) * (height - pad * 2));

  const linePath = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");

  // Area fill path
  const areaPath = linePath
    + ` L${xs[xs.length - 1].toFixed(1)},${height - pad} L${xs[0].toFixed(1)},${height - pad} Z`;

  const lastX = xs[xs.length - 1];
  const lastY = ys[ys.length - 1];
  const trend = points[points.length - 1] - points[0];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ overflow: "visible" }}
      aria-label={`Price trend: ${trend >= 0 ? "up" : "down"}`}
    >
      <path d={areaPath} fill={colour} opacity="0.08" />
      <path d={linePath} fill="none" stroke={colour} strokeWidth="1.2" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="2" fill={colour} />
    </svg>
  );
}

// ── Per100gBars ───────────────────────────────────────────────────────────────

export function Per100gBars({ variants }: { variants: VariantHistory[] }) {
  const withPer100g = variants
    .filter((v) => v.latest_price_per_100g != null)
    .sort((a, b) => (a.latest_price_per_100g ?? 999) - (b.latest_price_per_100g ?? 999));

  if (withPer100g.length === 0) return (
    <p className="p100g-empty">Price-per-100g data not available for this coffee.</p>
  );

  const max = Math.max(...withPer100g.map((v) => v.latest_price_per_100g ?? 0), 1);
  const cheapest = withPer100g[0];

  return (
    <div className="p100g-root">
      <div className="p100g-title">Price per 100g</div>
      <div className="p100g-list">
        {withPer100g.map((v, i) => {
          const p100 = v.latest_price_per_100g ?? 0;
          const pct = (p100 / max) * 100;
          const isBest = i === 0;
          return (
            <div key={v.variant_id} className="p100g-row">
              <div className="p100g-store">
                <span className="p100g-store-name">{v.store_name}</span>
                {v.weight_g && <span className="p100g-weight">{v.weight_g}g</span>}
              </div>
              <div className="p100g-bar-wrap">
                <div
                  className="p100g-bar"
                  style={{
                    width: `${pct}%`,
                    background: isBest ? "var(--accent)" : "var(--border)",
                  }}
                />
              </div>
              <span className={`p100g-val ${isBest ? "p100g-best" : ""}`}>
                £{p100.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>
      {cheapest.latest_price_per_100g && (
        <p className="p100g-note">
          Best: {cheapest.store_name} at £{cheapest.latest_price_per_100g.toFixed(2)}/100g
          {cheapest.latest_price_gbp && ` · £${cheapest.latest_price_gbp.toFixed(2)} per pack`}
        </p>
      )}
      <style jsx>{p100gStyles}</style>
    </div>
  );
}

// ── PriceHistoryChart (upgraded) ─────────────────────────────────────────────

export function PriceHistoryChart({ history }: { history: BeanPriceHistory }) {
  const W = 340, H = 110;
  const PAD = { t: 10, r: 12, b: 28, l: 36 };

  // Prefer 250g variants for the chart — most representative
  const series250 = history.variants.filter((v) => v.weight_g != null && v.weight_g >= 200 && v.weight_g <= 300);
  const series = series250.length > 0 ? series250 : history.variants;

  const allPts = series.flatMap((v) => v.history.filter((p) => p.price_gbp > 0));
  if (allPts.length < 2) return (
    <div className="chart-empty">
      <p>Price history will appear here once this coffee has been tracked for a few days.</p>
    </div>
  );

  const dates = allPts.map((p) => new Date(p.recorded_at).getTime());
  const prices = allPts.map((p) => p.price_gbp);
  const minDate = Math.min(...dates), maxDate = Math.max(...dates);
  const minP = Math.min(...prices) * 0.95;
  const maxP = Math.max(...prices) * 1.05;

  const cx = (d: number) => PAD.l + ((d - minDate) / (maxDate - minDate || 1)) * (W - PAD.l - PAD.r);
  const cy = (p: number) => PAD.t + ((maxP - p) / (maxP - minP || 1)) * (H - PAD.t - PAD.b);

  const COLOURS = ["var(--accent)", "#6b9e8c", "#8b6bab", "#5a7fa8"];
  const fmt = (ts: number) => new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

  const yTicks = [minP, (minP + maxP) / 2, maxP];

  return (
    <div className="pricechart-root">
      <svg viewBox={`0 0 ${W} ${H}`} className="pricechart-svg" style={{ overflow: "visible" }}>
        {/* Grid lines */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.l} y1={cy(t)} x2={W - PAD.r} y2={cy(t)}
              stroke="var(--border-light)" strokeWidth="0.5"
              strokeDasharray={i === 0 ? "none" : "2 4"}
            />
            <text
              x={PAD.l - 5} y={cy(t)}
              textAnchor="end" dominantBaseline="middle"
              fontSize="8" fill="var(--text-faint)"
            >
              £{t.toFixed(t < 10 ? 1 : 0)}
            </text>
          </g>
        ))}

        {/* Date labels */}
        <text x={PAD.l} y={H - 4} fontSize="8" fill="var(--text-faint)">{fmt(minDate)}</text>
        <text x={W - PAD.r} y={H - 4} fontSize="8" fill="var(--text-faint)" textAnchor="end">{fmt(maxDate)}</text>

        {/* Series */}
        {series.map((v, i) => {
          const pts = v.history
            .filter((p) => p.price_gbp > 0)
            .sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
          if (pts.length < 2) return null;

          const colour = COLOURS[i % COLOURS.length];
          const linePath = pts
            .map((p, j) => {
              const x = cx(new Date(p.recorded_at).getTime());
              const y = cy(p.price_gbp);
              return `${j === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(" ");

          // Area fill
          const firstX = cx(new Date(pts[0].recorded_at).getTime());
          const lastX = cx(new Date(pts[pts.length - 1].recorded_at).getTime());
          const areaPath = `${linePath} L${lastX.toFixed(1)},${(H - PAD.b).toFixed(1)} L${firstX.toFixed(1)},${(H - PAD.b).toFixed(1)} Z`;

          const last = pts[pts.length - 1];

          return (
            <g key={v.variant_id}>
              <path d={areaPath} fill={colour} opacity="0.06" />
              <path d={linePath} fill="none" stroke={colour} strokeWidth="1.5" strokeLinejoin="round" />
              <circle
                cx={cx(new Date(last.recorded_at).getTime())}
                cy={cy(last.price_gbp)}
                r="3" fill={colour}
              />
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="pricechart-legend">
        {series.map((v, i) => (
          <span key={v.variant_id} className="pricechart-legend-item">
            <span className="pricechart-legend-dot" style={{ background: COLOURS[i % COLOURS.length] }} />
            <span>{v.store_name}{v.weight_g ? ` ${v.weight_g}g` : ""}</span>
            {v.latest_price_gbp && (
              <span className="pricechart-legend-price">£{v.latest_price_gbp.toFixed(2)}</span>
            )}
          </span>
        ))}
      </div>

      <style jsx>{chartStyles}</style>
    </div>
  );
}

// ── ValueBadge ────────────────────────────────────────────────────────────────

export function ValueBadge({ pricePerHundred, medianPerHundred }: {
  pricePerHundred: number | null;
  medianPerHundred: number | null;
}) {
  if (!pricePerHundred || !medianPerHundred) return null;

  const ratio = pricePerHundred / medianPerHundred;

  if (ratio <= 0.8) {
    return (
      <span className="value-badge value-badge-good" title={`£${pricePerHundred.toFixed(2)}/100g — below market average`}>
        Good value
      </span>
    );
  }
  if (ratio >= 1.4) {
    return (
      <span className="value-badge value-badge-premium" title={`£${pricePerHundred.toFixed(2)}/100g — above market average`}>
        Premium
      </span>
    );
  }
  return null;
}

// ── GoodValueAlts ─────────────────────────────────────────────────────────────

export function GoodValueAlts({ coffeeId, maxPrice }: { coffeeId: string; maxPrice: number | null }) {
  const [alts, setAlts] = useState<AltCoffee[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!maxPrice) { setLoading(false); return; }
    // Find coffees cheaper than this one, with similar flavour profile
    fetch(`/api/coffees?page_size=4&max_price=${(maxPrice * 0.8).toFixed(2)}`)
      .then((r) => r.json())
      .then((d) => {
        const filtered = (d.data ?? []).filter((c: AltCoffee) => c.id !== coffeeId).slice(0, 3);
        setAlts(filtered);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [coffeeId, maxPrice]);

  if (loading || alts.length === 0) return null;

  return (
    <div className="alts-root">
      <div className="alts-title">Similar coffees for less</div>
      <div className="alts-list">
        {alts.map((c) => (
          <Link key={c.id} href={`/coffees/${c.id}`} className="alts-row">
            <div className="alts-info">
              <span className="alts-name">{c.canonical_name}</span>
              {c.origin_country && <span className="alts-origin">{c.origin_country}</span>}
            </div>
            {c.min_price_gbp && (
              <span className="alts-price">from £{c.min_price_gbp.toFixed(2)}</span>
            )}
          </Link>
        ))}
      </div>
      <style jsx>{altsStyles}</style>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const p100gStyles = `
  .p100g-root { padding: 4px 0; }
  .p100g-title { font-family: var(--font-body); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 12px; }
  .p100g-list { display: flex; flex-direction: column; gap: 8px; }
  .p100g-row { display: grid; grid-template-columns: 140px 1fr 56px; align-items: center; gap: 8px; }
  .p100g-store { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .p100g-store-name { font-family: var(--font-body); font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .p100g-weight { font-family: var(--font-body); font-size: 10px; color: var(--text-faint); }
  .p100g-bar-wrap { height: 5px; background: var(--surface-raised); border-radius: 3px; overflow: hidden; }
  .p100g-bar { height: 100%; border-radius: 3px; min-width: 3px; transition: width 0.4s ease; }
  .p100g-val { font-family: var(--font-body); font-size: 12px; color: var(--text-faint); text-align: right; font-weight: 500; }
  .p100g-best { color: var(--accent) !important; }
  .p100g-note { font-family: var(--font-body); font-size: 11px; color: var(--text-faint); margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-light); }
  .p100g-empty { font-family: var(--font-body); font-size: 13px; color: var(--text-faint); text-align: center; padding: 24px 0; }
`;

const chartStyles = `
  .pricechart-root { }
  .pricechart-svg { width: 100%; display: block; }
  .pricechart-legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
  .pricechart-legend-item { display: flex; align-items: center; gap: 5px; font-family: var(--font-body); font-size: 11px; color: var(--text-faint); }
  .pricechart-legend-dot { width: 8px; height: 3px; border-radius: 2px; flex-shrink: 0; }
  .pricechart-legend-price { font-weight: 600; color: var(--text-muted); margin-left: 2px; }
  .chart-empty { padding: 20px 0; text-align: center; font-family: var(--font-body); font-size: 12px; color: var(--text-faint); line-height: 1.5; }
`;

const altsStyles = `
  .alts-root { border-top: 1px solid var(--border-light); padding-top: 16px; margin-top: 4px; }
  .alts-title { font-family: var(--font-body); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 10px; }
  .alts-list { display: flex; flex-direction: column; gap: 2px; }
  .alts-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 8px; border-radius: 8px; text-decoration: none; transition: background 0.15s; }
  .alts-row:hover { background: var(--surface-raised); }
  .alts-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .alts-name { font-family: var(--font-display); font-size: 14px; font-style: italic; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .alts-origin { font-family: var(--font-body); font-size: 10px; color: var(--text-faint); }
  .alts-price { font-family: var(--font-body); font-size: 12px; font-weight: 600; color: var(--accent); white-space: nowrap; flex-shrink: 0; }
`;
