"use client";

export const dynamic = "force-dynamic";

/**
 * /origins — Origin Explorer
 *
 * Visual model: Origin Cards + Flavour Strip
 *
 * The page shows a grid of country cards. Each card has a compact
 * horizontal flavour strip — coloured bands proportional to how many
 * coffees from that origin belong to each flavour family.
 *
 * Clicking a country expands an inline detail panel (no page navigation)
 * showing: flavour bars, process distribution, region chips, altitude,
 * price range, tendency text, and the coffee list.
 *
 * Why cards over a map:
 * - A world map at mobile width loses most labels
 * - Cards are scannable and touch-friendly
 * - The flavour strip gives immediate visual differentiation between origins
 * - An interactive map can be added later as an enhancement
 */

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ExplanationBlurb } from "@/components/ExplanationBlurb";
import { useSearchParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface FlavourFamily {
  slug: string;
  label: string;
  colour: string;
  count: number;
  pct?: number;
}

interface OriginSummary {
  country: string;
  emoji: string;
  coffee_count: number;
  listing_count: number;
  dominant_process: string | null;
  avg_price_gbp: number | null;
  top_flavour_families: FlavourFamily[];
  regions: string[];
}

interface ProcessStat {
  process: string;
  count: number;
  pct: number;
}

interface RegionStat {
  region: string;
  count: number;
}

interface OriginDetail {
  country: string;
  emoji: string;
  tendency: string;
  altitude_note: string;
  notable_regions: string[];
  coffee_count: number;
  listing_count: number;
  processes: ProcessStat[];
  flavour_families: FlavourFamily[];
  regions: RegionStat[];
  price_min: number | null;
  price_max: number | null;
  price_avg: number | null;
  altitude_min: number | null;
  altitude_max: number | null;
  coffees: {
    id: string;
    canonical_name: string;
    origin_region: string | null;
    process: string | null;
    roast_level: string | null;
    flavour_notes: string[];
    listing_count: number;
  }[];
}

const PROCESS_COLOURS: Record<string, string> = {
  washed: "#6b9e8c",
  natural: "#c4763a",
  honey: "#d4a84b",
  anaerobic: "#8b6bab",
  wet_hulled: "#5a7fa8",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OriginsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const selectedCountry = searchParams.get("country") ?? null;

  const [origins, setOrigins] = useState<OriginSummary[]>([]);
  const [detail, setDetail] = useState<OriginDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load origin list
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/origins`)
      .then((r) => r.json())
      .then((d) => { setOrigins(d.origins); setLoading(false); })
      .catch(() => { setError("Could not load origins."); setLoading(false); });
  }, []);

  // Load detail when country selected
  useEffect(() => {
    if (!selectedCountry) { setDetail(null); return; }
    setDetailLoading(true);
    fetch(`${API_BASE}/api/v1/origins/${encodeURIComponent(selectedCountry)}`)
      .then((r) => r.json())
      .then((d) => { setDetail(d); setDetailLoading(false); })
      .catch(() => setDetailLoading(false));
  }, [selectedCountry]);

  const selectCountry = useCallback((country: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (params.get("country") === country) {
      params.delete("country");
    } else {
      params.set("country", country);
    }
    router.replace(`?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  return (
    <div className="origins-root">
      {/* Header */}
      <header className="origins-header">
        <p className="origins-eyebrow">Explore by origin</p>
        <h1 className="origins-title">Origin Explorer</h1>
        <p className="origins-subtitle">
          Discover how geography shapes flavour. Click any origin to explore.
        </p>
      </header>

      {loading ? (
        <OriginsSkeleton />
      ) : error ? (
        <div className="origins-error">{error}</div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="origins-stats">
            <span>{origins.length} origins</span>
            <span className="origins-stats-sep">·</span>
            <span>{origins.reduce((s, o) => s + o.coffee_count, 0)} coffees</span>
          </div>

          {/* Origin grid */}
          <div className="origins-grid">
            {origins.map((origin) => (
              <OriginCard
                key={origin.country}
                origin={origin}
                selected={selectedCountry === origin.country}
                onClick={() => selectCountry(origin.country)}
              />
            ))}
          </div>

          {/* Inline detail panel */}
          {selectedCountry && (
            <div className="origins-detail-wrap" id="origin-detail">
              {detailLoading ? (
                <DetailSkeleton />
              ) : detail ? (
                <OriginDetailPanel detail={detail} onClose={() => {
                  const params = new URLSearchParams(searchParams.toString());
                  params.delete("country");
                  router.replace(`?${params.toString()}`, { scroll: false });
                }} />
              ) : null}
            </div>
          )}
        </>
      )}

      <style jsx>{pageStyles}</style>
    </div>
  );
}

// ── Origin Card ───────────────────────────────────────────────────────────────

function OriginCard({ origin, selected, onClick }: {
  origin: OriginSummary;
  selected: boolean;
  onClick: () => void;
}) {
  const maxCount = Math.max(1, ...origin.top_flavour_families.map((f) => f.count));

  return (
    <button
      className={`origin-card ${selected ? "origin-card-selected" : ""}`}
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`${origin.country}: ${origin.coffee_count} coffees`}
    >
      <div className="origin-card-header">
        <span className="origin-card-emoji">{origin.emoji}</span>
        <div className="origin-card-meta">
          <span className="origin-card-name">{origin.country}</span>
          <span className="origin-card-count">{origin.coffee_count} coffees</span>
        </div>
        {origin.dominant_process && (
          <span
            className="origin-card-process"
            style={{
              background: (PROCESS_COLOURS[origin.dominant_process] ?? "#888") + "22",
              color: PROCESS_COLOURS[origin.dominant_process] ?? "#888",
            }}
          >
            {origin.dominant_process}
          </span>
        )}
      </div>

      {/* Flavour strip */}
      {origin.top_flavour_families.length > 0 ? (
        <div className="origin-flavour-strip">
          {origin.top_flavour_families.map((fam) => (
            <div
              key={fam.slug}
              className="origin-flavour-band"
              style={{
                flex: fam.count,
                background: fam.colour,
              }}
              title={`${fam.label}: ${fam.count} coffees`}
            />
          ))}
          <div className="origin-flavour-band origin-flavour-rest"
            style={{ flex: Math.max(0, origin.coffee_count - origin.top_flavour_families.reduce((s, f) => s + f.count, 0)) }}
          />
        </div>
      ) : (
        <div className="origin-flavour-strip origin-flavour-empty">
          <div className="origin-flavour-band" style={{ flex: 1, background: "var(--border)" }} />
        </div>
      )}

      {/* Flavour labels */}
      {origin.top_flavour_families.length > 0 && (
        <div className="origin-flavour-labels">
          {origin.top_flavour_families.slice(0, 3).map((fam) => (
            <span key={fam.slug} className="origin-flavour-label" style={{ color: fam.colour }}>
              {fam.label}
            </span>
          ))}
        </div>
      )}

      {origin.avg_price_gbp && (
        <div className="origin-card-price">avg £{origin.avg_price_gbp.toFixed(2)}</div>
      )}
    </button>
  );
}

// ── Origin Detail Panel ───────────────────────────────────────────────────────

function OriginDetailPanel({ detail, onClose }: { detail: OriginDetail; onClose: () => void }) {
  const flavourFamilies = detail.flavour_families ?? [];
  const processes = detail.processes ?? [];
  const regions = detail.regions ?? [];
  const coffees = detail.coffees ?? [];
  const maxFlavour = Math.max(1, ...flavourFamilies.map((f) => f.count), 1);

  return (
    <div className="detail-panel">
      {/* Detail header */}
      <div className="detail-header">
        <div className="detail-header-left">
          <span className="detail-emoji">{detail.emoji}</span>
          <div>
            <h2 className="detail-country">{detail.country}</h2>
            <div className="detail-quick-stats">
              <span>{detail.coffee_count} coffees</span>
              {detail.price_min && detail.price_max && (
                <>
                  <span className="detail-sep">·</span>
                  <span>£{detail.price_min.toFixed(0)}–£{detail.price_max.toFixed(0)}</span>
                </>
              )}
              {detail.altitude_min && detail.altitude_max && (
                <>
                  <span className="detail-sep">·</span>
                  <span>{detail.altitude_min}–{detail.altitude_max}m</span>
                </>
              )}
            </div>
          </div>
        </div>
        <button className="detail-close" onClick={onClose} aria-label="Close">×</button>
      </div>

      {/* Tendency */}
      {detail.tendency && (
        <div className="detail-tendency">
          <p className="detail-tendency-text">{detail.tendency}</p>
          {detail.altitude_note && (
            <p className="detail-altitude-note">{detail.altitude_note}</p>
          )}
        </div>
      )}

      {/* Grounded origin explanation */}
      <div style={{ padding: "12px 24px 0" }}>
        <ExplanationBlurb type="origin" params={{ country: detail.country }} />
      </div>

      <div className="detail-body">
        {/* Flavour families */}
        {flavourFamilies.length > 0 && (
          <div className="detail-section">
            <h3 className="detail-section-title">Flavour character</h3>
            <div className="detail-flavour-bars">
              {flavourFamilies.map((fam) => (
                <div key={fam.slug} className="detail-flavour-row">
                  <span className="detail-flavour-label" style={{ color: fam.colour }}>
                    {fam.label}
                  </span>
                  <div className="detail-flavour-bar-wrap">
                    <div
                      className="detail-flavour-bar"
                      style={{
                        width: `${(fam.count / maxFlavour) * 100}%`,
                        background: fam.colour,
                      }}
                    />
                  </div>
                  <span className="detail-flavour-count">{fam.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Process distribution */}
        {processes.length > 0 && (
          <div className="detail-section">
            <h3 className="detail-section-title">Processing</h3>
            <div className="detail-processes">
              {processes.map((p) => (
                <div key={p.process} className="detail-process-row">
                  <span
                    className="detail-process-dot"
                    style={{ background: PROCESS_COLOURS[p.process] ?? "#888" }}
                  />
                  <span className="detail-process-name">{p.process}</span>
                  <div className="detail-process-bar-wrap">
                    <div
                      className="detail-process-bar"
                      style={{
                        width: `${p.pct}%`,
                        background: PROCESS_COLOURS[p.process] ?? "#888",
                      }}
                    />
                  </div>
                  <span className="detail-process-pct">{p.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Regions */}
        {regions.length > 0 && (
          <div className="detail-section">
            <h3 className="detail-section-title">Regions</h3>
            <div className="detail-regions">
              {regions.map((r) => (
                <span key={r.region} className="detail-region-chip">
                  {r.region}
                  <span className="detail-region-count">{r.count}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Coffee list */}
        {coffees.length > 0 && (
          <div className="detail-section">
            <h3 className="detail-section-title">Coffees from {detail.country}</h3>
            <div className="detail-coffees">
              {coffees.slice(0, 8).map((c) => (
                <Link key={c.id} href={`/coffees/${c.id}`} className="detail-coffee-row">
                  <div className="detail-coffee-info">
                    {c.process && (
                      <span
                        className="detail-coffee-process"
                        style={{ background: (PROCESS_COLOURS[c.process] ?? "#888") + "22",
                                 color: PROCESS_COLOURS[c.process] ?? "#888" }}
                      >
                        {c.process}
                      </span>
                    )}
                    <span className="detail-coffee-name">{c.canonical_name}</span>
                    {c.origin_region && (
                      <span className="detail-coffee-region">{c.origin_region}</span>
                    )}
                  </div>
                  <div className="detail-coffee-notes">
                    {c.flavour_notes.slice(0, 3).map((n) => (
                      <span key={n} className="detail-coffee-note">{n}</span>
                    ))}
                  </div>
                </Link>
              ))}
              {coffees.length > 8 && (
                <Link
                  href={`/coffees?origin=${encodeURIComponent(detail.country)}`}
                  className="detail-see-all"
                >
                  See all {coffees.length} coffees →
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Skeletons ─────────────────────────────────────────────────────────────────

function OriginsSkeleton() {
  return (
    <div className="origins-grid">
      {[...Array(8)].map((_, i) => (
        <div key={i} className="origin-skeleton" style={{ animationDelay: `${i * 0.05}s` }} />
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="detail-skeleton">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="detail-skeleton-row" />
      ))}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const pageStyles = `
  .origins-root {
    min-height: 100vh;
    background: var(--bg);
    padding-bottom: 120px;
  }

  /* Header */
  .origins-header {
    padding: 48px 32px 24px;
    max-width: 900px;
    margin: 0 auto;
  }
  .origins-eyebrow {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 8px;
  }
  .origins-title {
    font-family: var(--font-display);
    font-size: clamp(32px, 6vw, 56px);
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0 0 8px;
    line-height: 1.1;
  }
  .origins-subtitle {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
  }

  /* Stats */
  .origins-stats {
    max-width: 900px;
    margin: 0 auto 16px;
    padding: 0 32px;
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-faint);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .origins-stats-sep { opacity: 0.4; }

  /* Grid */
  .origins-grid {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 32px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
  }

  /* Origin card */
  .origin-card {
    text-align: left;
    background: var(--surface);
    border: 1.5px solid var(--border-light);
    border-radius: 14px;
    padding: 16px;
    cursor: pointer;
    transition: border-color 0.18s, transform 0.18s, box-shadow 0.18s;
    width: 100%;
  }
  .origin-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  }
  .origin-card-selected {
    border-color: var(--accent);
    background: var(--accent-dim);
  }
  .origin-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .origin-card-emoji { font-size: 22px; flex-shrink: 0; }
  .origin-card-meta { flex: 1; min-width: 0; }
  .origin-card-name {
    font-family: var(--font-display);
    font-size: 17px;
    font-weight: 500;
    font-style: italic;
    color: var(--text);
    display: block;
    line-height: 1.2;
  }
  .origin-card-count {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    display: block;
  }
  .origin-card-process {
    font-family: var(--font-body);
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 100px;
    font-weight: 500;
    text-transform: capitalize;
    flex-shrink: 0;
  }

  /* Flavour strip */
  .origin-flavour-strip {
    display: flex;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    gap: 1px;
    margin-bottom: 8px;
  }
  .origin-flavour-band {
    height: 100%;
    border-radius: 2px;
    min-width: 4px;
    transition: flex 0.3s ease;
  }
  .origin-flavour-rest { background: var(--border-light) !important; }
  .origin-flavour-empty { opacity: 0.3; }

  .origin-flavour-labels {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .origin-flavour-label {
    font-family: var(--font-body);
    font-size: 10px;
    font-weight: 500;
  }
  .origin-card-price {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 4px;
  }

  /* Detail panel */
  .origins-detail-wrap {
    max-width: 900px;
    margin: 24px auto 0;
    padding: 0 32px;
  }
  .detail-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    animation: detail-in 0.2s ease;
  }
  @keyframes detail-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 24px 24px 20px;
    border-bottom: 1px solid var(--border-light);
  }
  .detail-header-left { display: flex; align-items: center; gap: 16px; }
  .detail-emoji { font-size: 36px; }
  .detail-country {
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0 0 4px;
  }
  .detail-quick-stats {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-faint);
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .detail-sep { opacity: 0.4; }
  .detail-close {
    background: none;
    border: none;
    color: var(--text-faint);
    font-size: 22px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
    transition: color 0.15s;
    flex-shrink: 0;
  }
  .detail-close:hover { color: var(--text); }

  .detail-tendency {
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-light);
    background: var(--bg-warm);
  }
  .detail-tendency-text {
    font-family: var(--font-display);
    font-size: 16px;
    font-style: italic;
    color: var(--text-muted);
    margin: 0 0 8px;
    line-height: 1.6;
  }
  .detail-altitude-note {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-faint);
    margin: 0;
    line-height: 1.5;
  }

  .detail-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }
  .detail-section {
    padding: 20px 24px;
    border-right: 1px solid var(--border-light);
    border-bottom: 1px solid var(--border-light);
  }
  .detail-section:nth-child(even) { border-right: none; }
  .detail-section:last-child, .detail-section:nth-last-child(2):nth-child(odd) {
    border-bottom: none;
  }
  .detail-section-title {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 12px;
  }

  /* Flavour bars */
  .detail-flavour-bars { display: flex; flex-direction: column; gap: 8px; }
  .detail-flavour-row { display: flex; align-items: center; gap: 8px; }
  .detail-flavour-label {
    font-family: var(--font-body);
    font-size: 12px;
    font-weight: 500;
    width: 70px;
    flex-shrink: 0;
  }
  .detail-flavour-bar-wrap {
    flex: 1;
    height: 6px;
    background: var(--surface-raised);
    border-radius: 3px;
    overflow: hidden;
  }
  .detail-flavour-bar {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
    min-width: 3px;
  }
  .detail-flavour-count {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    width: 20px;
    text-align: right;
  }

  /* Process bars */
  .detail-processes { display: flex; flex-direction: column; gap: 8px; }
  .detail-process-row { display: flex; align-items: center; gap: 8px; }
  .detail-process-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .detail-process-name {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-muted);
    width: 70px;
    flex-shrink: 0;
    text-transform: capitalize;
  }
  .detail-process-bar-wrap {
    flex: 1;
    height: 5px;
    background: var(--surface-raised);
    border-radius: 3px;
    overflow: hidden;
  }
  .detail-process-bar {
    height: 100%;
    border-radius: 3px;
    min-width: 2px;
  }
  .detail-process-pct {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    width: 32px;
    text-align: right;
  }

  /* Regions */
  .detail-regions { display: flex; flex-wrap: wrap; gap: 6px; }
  .detail-region-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 100px;
    background: var(--surface-raised);
    border: 1px solid var(--border-light);
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-muted);
  }
  .detail-region-count {
    font-size: 10px;
    color: var(--text-faint);
    background: var(--border-light);
    border-radius: 100px;
    padding: 0 5px;
  }

  /* Coffee list */
  .detail-coffees { display: flex; flex-direction: column; gap: 2px; }
  .detail-coffee-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    text-decoration: none;
    transition: background 0.15s;
  }
  .detail-coffee-row:hover { background: var(--surface-raised); }
  .detail-coffee-info { flex: 1; min-width: 0; }
  .detail-coffee-process {
    display: inline-block;
    font-family: var(--font-body);
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 100px;
    font-weight: 500;
    text-transform: capitalize;
    margin-bottom: 3px;
  }
  .detail-coffee-name {
    display: block;
    font-family: var(--font-display);
    font-size: 15px;
    font-style: italic;
    color: var(--text);
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .detail-coffee-region {
    display: block;
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 2px;
  }
  .detail-coffee-notes {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: flex-start;
    flex-shrink: 0;
  }
  .detail-coffee-note {
    font-family: var(--font-body);
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 100px;
    background: var(--surface-raised);
    color: var(--text-faint);
    white-space: nowrap;
  }
  .detail-see-all {
    display: block;
    margin-top: 8px;
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--accent);
    text-decoration: none;
    padding: 6px 10px;
  }
  .detail-see-all:hover { text-decoration: underline; }

  /* Skeletons */
  .origin-skeleton {
    height: 130px;
    border-radius: 14px;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  .detail-skeleton { padding: 24px; display: flex; flex-direction: column; gap: 12px; }
  .detail-skeleton-row {
    height: 40px;
    border-radius: 8px;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .origins-error {
    text-align: center;
    padding: 64px 32px;
    font-family: var(--font-body);
    color: var(--text-muted);
  }

  /* Mobile */
  @media (max-width: 600px) {
    .origins-header { padding: 32px 20px 20px; }
    .origins-stats, .origins-grid, .origins-detail-wrap { padding: 0 20px; }
    .origins-grid { grid-template-columns: 1fr 1fr; gap: 10px; }
    .detail-body { grid-template-columns: 1fr; }
    .detail-section { border-right: none !important; }
    .detail-header { padding: 16px; }
    .detail-tendency { padding: 16px; }
    .detail-section { padding: 16px; }
  }
  @media (max-width: 380px) {
    .origins-grid { grid-template-columns: 1fr; }
  }
`;
