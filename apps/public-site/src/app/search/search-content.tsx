"use client";

/**
 * /search — Natural language search page.
 *
 * Flow:
 * 1. User types a query and submits
 * 2. POST /api/v1/search/interpret → parsed query + ranked results
 * 3. Show interpretation summary + results with match reasons
 * 4. Fallback gracefully if API fails
 */

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import NaturalSearchBox from "@/components/NaturalSearchBox";
import { ExplanationBlurb } from "@/components/ExplanationBlurb";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ParsedQuery {
  flavour_notes: string[];
  roast_level: string | null;
  process: string | null;
  origin_country: string | null;
  origin_region: string | null;
  max_price: number | null;
  min_price: number | null;
  espresso_suitable: boolean | null;
  filter_suitable: boolean | null;
  body_signal: string | null;
  acidity_signal: string | null;
  decaf: boolean | null;
  summary: string;
  source: string;
}

interface CoffeeMatch {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  process: string | null;
  roast_level: string | null;
  flavour_notes: string[];
  min_price_gbp: number | null;
  listing_count: number;
  data_completeness_score: number;
  match_score: number;
  match_reasons: string[];
}

interface SearchResponse {
  query: string;
  parsed: ParsedQuery;
  summary: string;
  source: string;
  results: CoffeeMatch[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c",
  natural: "#c4763a",
  honey: "#d4a03a",
  anaerobic: "#8b6bab",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SearchPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialQ = searchParams.get("q") ?? "";

  const [query, setQuery] = useState(initialQ);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const abortRef = useRef<AbortController | null>(null);

  const runSearch = useCallback(async (q: string, pg = 1) => {
    if (!q.trim()) { setResponse(null); return; }

    // Cancel previous request
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/search/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, page: pg, page_size: 12, use_llm: true }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: SearchResponse = await res.json();
      if (pg === 1) {
        setResponse(data);
      } else {
        setResponse((prev) =>
          prev ? { ...data, results: [...prev.results, ...data.results] } : data
        );
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") return;
      setError("Search failed. Please try again.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Run search when URL query changes
  useEffect(() => {
    const q = searchParams.get("q") ?? "";
    setQuery(q);
    setPage(1);
    if (q) runSearch(q, 1);
    else setResponse(null);
  }, [searchParams, runSearch]);

  const loadMore = useCallback(() => {
    const next = page + 1;
    setPage(next);
    runSearch(query, next);
  }, [page, query, runSearch]);

  return (
    <div className="search-root">
      {/* ── Search header ── */}
      <div className="search-header">
        <div className="search-header-inner">
          <p className="search-eyebrow">Natural language search</p>
          <h1 className="search-title">Find your cup</h1>
          <p className="search-hint">Describe what you're looking for. Origin, flavour, brew method, price — anything.</p>
        </div>
        <div className="search-box-wrap">
          <NaturalSearchBox variant="page" initialValue={query} autoFocus={!query} />
        </div>
      </div>

      {/* ── States ── */}
      {loading && page === 1 && <SearchSkeleton />}

      {error && (
        <div className="search-error">
          <p>{error}</p>
          <button onClick={() => runSearch(query, 1)}>Try again</button>
        </div>
      )}

      {!loading && !error && response && (
        <>
          {/* Interpretation summary */}
          <InterpretationBanner response={response} />

          {/* Results */}
          {response.results.length === 0 ? (
            <EmptyResults query={query} />
          ) : (
            <>
              <div className="results-header">
                <span className="results-count">
                  {response.total} coffee{response.total !== 1 ? "s" : ""} match
                </span>
                {response.source === "fallback" && (
                  <span className="fallback-badge">Rules mode</span>
                )}
              </div>
              <div className="results-grid">
                {response.results.map((coffee, i) => (
                  <CoffeeMatchCard key={coffee.id} coffee={coffee} rank={i + 1} query={query} />
                ))}
              </div>
              {response.has_next && (
                <button
                  className="load-more"
                  onClick={loadMore}
                  disabled={loading}
                >
                  {loading ? "Loading…" : "Load more"}
                </button>
              )}
            </>
          )}
        </>
      )}

      {!loading && !error && !response && !query && <EmptyState />}

      <style jsx>{pageStyles}</style>
    </div>
  );
}

// ── Interpretation banner ─────────────────────────────────────────────────────

function InterpretationBanner({ response }: { response: SearchResponse }) {
  const p = response.parsed;
  const tags: { label: string; colour: string }[] = [];

  if (p.roast_level) tags.push({ label: `${p.roast_level} roast`, colour: "#c4763a" });
  if (p.process) tags.push({ label: p.process, colour: "#6b9e8c" });
  if (p.origin_country) tags.push({ label: p.origin_country, colour: "#8b6bab" });
  if (p.espresso_suitable) tags.push({ label: "espresso", colour: "#c4763a" });
  if (p.filter_suitable) tags.push({ label: "filter", colour: "#6b9e8c" });
  if (p.max_price) tags.push({ label: `under £${p.max_price}`, colour: "#d4a84b" });
  if (p.min_price) tags.push({ label: `over £${p.min_price}`, colour: "#d4a84b" });
  if (p.decaf) tags.push({ label: "decaf", colour: "#a07850" });
  if (p.body_signal) tags.push({ label: `${p.body_signal} body`, colour: "#888" });
  if (p.acidity_signal) tags.push({ label: `${p.acidity_signal} acidity`, colour: "#888" });
  p.flavour_notes.slice(0, 4).forEach((note) =>
    tags.push({ label: note, colour: "#e05c3a" })
  );

  return (
    <div className="interp-banner">
      <div className="interp-inner">
        <div className="interp-left">
          <span className="interp-label">Understood as</span>
          <p className="interp-summary">{response.summary}</p>
        </div>
        {tags.length > 0 && (
          <div className="interp-tags">
            {tags.map((t) => (
              <span
                key={t.label}
                className="interp-tag"
                style={{ "--tag-colour": t.colour } as React.CSSProperties}
              >
                {t.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Coffee match card ─────────────────────────────────────────────────────────

function CoffeeMatchCard({ coffee, rank, query }: { coffee: CoffeeMatch; rank: number; query: string }) {
  const processColour = PROCESS_COLORS[coffee.process ?? ""] ?? "var(--border)";

  return (
    <Link href={`/coffees/${coffee.id}`} className="match-card">
      {/* Rank */}
      <span className="match-rank">#{rank}</span>

      {/* Process pill */}
      {coffee.process && (
        <span
          className="match-process"
          style={{ background: processColour + "22", color: processColour }}
        >
          {coffee.process}
        </span>
      )}

      <div className="match-origin">
        {[coffee.origin_country, coffee.origin_region].filter(Boolean).join(" · ")}
      </div>
      <h3 className="match-name">{coffee.canonical_name}</h3>

      {/* Flavour notes */}
      {coffee.flavour_notes.length > 0 && (
        <div className="match-notes">
          {coffee.flavour_notes.slice(0, 4).map((n) => (
            <span key={n} className="match-note">{n}</span>
          ))}
        </div>
      )}

      {/* Why this matches */}
      {coffee.match_reasons.length > 0 && (
        <div className="match-reasons">
          <span className="match-reasons-label">Matches: </span>
          {coffee.match_reasons.join(" · ")}
        </div>
      )}

      <ExplanationBlurb
        type="search"
        params={{ q: query, coffeeId: coffee.id }}
        showSkeleton={false}
        className="match-explanation"
      />

      <div className="match-footer">
        {coffee.min_price_gbp != null && (
          <span className="match-price">from £{coffee.min_price_gbp.toFixed(2)}</span>
        )}
        {coffee.roast_level && (
          <span className="match-roast">{coffee.roast_level} roast</span>
        )}
      </div>
    </Link>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SearchSkeleton() {
  return (
    <div className="skeleton-wrap">
      <div className="skeleton-banner" />
      <div className="results-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </div>
    </div>
  );
}

// ── Empty results ─────────────────────────────────────────────────────────────

function EmptyResults({ query }: { query: string }) {
  return (
    <div className="empty-results">
      <div className="empty-icon">☕</div>
      <h3>No matches for "{query}"</h3>
      <p>Try broadening your search — remove price or origin constraints, or describe the flavour differently.</p>
      <div className="empty-suggestions">
        {["fruity and bright", "chocolatey espresso", "clean light roast"].map((s) => (
          <Link key={s} href={`/search?q=${encodeURIComponent(s)}`} className="empty-chip">
            {s}
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-state-line" />
      <p>
        Type anything — a flavour, a brew method, a mood.<br />
        <span style={{ color: "var(--text-faint)", fontSize: "13px" }}>
          "Something like a good Burgundy" works too.
        </span>
      </p>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const pageStyles = `
  .search-root {
    min-height: 100vh;
    background: var(--bg);
    padding-bottom: 120px;
  }

  /* Header */
  .search-header {
    padding: 48px 32px 36px;
    max-width: 880px;
    margin: 0 auto;
  }
  .search-eyebrow {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 8px;
  }
  .search-title {
    font-family: var(--font-display);
    font-size: clamp(28px, 5vw, 48px);
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0 0 8px;
    line-height: 1.1;
  }
  .search-hint {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-muted);
    margin: 0 0 24px;
  }
  .search-box-wrap {
    width: 100%;
  }

  /* Interpretation banner */
  .interp-banner {
    max-width: 880px;
    margin: 0 auto 24px;
    padding: 0 32px;
  }
  .interp-inner {
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 18px 20px;
    display: flex;
    gap: 20px;
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .interp-left { flex: 1; min-width: 200px; }
  .interp-label {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    display: block;
    margin-bottom: 4px;
  }
  .interp-summary {
    font-family: var(--font-display);
    font-size: 17px;
    font-style: italic;
    font-weight: 400;
    color: var(--text);
    margin: 0;
    line-height: 1.4;
  }
  .interp-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    padding-top: 2px;
  }
  .interp-tag {
    font-family: var(--font-body);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 100px;
    background: color-mix(in srgb, var(--tag-colour) 15%, var(--surface));
    color: var(--tag-colour);
    font-weight: 500;
    text-transform: capitalize;
  }

  /* Results */
  .results-header {
    max-width: 880px;
    margin: 0 auto 16px;
    padding: 0 32px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .results-count {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-muted);
  }
  .fallback-badge {
    font-family: var(--font-body);
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 100px;
    background: var(--surface-raised);
    color: var(--text-faint);
    border: 1px solid var(--border-light);
  }
  .results-grid {
    max-width: 880px;
    margin: 0 auto;
    padding: 0 32px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 14px;
  }

  /* Match card */
  .match-card {
    position: relative;
    display: block;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 14px;
    padding: 20px;
    text-decoration: none;
    transition: border-color 0.18s, transform 0.18s, box-shadow 0.18s;
  }
  .match-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.07);
  }
  .match-rank {
    position: absolute;
    top: 12px;
    right: 14px;
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    font-weight: 500;
  }
  .match-process {
    display: inline-block;
    font-family: var(--font-body);
    font-size: 10px;
    font-weight: 500;
    text-transform: capitalize;
    padding: 2px 8px;
    border-radius: 100px;
    margin-bottom: 8px;
    letter-spacing: 0.04em;
  }
  .match-origin {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 5px;
  }
  .match-name {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 400;
    font-style: italic;
    color: var(--text);
    margin: 0 0 10px;
    line-height: 1.2;
    padding-right: 24px;
  }
  .match-notes {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-bottom: 10px;
  }
  .match-note {
    font-family: var(--font-body);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 100px;
    background: var(--surface-raised);
    color: var(--text-muted);
    text-transform: capitalize;
  }
  .match-reasons {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--accent);
    margin-bottom: 10px;
    line-height: 1.4;
  }
  .match-reasons-label {
    color: var(--text-faint);
  }
  .match-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: auto;
    padding-top: 10px;
    border-top: 1px solid var(--border-light);
  }
  .match-price {
    font-family: var(--font-body);
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
  }
  .match-roast {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    text-transform: capitalize;
  }

  /* Skeleton */
  .skeleton-wrap { max-width: 880px; margin: 0 auto; padding: 0 32px; }
  .skeleton-banner {
    height: 80px;
    border-radius: 12px;
    background: var(--surface);
    margin-bottom: 24px;
    animation: shimmer 1.4s ease-in-out infinite;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
  }
  .skeleton-card {
    height: 180px;
    border-radius: 14px;
    animation: shimmer 1.4s ease-in-out infinite;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  /* Empty */
  .empty-results {
    max-width: 480px;
    margin: 48px auto;
    padding: 0 32px;
    text-align: center;
  }
  .empty-icon { font-size: 36px; margin-bottom: 16px; }
  .empty-results h3 {
    font-family: var(--font-display);
    font-size: 22px;
    font-style: italic;
    font-weight: 400;
    color: var(--text);
    margin: 0 0 10px;
  }
  .empty-results p {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-muted);
    margin: 0 0 20px;
    line-height: 1.6;
  }
  .empty-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
  .empty-chip {
    padding: 7px 14px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 13px;
    text-decoration: none;
    transition: border-color 0.15s, color 0.15s;
  }
  .empty-chip:hover { border-color: var(--accent); color: var(--accent); }

  .empty-state {
    max-width: 480px;
    margin: 0 auto;
    padding: 32px 32px 0;
    text-align: center;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 15px;
    line-height: 1.7;
  }
  .empty-state-line {
    width: 1px;
    height: 40px;
    background: var(--border);
    margin: 0 auto 20px;
  }

  .match-explanation {
    font-size: 12px !important;
    margin-top: 4px !important;
    color: var(--text-faint) !important;
    font-style: italic;
  }
  /* Load more */
  .load-more {
    display: block;
    margin: 28px auto 0;
    padding: 11px 32px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .load-more:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .load-more:disabled { opacity: 0.5; cursor: default; }

  /* Error */
  .search-error {
    max-width: 480px;
    margin: 32px auto;
    padding: 20px 32px;
    text-align: center;
    color: var(--text-muted);
    font-family: var(--font-body);
    font-size: 14px;
  }
  .search-error button {
    margin-top: 12px;
    padding: 8px 20px;
    border-radius: 100px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 13px;
  }

  @media (max-width: 600px) {
    .search-header { padding: 32px 20px 24px; }
    .interp-banner, .results-header, .results-grid, .skeleton-wrap { padding: 0 20px; }
    .results-grid { grid-template-columns: 1fr; }
  }
`;
