"use client";

/**
 * /roasters/[id] — Roaster Fingerprint page.
 *
 * Visual model: Composite Fingerprint Strip
 *
 * The fingerprint is a horizontal composite of three stacked lanes:
 *   1. Flavour families — coloured bands proportional to coffee count
 *   2. Process mix — coloured bands proportional to process count
 *   3. Roast distribution — a gradient ribbon from light → dark
 *
 * Reading all three together gives an immediate gestalt of the roaster's
 * style — a light-roast washed-process floral specialist looks very
 * different from a dark-roast natural-process chocolate-led roaster.
 *
 * Below the fingerprint: origin blocks, price stats, recent coffees.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { ExplanationBlurb } from "@/components/ExplanationBlurb";
import { useParams } from "next/navigation";



// ── Types ─────────────────────────────────────────────────────────────────────

interface FamilyStat   { slug: string; label: string; colour: string; count: number; pct: number; }
interface ProcessStat  { process: string; colour: string; count: number; pct: number; }
interface OriginStat   { country: string; count: number; pct: number; }
interface RoastStat    { roast_level: string; count: number; pct: number; }
interface RecentCoffee {
  id: string; canonical_name: string; origin_country: string | null;
  process: string | null; roast_level: string | null;
  flavour_notes: string[]; min_price_gbp: number | null;
}
interface Fingerprint {
  store_id: string; name: string; domain: string;
  homepage_url: string; uk_region: string | null;
  roaster_flag: boolean; cafe_flag: boolean;
  coffee_count: number; listing_count: number;
  style_summary: string;
  flavour_families: FamilyStat[];
  processes: ProcessStat[];
  origins: OriginStat[];
  roast_levels: RoastStat[];
  avg_price_gbp: number | null;
  price_min_gbp: number | null;
  price_max_gbp: number | null;
  recent_coffees: RecentCoffee[];
}

const PROCESS_COLOURS: Record<string, string> = {
  washed: "#6b9e8c", natural: "#c4763a", honey: "#d4a84b",
  anaerobic: "#8b6bab", wet_hulled: "#5a7fa8",
};

const ROAST_COLOURS: Record<string, string> = {
  light: "#f5e6c8", medium_light: "#e8c98a", medium: "#c4763a",
  medium_dark: "#8b4a20", dark: "#3a1a0a",
};

const ROAST_LABELS: Record<string, string> = {
  light: "Light", medium_light: "Med-Light", medium: "Medium",
  medium_dark: "Med-Dark", dark: "Dark",
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RoasterPage() {
  const params = useParams();
  const id = params?.id as string;

  const [fp, setFp] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/roasters/${id}/fingerprint`)
      .then((r) => { if (!r.ok) throw new Error(r.status.toString()); return r.json(); })
      .then((d) => { setFp(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [id]);

  if (loading) return <PageSkeleton />;
  if (error || !fp) return (
    <div className="rf-error">
      <p>Roaster not found.</p>
      <Link href="/roasters">← All roasters</Link>
    </div>
  );

  return (
    <div className="rf-root">
      {/* Header */}
      <header className="rf-header">
        <Link href="/roasters" className="rf-back">← Roasters</Link>
        <div className="rf-header-main">
          <div className="rf-avatar">{fp.name.charAt(0)}</div>
          <div>
            <h1 className="rf-name">{fp.name}</h1>
            <div className="rf-meta">
              {fp.uk_region && <span className="rf-badge">{fp.uk_region}</span>}
              {fp.cafe_flag && <span className="rf-badge">☕ Café</span>}
              {fp.roaster_flag && <span className="rf-badge">🫘 Roaster</span>}
            </div>
          </div>
          <a
            href={fp.homepage_url}
            target="_blank"
            rel="noopener"
            className="rf-visit"
          >
            Visit site →
          </a>
        </div>

        {/* Quick stats */}
        <div className="rf-quick-stats">
          <div className="rf-stat">
            <span className="rf-stat-val">{fp.coffee_count}</span>
            <span className="rf-stat-label">coffees</span>
          </div>
          {fp.avg_price_gbp && (
            <div className="rf-stat">
              <span className="rf-stat-val">£{fp.avg_price_gbp.toFixed(2)}</span>
              <span className="rf-stat-label">avg price</span>
            </div>
          )}
          {fp.price_min_gbp && fp.price_max_gbp && (
            <div className="rf-stat">
              <span className="rf-stat-val">£{fp.price_min_gbp.toFixed(0)}–£{fp.price_max_gbp.toFixed(0)}</span>
              <span className="rf-stat-label">range</span>
            </div>
          )}
          {fp.origins.length > 0 && (
            <div className="rf-stat">
              <span className="rf-stat-val">{fp.origins.length}</span>
              <span className="rf-stat-label">origins</span>
            </div>
          )}
        </div>
      </header>

      {/* ── Fingerprint visual ── */}
      <section className="rf-section">
        <RoasterFingerprintVisual fp={fp} />
      </section>

      {/* Style summary */}
      {fp.style_summary && (
        <div className="rf-summary">
          <p className="rf-summary-text">{fp.style_summary}</p>
        </div>
      )}

      {/* Grounded roaster explanation */}
      {fp.store_id && (
        <div className="rf-explanation">
          <ExplanationBlurb type="roaster" params={{ roasterId: fp.store_id }} />
        </div>
      )}

      {/* ── Body grid ── */}
      <div className="rf-body-grid">
        {/* Origins */}
        {fp.origins.length > 0 && (
          <div className="rf-card">
            <h3 className="rf-card-title">Origins</h3>
            <OriginBlocks origins={fp.origins} />
          </div>
        )}

        {/* Process + Roast */}
        <div className="rf-card">
          <h3 className="rf-card-title">Processing</h3>
          <div className="rf-process-list">
            {fp.processes.map((p) => (
              <div key={p.process} className="rf-process-row">
                <span className="rf-process-dot" style={{ background: p.colour }} />
                <span className="rf-process-name">{p.process}</span>
                <div className="rf-process-bar-wrap">
                  <div className="rf-process-bar" style={{ width: `${p.pct}%`, background: p.colour }} />
                </div>
                <span className="rf-process-pct">{p.pct}%</span>
              </div>
            ))}
          </div>
          {fp.roast_levels.length > 0 && (
            <>
              <h3 className="rf-card-title" style={{ marginTop: 20 }}>Roast profile</h3>
              <RoastStrip roasts={fp.roast_levels} />
            </>
          )}
        </div>
      </div>

      {/* ── Recent coffees ── */}
      {fp.recent_coffees.length > 0 && (
        <section className="rf-section">
          <h3 className="rf-section-title">Recent coffees</h3>
          <div className="rf-coffees-grid">
            {fp.recent_coffees.map((c) => (
              <Link key={c.id} href={`/coffees/${c.id}`} className="rf-coffee-card">
                {c.process && (
                  <div
                    className="rf-coffee-process-bar"
                    style={{ background: PROCESS_COLOURS[c.process] ?? "#888" }}
                  />
                )}
                <div className="rf-coffee-body">
                  <div className="rf-coffee-origin">{c.origin_country ?? "—"}</div>
                  <div className="rf-coffee-name">{c.canonical_name}</div>
                  <div className="rf-coffee-notes">
                    {c.flavour_notes.map((n) => (
                      <span key={n} className="rf-coffee-note">{n}</span>
                    ))}
                  </div>
                  {c.min_price_gbp && (
                    <div className="rf-coffee-price">from £{c.min_price_gbp.toFixed(2)}</div>
                  )}
                </div>
              </Link>
            ))}
          </div>
          <Link href={`/coffees?store=${id}`} className="rf-see-all">
            See all {fp.coffee_count} coffees →
          </Link>
        </section>
      )}

      <style jsx>{styles}</style>
    </div>
  );
}

// ── Fingerprint Visual ────────────────────────────────────────────────────────

function RoasterFingerprintVisual({ fp }: { fp: Fingerprint }) {
  const hasFlavour = fp.flavour_families.length > 0;
  const hasProcess = fp.processes.length > 0;
  const hasRoast   = fp.roast_levels.length > 0;

  if (!hasFlavour && !hasProcess && !hasRoast) {
    return (
      <div className="fp-empty">
        <p>Not enough data yet to build this roaster's fingerprint.</p>
      </div>
    );
  }

  return (
    <div className="fp-wrap">
      <div className="fp-label-col">
        {hasFlavour && <span className="fp-lane-label">Flavour</span>}
        {hasProcess && <span className="fp-lane-label">Process</span>}
        {hasRoast   && <span className="fp-lane-label">Roast</span>}
      </div>

      <div className="fp-lanes">
        {/* Lane 1: Flavour families */}
        {hasFlavour && (
          <div className="fp-lane">
            {fp.flavour_families.map((f) => (
              <div
                key={f.slug}
                className="fp-segment"
                style={{ flex: f.count, background: f.colour }}
                title={`${f.label}: ${f.count} coffees (${f.pct}%)`}
              />
            ))}
          </div>
        )}

        {/* Lane 2: Process mix */}
        {hasProcess && (
          <div className="fp-lane">
            {fp.processes.map((p) => (
              <div
                key={p.process}
                className="fp-segment"
                style={{ flex: p.count, background: p.colour }}
                title={`${p.process}: ${p.pct}%`}
              />
            ))}
          </div>
        )}

        {/* Lane 3: Roast distribution */}
        {hasRoast && (
          <div className="fp-lane">
            {fp.roast_levels.map((r) => (
              <div
                key={r.roast_level}
                className="fp-segment"
                style={{ flex: r.count, background: ROAST_COLOURS[r.roast_level] ?? "#888" }}
                title={`${ROAST_LABELS[r.roast_level] ?? r.roast_level}: ${r.pct}%`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="fp-legend">
        {hasFlavour && (
          <div className="fp-legend-row">
            {fp.flavour_families.map((f) => (
              <span key={f.slug} className="fp-legend-item">
                <span className="fp-legend-dot" style={{ background: f.colour }} />
                {f.label}
              </span>
            ))}
          </div>
        )}
        {hasProcess && (
          <div className="fp-legend-row">
            {fp.processes.map((p) => (
              <span key={p.process} className="fp-legend-item">
                <span className="fp-legend-dot" style={{ background: p.colour }} />
                {p.process}
              </span>
            ))}
          </div>
        )}
        {hasRoast && (
          <div className="fp-legend-row">
            {fp.roast_levels.map((r) => (
              <span key={r.roast_level} className="fp-legend-item">
                <span className="fp-legend-dot" style={{ background: ROAST_COLOURS[r.roast_level] ?? "#888",
                  border: r.roast_level === "light" ? "1px solid var(--border)" : "none" }} />
                {ROAST_LABELS[r.roast_level] ?? r.roast_level}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Origin blocks ─────────────────────────────────────────────────────────────

function OriginBlocks({ origins }: { origins: OriginStat[] }) {
  const max = Math.max(...origins.map((o) => o.count), 1);
  return (
    <div className="origin-blocks">
      {origins.map((o) => (
        <div key={o.country} className="origin-block-row">
          <span className="origin-block-name">{o.country}</span>
          <div className="origin-block-bar-wrap">
            <div
              className="origin-block-bar"
              style={{ width: `${(o.count / max) * 100}%` }}
            />
          </div>
          <span className="origin-block-count">{o.count}</span>
        </div>
      ))}
    </div>
  );
}

// ── Roast strip ───────────────────────────────────────────────────────────────

function RoastStrip({ roasts }: { roasts: RoastStat[] }) {
  return (
    <div>
      <div className="roast-strip">
        {roasts.map((r) => (
          <div
            key={r.roast_level}
            className="roast-strip-seg"
            style={{
              flex: r.count,
              background: ROAST_COLOURS[r.roast_level] ?? "#888",
              border: r.roast_level === "light" ? "1px solid var(--border)" : "none",
            }}
            title={`${ROAST_LABELS[r.roast_level]}: ${r.pct}%`}
          />
        ))}
      </div>
      <div className="roast-strip-labels">
        {roasts.map((r) => (
          <span key={r.roast_level} className="roast-strip-label" style={{ flex: r.count }}>
            {r.pct >= 20 ? (ROAST_LABELS[r.roast_level] ?? r.roast_level) : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── States ────────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="rf-root">
      <div className="rf-skeleton-header" />
      <div className="rf-skeleton-fp" />
      <div className="rf-body-grid">
        <div className="rf-skeleton-card" />
        <div className="rf-skeleton-card" />
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = `
  .rf-root { min-height: 100vh; background: var(--bg); padding-bottom: 120px; }

  /* Header */
  .rf-header { max-width: 860px; margin: 0 auto; padding: 48px 32px 0; }
  .rf-back {
    font-family: var(--font-body); font-size: 12px; letter-spacing: 0.06em;
    color: var(--text-faint); text-decoration: none; display: block; margin-bottom: 16px;
    transition: color 0.15s;
  }
  .rf-back:hover { color: var(--accent); }
  .rf-header-main { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .rf-avatar {
    width: 52px; height: 52px; border-radius: 50%;
    background: var(--accent-dim); color: var(--accent);
    font-family: var(--font-display); font-size: 24px; font-weight: 500;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .rf-name {
    font-family: var(--font-display); font-size: clamp(24px, 4vw, 40px);
    font-weight: 300; font-style: italic; color: var(--text);
    margin: 0 0 6px; line-height: 1.1;
  }
  .rf-meta { display: flex; gap: 6px; flex-wrap: wrap; }
  .rf-badge {
    font-family: var(--font-body); font-size: 11px; padding: 3px 9px;
    border-radius: 100px; background: var(--surface-raised);
    color: var(--text-faint); border: 1px solid var(--border-light);
  }
  .rf-visit {
    margin-left: auto; font-family: var(--font-body); font-size: 13px;
    color: var(--accent); text-decoration: none; white-space: nowrap;
    padding: 8px 16px; border: 1.5px solid var(--accent);
    border-radius: 100px; transition: all 0.15s; flex-shrink: 0;
  }
  .rf-visit:hover { background: var(--accent); color: white; }

  .rf-quick-stats { display: flex; gap: 28px; flex-wrap: wrap; padding-bottom: 24px; border-bottom: 1px solid var(--border-light); }
  .rf-stat { display: flex; flex-direction: column; gap: 2px; }
  .rf-stat-val { font-family: var(--font-display); font-size: 22px; font-weight: 400; color: var(--text); line-height: 1; }
  .rf-stat-label { font-family: var(--font-body); font-size: 11px; color: var(--text-faint); }

  /* Sections */
  .rf-section { max-width: 860px; margin: 28px auto 0; padding: 0 32px; }
  .rf-section-title {
    font-family: var(--font-body); font-size: 11px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--text-faint); margin: 0 0 14px;
  }

  /* Fingerprint */
  .fp-wrap { background: var(--surface); border: 1px solid var(--border-light); border-radius: 14px; padding: 20px 20px 14px; }
  .fp-label-col { display: none; }
  .fp-lanes { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
  .fp-lane { display: flex; height: 18px; border-radius: 4px; overflow: hidden; gap: 2px; }
  .fp-segment { height: 100%; min-width: 3px; border-radius: 3px; transition: flex 0.4s ease; }
  .fp-legend { display: flex; flex-direction: column; gap: 6px; padding-top: 8px; border-top: 1px solid var(--border-light); }
  .fp-legend-row { display: flex; flex-wrap: wrap; gap: 8px; }
  .fp-legend-item { display: flex; align-items: center; gap: 5px; font-family: var(--font-body); font-size: 11px; color: var(--text-faint); text-transform: capitalize; }
  .fp-legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .fp-empty { padding: 32px; text-align: center; font-family: var(--font-body); font-size: 14px; color: var(--text-faint); }

  /* Summary */
  .rf-summary { max-width: 860px; margin: 20px auto 0; padding: 0 32px; }
  .rf-explanation {
    max-width: 860px;
    margin: 8px auto 0;
    padding: 0 32px;
  }
  .rf-summary-text {
    font-family: var(--font-display); font-size: 17px; font-style: italic;
    color: var(--text-muted); margin: 0; line-height: 1.6;
  }

  /* Body grid */
  .rf-body-grid {
    max-width: 860px; margin: 24px auto 0; padding: 0 32px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
  }
  .rf-card {
    background: var(--surface); border: 1px solid var(--border-light);
    border-radius: 14px; padding: 20px;
  }
  .rf-card-title {
    font-family: var(--font-body); font-size: 10px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--text-faint); margin: 0 0 14px;
  }

  /* Process */
  .rf-process-list { display: flex; flex-direction: column; gap: 10px; }
  .rf-process-row { display: flex; align-items: center; gap: 8px; }
  .rf-process-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .rf-process-name { font-family: var(--font-body); font-size: 12px; color: var(--text-muted); width: 68px; flex-shrink: 0; text-transform: capitalize; }
  .rf-process-bar-wrap { flex: 1; height: 5px; background: var(--surface-raised); border-radius: 3px; overflow: hidden; }
  .rf-process-bar { height: 100%; border-radius: 3px; min-width: 2px; transition: width 0.4s ease; }
  .rf-process-pct { font-family: var(--font-body); font-size: 11px; color: var(--text-faint); width: 32px; text-align: right; }

  /* Origins */
  .origin-blocks { display: flex; flex-direction: column; gap: 8px; }
  .origin-block-row { display: flex; align-items: center; gap: 8px; }
  .origin-block-name { font-family: var(--font-body); font-size: 12px; color: var(--text-muted); width: 80px; flex-shrink: 0; }
  .origin-block-bar-wrap { flex: 1; height: 6px; background: var(--surface-raised); border-radius: 3px; overflow: hidden; }
  .origin-block-bar { height: 100%; border-radius: 3px; background: var(--accent); min-width: 3px; transition: width 0.4s ease; }
  .origin-block-count { font-family: var(--font-body); font-size: 11px; color: var(--text-faint); width: 20px; text-align: right; }

  /* Roast strip */
  .roast-strip { display: flex; height: 10px; border-radius: 5px; overflow: hidden; gap: 2px; margin-bottom: 6px; }
  .roast-strip-seg { height: 100%; min-width: 3px; border-radius: 4px; }
  .roast-strip-labels { display: flex; }
  .roast-strip-label { font-family: var(--font-body); font-size: 10px; color: var(--text-faint); text-align: center; }

  /* Recent coffees */
  .rf-coffees-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
  .rf-coffee-card {
    display: block; background: var(--surface); border: 1px solid var(--border-light);
    border-radius: 12px; overflow: hidden; text-decoration: none;
    transition: border-color 0.18s, transform 0.18s;
  }
  .rf-coffee-card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .rf-coffee-process-bar { height: 3px; width: 100%; }
  .rf-coffee-body { padding: 14px; }
  .rf-coffee-origin { font-family: var(--font-body); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); margin-bottom: 4px; }
  .rf-coffee-name { font-family: var(--font-display); font-size: 15px; font-style: italic; color: var(--text); margin-bottom: 8px; line-height: 1.2; }
  .rf-coffee-notes { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
  .rf-coffee-note { font-family: var(--font-body); font-size: 10px; padding: 2px 7px; border-radius: 100px; background: var(--surface-raised); color: var(--text-faint); }
  .rf-coffee-price { font-family: var(--font-body); font-size: 12px; font-weight: 600; color: var(--accent); }
  .rf-see-all { display: block; margin-top: 16px; font-family: var(--font-body); font-size: 13px; color: var(--accent); text-decoration: none; }
  .rf-see-all:hover { text-decoration: underline; }

  /* Skeletons */
  .rf-skeleton-header { height: 140px; background: var(--surface); margin: 48px 32px 0; max-width: 860px; margin-left: auto; margin-right: auto; border-radius: 14px; animation: shimmer 1.4s ease-in-out infinite; background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%); background-size: 200% 100%; }
  .rf-skeleton-fp { height: 120px; margin: 24px 32px 0; max-width: 860px; margin-left: auto; margin-right: auto; border-radius: 14px; animation: shimmer 1.4s ease-in-out infinite; background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%); background-size: 200% 100%; }
  .rf-skeleton-card { height: 200px; border-radius: 14px; animation: shimmer 1.4s ease-in-out infinite; background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%); background-size: 200% 100%; }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .rf-error { max-width: 480px; margin: 80px auto; padding: 0 32px; text-align: center; font-family: var(--font-body); color: var(--text-muted); }
  .rf-error a { color: var(--accent); text-decoration: none; display: block; margin-top: 12px; }

  @media (max-width: 600px) {
    .rf-header, .rf-section, .rf-summary { padding: 0 20px; }
    .rf-header { padding-top: 32px; }
    .rf-body-grid { grid-template-columns: 1fr; padding: 0 20px; }
    .rf-coffees-grid { grid-template-columns: 1fr 1fr; }
    .rf-visit { display: none; }
  }
`;
