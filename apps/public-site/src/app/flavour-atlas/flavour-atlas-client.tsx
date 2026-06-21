"use client";


/**
 * Flavour Atlas — /flavour-atlas
 *
 * Interaction model: Orbital Bloom
 * Families orbit a central point. Clicking a family blooms its sub-nodes
 * outward in a second ring. Clicking a sub-node (category or tag) adds it
 * to the active selection and fetches matching coffees below.
 *
 * Why this model instead of a sunburst:
 * - Sunbursts encode hierarchy through area, making outer rings illegible at small sizes.
 * - The orbital bloom encodes hierarchy through proximity and animation, keeping all
 *   labels large and readable at every depth.
 * - Selection is additive — users can build a taste profile across families.
 * - The central node provides live feedback (X coffees match) as selections change.
 */

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

// Use local proxy routes instead of external API
const API_BASE = "";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AtlasNode {
  slug: string;
  label: string;
  depth: number;
  colour: string;
  coffee_count: number;
  children: AtlasNode[];
}

interface AtlasResponse {
  families: AtlasNode[];
  total_coffees: number;
}

interface MatchedCoffee {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  process: string | null;
  roast_level: string | null;
  flavour_notes: string[];
  data_completeness_score: number;
  matched_tags: { slug: string; label: string }[];
}

// ── Geometry helpers ──────────────────────────────────────────────────────────

function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function FlavourAtlasPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [atlas, setAtlas] = useState<AtlasResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Which family is currently "bloomed" (showing its children)
  const [activeFamilySlug, setActiveFamilySlug] = useState<string | null>(null);

  // Selected slugs (can be family, category, or tag)
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(() => {
    const param = searchParams.get("flavours");
    return param ? new Set(param.split(",").filter(Boolean)) : new Set();
  });

  // Coffees matching current selection
  const [coffees, setCoffees] = useState<MatchedCoffee[]>([]);
  const [coffeeTotal, setCoffeeTotal] = useState(0);
  const [coffeePage, setCoffeePage] = useState(1);
  const [coffeeLoading, setCoffeeLoading] = useState(false);

  // View mode
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");

  // Load taxonomy
  useEffect(() => {
    fetch(`${API_BASE}/api/taste/atlas`)
      .then((r) => r.json())
      .then((d: AtlasResponse) => { setAtlas(d); setLoading(false); })
      .catch(() => { setError("Could not load flavour data."); setLoading(false); });
  }, []);

  // Sync URL
  useEffect(() => {
    const slugStr = [...selectedSlugs].join(",");
    const params = new URLSearchParams(searchParams.toString());
    if (slugStr) params.set("flavours", slugStr);
    else params.delete("flavours");
    router.replace(`?${params.toString()}`, { scroll: false });
  }, [selectedSlugs]);

  // Fetch coffees when selection changes
  useEffect(() => {
    if (selectedSlugs.size === 0) { setCoffees([]); setCoffeeTotal(0); return; }
    setCoffeeLoading(true);
    setCoffeePage(1);
    const slugStr = [...selectedSlugs].join(",");
    fetch(`${API_BASE}/api/taste/atlas/coffees?slugs=${encodeURIComponent(slugStr)}&page=1&page_size=12`)
      .then((r) => r.json())
      .then((d) => { setCoffees(d.data); setCoffeeTotal(d.total); setCoffeeLoading(false); })
      .catch(() => setCoffeeLoading(false));
  }, [selectedSlugs]);

  const loadMoreCoffees = useCallback(() => {
    const next = coffeePage + 1;
    const slugStr = [...selectedSlugs].join(",");
    fetch(`${API_BASE}/api/taste/atlas/coffees?slugs=${encodeURIComponent(slugStr)}&page=${next}&page_size=12`)
      .then((r) => r.json())
      .then((d) => { setCoffees((prev) => [...prev, ...d.data]); setCoffeePage(next); });
  }, [coffeePage, selectedSlugs]);

  const toggleSlug = useCallback((slug: string, familySlug: string) => {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
    // If clicking a family node, also bloom/unbloom it
    setActiveFamilySlug((prev) => prev === familySlug ? null : familySlug);
  }, []);

  const clearAll = useCallback(() => {
    setSelectedSlugs(new Set());
    setActiveFamilySlug(null);
  }, []);

  const activeFamily = useMemo(
    () => atlas?.families.find((f) => f.slug === activeFamilySlug) ?? null,
    [atlas, activeFamilySlug]
  );

  const selectedCount = useMemo(() => {
    if (selectedSlugs.size === 0) return atlas?.total_coffees ?? 0;
    return coffeeTotal;
  }, [selectedSlugs, coffeeTotal, atlas]);

  return (
    <div className="atlas-root">
      {/* ── Page header ── */}
      <header className="atlas-header">
        <div className="atlas-header-inner">
          <p className="atlas-eyebrow">Discover by taste</p>
          <h1 className="atlas-title">Flavour Atlas</h1>
          <p className="atlas-subtitle">
            Select a flavour family to explore. Add notes to narrow your search.
          </p>
        </div>
        <div className="atlas-controls">
          <button
            className={`mode-btn ${viewMode === "graph" ? "active" : ""}`}
            onClick={() => setViewMode("graph")}
            aria-pressed={viewMode === "graph"}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="2.5" fill="currentColor" />
              <circle cx="8" cy="2" r="1.5" fill="currentColor" opacity=".6" />
              <circle cx="14" cy="5" r="1.5" fill="currentColor" opacity=".6" />
              <circle cx="14" cy="11" r="1.5" fill="currentColor" opacity=".6" />
              <circle cx="8" cy="14" r="1.5" fill="currentColor" opacity=".6" />
              <circle cx="2" cy="11" r="1.5" fill="currentColor" opacity=".6" />
              <circle cx="2" cy="5" r="1.5" fill="currentColor" opacity=".6" />
            </svg>
            Visual
          </button>
          <button
            className={`mode-btn ${viewMode === "list" ? "active" : ""}`}
            onClick={() => setViewMode("list")}
            aria-pressed={viewMode === "list"}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="3" width="14" height="1.5" rx=".75" fill="currentColor" />
              <rect x="1" y="7.25" width="14" height="1.5" rx=".75" fill="currentColor" opacity=".6" />
              <rect x="1" y="11.5" width="14" height="1.5" rx=".75" fill="currentColor" opacity=".4" />
            </svg>
            List
          </button>
          {selectedSlugs.size > 0 && (
            <button className="clear-btn" onClick={clearAll}>
              Clear
            </button>
          )}
        </div>
      </header>

      {/* ── Graph or list view ── */}
      {loading ? (
        <div className="atlas-loading">
          <div className="loading-bloom">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="loading-petal" style={{ "--i": i } as React.CSSProperties} />
            ))}
          </div>
          <p>Mapping flavours…</p>
        </div>
      ) : error ? (
        <div className="atlas-error">{error}</div>
      ) : atlas && viewMode === "graph" ? (
        <OrbitalGraph
          atlas={atlas}
          activeFamilySlug={activeFamilySlug}
          selectedSlugs={selectedSlugs}
          onToggle={toggleSlug}
          matchCount={selectedCount}
        />
      ) : atlas && viewMode === "list" ? (
        <ListView
          atlas={atlas}
          selectedSlugs={selectedSlugs}
          onToggle={toggleSlug}
        />
      ) : null}

      {/* ── Chip strip for active selections ── */}
      {selectedSlugs.size > 0 && (
        <div className="atlas-chips">
          {[...selectedSlugs].map((slug) => {
            const node = findNode(atlas?.families ?? [], slug);
            return (
              <button
                key={slug}
                className="chip"
                style={{ "--chip-colour": node?.colour ?? "#888" } as React.CSSProperties}
                onClick={() => setSelectedSlugs((prev) => { const n = new Set(prev); n.delete(slug); return n; })}
              >
                {node?.label ?? slug}
                <span className="chip-x">×</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Coffee results ── */}
      {selectedSlugs.size > 0 && (
        <section className="atlas-results">
          <div className="results-header">
            <h2 className="results-title">
              {coffeeLoading ? "Finding coffees…" : `${coffeeTotal} coffee${coffeeTotal !== 1 ? "s" : ""} match`}
            </h2>
          </div>

          {coffeeLoading ? (
            <div className="results-skeleton">
              {[...Array(4)].map((_, i) => <div key={i} className="skeleton-card" />)}
            </div>
          ) : coffees.length === 0 ? (
            <div className="empty-results">
              <p>No coffees tagged with these flavours yet.</p>
              <p className="empty-hint">Try selecting a broader family.</p>
            </div>
          ) : (
            <>
              <div className="results-grid">
                {coffees.map((c) => (
                  <CoffeeResultCard key={c.id} coffee={c} selectedSlugs={selectedSlugs} />
                ))}
              </div>
              {coffees.length < coffeeTotal && (
                <button className="load-more" onClick={loadMoreCoffees}>
                  Load more
                </button>
              )}
            </>
          )}
        </section>
      )}

      {/* ── Empty state ── */}
      {selectedSlugs.size === 0 && !loading && (
        <div className="atlas-onboarding">
          <div className="onboarding-line" />
          <p>
            {atlas ? `${atlas.total_coffees} coffees mapped across ${atlas.families.length} flavour families.` : ""}
            <br />
            Select a node to begin.
          </p>
        </div>
      )}

      <style jsx>{atlasStyles}</style>
    </div>
  );
}

// ── Orbital Graph Component ───────────────────────────────────────────────────

function OrbitalGraph({
  atlas,
  activeFamilySlug,
  selectedSlugs,
  onToggle,
  matchCount,
}: {
  atlas: AtlasResponse;
  activeFamilySlug: string | null;
  selectedSlugs: Set<string>;
  onToggle: (slug: string, familySlug: string) => void;
  matchCount: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dims, setDims] = useState({ w: 600, h: 600 });

  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      const entry = entries[0];
      const w = entry.contentRect.width;
      const h = Math.min(w, 600);
      setDims({ w, h });
    });
    if (svgRef.current?.parentElement) obs.observe(svgRef.current.parentElement);
    return () => obs.disconnect();
  }, []);

  const { w, h } = dims;
  const cx = w / 2;
  const cy = h / 2;
  const familyR = Math.min(w, h) * 0.32;
  const childR = Math.min(w, h) * 0.47;
  const nodeSz = Math.min(w, h) * 0.07;
  const childSz = nodeSz * 0.72;

  const families = atlas.families;
  const activeFamily = families.find((f) => f.slug === activeFamilySlug) ?? null;

  // Children to show: category nodes if family has categories, else tag nodes
  const visibleChildren: (AtlasNode & { parentFamilySlug: string })[] = [];
  if (activeFamily) {
    const kids = activeFamily.children.length > 0 ? activeFamily.children : [];
    kids.forEach((k) => visibleChildren.push({ ...k, parentFamilySlug: activeFamily.slug }));
  }

  return (
    <div className="graph-wrapper">
      <svg
        ref={svgRef}
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        aria-label="Flavour Atlas graph"
        style={{ overflow: "visible" }}
      >
        {/* Ambient rings */}
        <circle cx={cx} cy={cy} r={familyR} fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="3 6" opacity="0.4" />
        {activeFamily && (
          <circle cx={cx} cy={cy} r={childR} fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="2 8" opacity="0.3" />
        )}

        {/* Connector lines from centre to family nodes */}
        {families.map((fam, i) => {
          const angle = (360 / families.length) * i;
          const pos = polarToXY(cx, cy, familyR, angle);
          const isActive = fam.slug === activeFamilySlug;
          return (
            <line
              key={fam.slug + "-line"}
              x1={cx} y1={cy} x2={pos.x} y2={pos.y}
              stroke={isActive ? fam.colour : "var(--border)"}
              strokeWidth={isActive ? 1.5 : 0.75}
              strokeDasharray={isActive ? "none" : "3 5"}
              opacity={isActive ? 0.6 : 0.3}
              style={{ transition: "all 0.3s ease" }}
            />
          );
        })}

        {/* Connector lines from family to children */}
        {activeFamily && visibleChildren.map((child, i) => {
          const famAngle = (360 / families.length) * families.findIndex((f) => f.slug === activeFamily.slug);
          const spread = Math.min(80, visibleChildren.length * 18);
          const startAngle = famAngle - spread / 2;
          const childAngle = startAngle + (spread / Math.max(visibleChildren.length - 1, 1)) * i;
          const famPos = polarToXY(cx, cy, familyR, famAngle);
          const childPos = polarToXY(cx, cy, childR, childAngle);
          return (
            <line
              key={child.slug + "-cline"}
              x1={famPos.x} y1={famPos.y} x2={childPos.x} y2={childPos.y}
              stroke={activeFamily.colour}
              strokeWidth="0.75"
              opacity="0.35"
              style={{ transition: "all 0.3s ease" }}
            />
          );
        })}

        {/* Child nodes */}
        {activeFamily && visibleChildren.map((child, i) => {
          const famAngle = (360 / families.length) * families.findIndex((f) => f.slug === activeFamily.slug);
          const spread = Math.min(80, visibleChildren.length * 18);
          const startAngle = famAngle - spread / 2;
          const childAngle = startAngle + (spread / Math.max(visibleChildren.length - 1, 1)) * i;
          const pos = polarToXY(cx, cy, childR, childAngle);
          const isSelected = selectedSlugs.has(child.slug);
          return (
            <g
              key={child.slug}
              style={{ cursor: "pointer", transition: "all 0.25s ease" }}
              onClick={() => onToggle(child.slug, activeFamily.slug)}
              role="button"
              aria-label={`${child.label}, ${child.coffee_count} coffees`}
              aria-pressed={isSelected}
            >
              <circle
                cx={pos.x} cy={pos.y} r={childSz}
                fill={isSelected ? child.colour : "var(--surface)"}
                stroke={child.colour}
                strokeWidth={isSelected ? 0 : 1.5}
                opacity={isSelected ? 1 : 0.85}
                style={{ filter: isSelected ? `drop-shadow(0 0 8px ${child.colour}88)` : "none", transition: "all 0.2s ease" }}
              />
              <text
                x={pos.x} y={pos.y - 2}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={isSelected ? "#fff" : "var(--text)"}
                fontSize={Math.max(9, childSz * 0.38)}
                fontFamily="var(--font-body)"
                fontWeight={isSelected ? "600" : "400"}
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {child.label.length > 9 ? child.label.slice(0, 8) + "…" : child.label}
              </text>
              {child.coffee_count > 0 && (
                <text
                  x={pos.x} y={pos.y + childSz * 0.42}
                  textAnchor="middle"
                  fill={isSelected ? "#ffffffaa" : "var(--text-faint)"}
                  fontSize={Math.max(7, childSz * 0.28)}
                  fontFamily="var(--font-body)"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {child.coffee_count}
                </text>
              )}
            </g>
          );
        })}

        {/* Family nodes */}
        {families.map((fam, i) => {
          const angle = (360 / families.length) * i;
          const pos = polarToXY(cx, cy, familyR, angle);
          const isActive = fam.slug === activeFamilySlug;
          const isSelected = selectedSlugs.has(fam.slug);
          return (
            <g
              key={fam.slug}
              style={{ cursor: "pointer" }}
              onClick={() => onToggle(fam.slug, fam.slug)}
              role="button"
              aria-label={`${fam.label} family, ${fam.coffee_count} coffees`}
              aria-pressed={isActive}
            >
              <circle
                cx={pos.x} cy={pos.y} r={isActive ? nodeSz * 1.1 : nodeSz}
                fill={isActive || isSelected ? fam.colour : "var(--surface)"}
                stroke={fam.colour}
                strokeWidth={isActive ? 0 : 2}
                style={{
                  filter: isActive ? `drop-shadow(0 0 12px ${fam.colour}99)` : "none",
                  transition: "all 0.25s ease",
                }}
              />
              <text
                x={pos.x} y={pos.y - 1}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={isActive || isSelected ? "#fff" : "var(--text)"}
                fontSize={Math.max(10, nodeSz * 0.36)}
                fontFamily="var(--font-body)"
                fontWeight={isActive ? "600" : "500"}
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {fam.label}
              </text>
              <text
                x={pos.x} y={pos.y + nodeSz * 0.42}
                textAnchor="middle"
                fill={isActive || isSelected ? "#ffffffaa" : "var(--text-faint)"}
                fontSize={Math.max(8, nodeSz * 0.28)}
                fontFamily="var(--font-body)"
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {fam.coffee_count}
              </text>
            </g>
          );
        })}

        {/* Central node */}
        <g style={{ pointerEvents: "none" }}>
          <circle cx={cx} cy={cy} r={nodeSz * 0.85} fill="var(--surface-raised)" stroke="var(--border)" strokeWidth="1.5" />
          <text
            x={cx} y={cy - 6}
            textAnchor="middle"
            fill="var(--text)"
            fontSize={Math.max(18, nodeSz * 0.55)}
            fontFamily="var(--font-display)"
            fontWeight="300"
            fontStyle="italic"
          >
            {matchCount}
          </text>
          <text
            x={cx} y={cy + nodeSz * 0.35}
            textAnchor="middle"
            fill="var(--text-faint)"
            fontSize={Math.max(8, nodeSz * 0.24)}
            fontFamily="var(--font-body)"
            letterSpacing="0.08em"
          >
            COFFEES
          </text>
        </g>
      </svg>
    </div>
  );
}

// ── List View ─────────────────────────────────────────────────────────────────

function ListView({
  atlas,
  selectedSlugs,
  onToggle,
}: {
  atlas: AtlasResponse;
  selectedSlugs: Set<string>;
  onToggle: (slug: string, familySlug: string) => void;
}) {
  return (
    <div className="list-view">
      {atlas.families.map((fam) => (
        <div key={fam.slug} className="list-family">
          <button
            className={`list-family-btn ${selectedSlugs.has(fam.slug) ? "selected" : ""}`}
            style={{ "--fam-colour": fam.colour } as React.CSSProperties}
            onClick={() => onToggle(fam.slug, fam.slug)}
          >
            <span className="list-dot" />
            <span>{fam.label}</span>
            <span className="list-count">{fam.coffee_count}</span>
          </button>
          <div className="list-children">
            {fam.children.map((cat) => (
              <div key={cat.slug}>
                <button
                  className={`list-child-btn depth-1 ${selectedSlugs.has(cat.slug) ? "selected" : ""}`}
                  style={{ "--fam-colour": fam.colour } as React.CSSProperties}
                  onClick={() => onToggle(cat.slug, fam.slug)}
                >
                  {cat.label}
                  <span className="list-count">{cat.coffee_count}</span>
                </button>
                {cat.children.map((tag) => (
                  <button
                    key={tag.slug}
                    className={`list-child-btn depth-2 ${selectedSlugs.has(tag.slug) ? "selected" : ""}`}
                    style={{ "--fam-colour": fam.colour } as React.CSSProperties}
                    onClick={() => onToggle(tag.slug, fam.slug)}
                  >
                    {tag.label}
                    <span className="list-count">{tag.coffee_count}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Coffee Result Card ────────────────────────────────────────────────────────

function CoffeeResultCard({ coffee, selectedSlugs }: { coffee: MatchedCoffee; selectedSlugs: Set<string> }) {
  const matchedLabels = coffee.matched_tags
    .filter((t) => [...selectedSlugs].some((s) => t.slug === s || t.slug.startsWith(s + ".")))
    .map((t) => t.label)
    .slice(0, 4);

  return (
    <Link href={`/coffees/${coffee.id}`} className="result-card">
      <div className="result-origin">
        {[coffee.origin_country, coffee.origin_region].filter(Boolean).join(" · ")}
      </div>
      <h3 className="result-name">{coffee.canonical_name}</h3>
      <div className="result-meta">
        {coffee.process && <span className="result-process">{coffee.process}</span>}
        {coffee.roast_level && <span className="result-roast">{coffee.roast_level} roast</span>}
      </div>
      <div className="result-tags">
        {matchedLabels.map((l) => (
          <span key={l} className="result-tag">{l}</span>
        ))}
      </div>
    </Link>
  );
}

// ── Utility ───────────────────────────────────────────────────────────────────

function findNode(families: AtlasNode[], slug: string): AtlasNode | null {
  for (const f of families) {
    if (f.slug === slug) return f;
    for (const c of f.children) {
      if (c.slug === slug) return c;
      for (const t of c.children) {
        if (t.slug === slug) return t;
      }
    }
  }
  return null;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const atlasStyles = `
  .atlas-root {
    min-height: 100vh;
    background: var(--bg);
    padding: 0 0 120px;
  }

  /* Header */
  .atlas-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    padding: 56px 32px 32px;
    max-width: 900px;
    margin: 0 auto;
  }
  .atlas-header-inner {}
  .atlas-eyebrow {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 8px;
  }
  .atlas-title {
    font-family: var(--font-display);
    font-size: clamp(32px, 6vw, 56px);
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0 0 8px;
    line-height: 1.1;
  }
  .atlas-subtitle {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
  }

  /* Controls */
  .atlas-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mode-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .mode-btn:hover { border-color: var(--accent); color: var(--accent); }
  .mode-btn.active { background: var(--text); color: var(--bg); border-color: var(--text); }
  .clear-btn {
    padding: 8px 14px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-faint);
    font-family: var(--font-body);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .clear-btn:hover { border-color: #e05c3a; color: #e05c3a; }

  /* Graph */
  .graph-wrapper {
    max-width: 640px;
    margin: 0 auto;
    padding: 0 24px;
    touch-action: manipulation;
  }

  /* Loading bloom */
  .atlas-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 24px;
    min-height: 360px;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 14px;
  }
  .loading-bloom {
    position: relative;
    width: 80px;
    height: 80px;
  }
  .loading-petal {
    position: absolute;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
    top: 50%;
    left: 50%;
    transform-origin: -20px 0;
    animation: bloom-spin 1.4s ease-in-out infinite;
    animation-delay: calc(var(--i) * 0.175s);
    opacity: 0;
  }
  @keyframes bloom-spin {
    0% { opacity: 0; transform: rotate(calc(var(--i) * 45deg)) translateX(30px) scale(0.4); }
    40% { opacity: 1; }
    100% { opacity: 0; transform: rotate(calc(var(--i) * 45deg + 360deg)) translateX(30px) scale(1); }
  }

  .atlas-error {
    text-align: center;
    color: var(--text-muted);
    padding: 64px 32px;
    font-family: var(--font-body);
  }

  /* Chip strip */
  .atlas-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    max-width: 900px;
    margin: 16px auto 0;
    padding: 0 32px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 100px;
    border: none;
    background: color-mix(in srgb, var(--chip-colour) 18%, var(--surface));
    color: var(--chip-colour);
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .chip:hover { opacity: 0.7; }
  .chip-x { opacity: 0.6; font-size: 15px; line-height: 1; }

  /* Results */
  .atlas-results {
    max-width: 900px;
    margin: 40px auto 0;
    padding: 0 32px;
  }
  .results-header {
    margin-bottom: 20px;
  }
  .results-title {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 400;
    font-style: italic;
    color: var(--text);
    margin: 0;
  }
  .results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
  }
  .results-skeleton {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
  }
  .skeleton-card {
    height: 140px;
    border-radius: 12px;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  .empty-results {
    padding: 48px 0;
    text-align: center;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 15px;
  }
  .empty-hint {
    font-size: 13px;
    color: var(--text-faint);
    margin-top: 6px;
  }

  /* Result card */
  .result-card {
    display: block;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 20px;
    text-decoration: none;
    transition: border-color 0.18s, transform 0.18s, box-shadow 0.18s;
  }
  .result-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
  }
  .result-origin {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 6px;
  }
  .result-name {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 400;
    font-style: italic;
    color: var(--text);
    margin: 0 0 10px;
    line-height: 1.2;
  }
  .result-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }
  .result-process, .result-roast {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    text-transform: capitalize;
    background: var(--surface-raised);
    padding: 2px 8px;
    border-radius: 100px;
  }
  .result-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .result-tag {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--accent);
    background: var(--accent-dim);
    padding: 2px 8px;
    border-radius: 100px;
  }

  /* Load more */
  .load-more {
    display: block;
    margin: 32px auto 0;
    padding: 12px 32px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .load-more:hover { border-color: var(--accent); color: var(--accent); }

  /* Onboarding */
  .atlas-onboarding {
    max-width: 480px;
    margin: 0 auto;
    padding: 32px 32px 0;
    text-align: center;
    color: var(--text-faint);
    font-family: var(--font-body);
    font-size: 14px;
    line-height: 1.6;
  }
  .onboarding-line {
    width: 1px;
    height: 40px;
    background: var(--border);
    margin: 0 auto 20px;
  }

  /* List view */
  .list-view {
    max-width: 640px;
    margin: 16px auto 0;
    padding: 0 32px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .list-family {
    border: 1px solid var(--border-light);
    border-radius: 10px;
    overflow: hidden;
    background: var(--surface);
  }
  .list-family-btn {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    background: transparent;
    border: none;
    color: var(--text);
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s;
  }
  .list-family-btn:hover { background: var(--surface-raised); }
  .list-family-btn.selected { background: color-mix(in srgb, var(--fam-colour) 15%, var(--surface)); }
  .list-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--fam-colour);
    flex-shrink: 0;
  }
  .list-count {
    margin-left: auto;
    font-size: 12px;
    color: var(--text-faint);
    font-weight: 400;
  }
  .list-children {
    padding: 0 16px 8px 36px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .list-child-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 100px;
    border: 1px solid var(--border-light);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .list-child-btn:hover { border-color: var(--fam-colour); color: var(--text); }
  .list-child-btn.selected {
    background: color-mix(in srgb, var(--fam-colour) 20%, var(--surface));
    border-color: var(--fam-colour);
    color: var(--text);
  }
  .depth-2 { font-size: 12px; }

  /* Mobile */
  @media (max-width: 600px) {
    .atlas-header { padding: 32px 20px 24px; }
    .atlas-chips, .atlas-results, .atlas-onboarding, .list-view { padding: 0 20px; }
    .graph-wrapper { padding: 0 12px; }
    .results-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
    .result-card { padding: 14px; }
    .result-name { font-size: 15px; }
  }
  @media (max-width: 400px) {
    .results-grid { grid-template-columns: 1fr; }
  }
`;
