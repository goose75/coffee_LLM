"use client";

/**
 * Grounds Homepage — Redesigned
 *
 * Aesthetic direction: Editorial Stillness
 * Inspiration: Wallpaper* magazine meets a specialty coffee menu card.
 * One large typographic hero. Restrained sections that open into depth.
 * The page breathes. White space is the primary design element.
 *
 * Structure:
 *   1. Hero — one strong statement + smart search
 *   2. Flavour Atlas preview — the centrepiece interaction teaser
 *   3. New releases — horizontal scroll, editorial card treatment
 *   4. Origin highlights — three featured origins with flavour strips
 *   5. Roaster strip — compact but dignified
 *   6. How it works — three lines, no more
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PROCESS_COLOURS: Record<string, string> = {
  washed: "#6b9e8c", natural: "#c4763a", honey: "#d4a84b",
  anaerobic: "#8b6bab", wet_hulled: "#5a7fa8",
};

const FAMILY_COLOURS: Record<string, string> = {
  fruity: "#e05c3a", floral: "#c084c0", sweet: "#d4a84b",
  chocolate: "#7c4b2a", nutty: "#a07850", earthy: "#6b7c4a",
  fermented: "#8b6bab", spice: "#c47820",
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface Coffee {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  process: string | null;
  roast_level: string | null;
  flavour_notes: string[];
  min_price_gbp: number | null;
  newest_listing_at: string | null;
}

interface Roaster {
  id: string;
  name: string;
  domain: string;
  uk_region: string | null;
  listing_count: number;
}

interface OriginSummary {
  country: string;
  emoji: string;
  coffee_count: number;
  top_flavour_families: { slug: string; label: string; colour: string; count: number }[];
  dominant_process: string | null;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [newReleases, setNewReleases] = useState<Coffee[]>([]);
  const [roasters, setRoasters] = useState<Roaster[]>([]);
  const [origins, setOrigins] = useState<OriginSummary[]>([]);
  const [totalCoffees, setTotalCoffees] = useState<number>(0);
  const [totalRoasters, setTotalRoasters] = useState<number>(0);

  useEffect(() => {
    // Fetch in parallel, degrade gracefully
    fetch(`${API_BASE}/api/v1/new-releases?days=21&page=1&page_size=8`)
      .then(r => r.json()).then(d => setNewReleases(d.data ?? [])).catch(() => {});

    fetch(`${API_BASE}/api/v1/roasters?page=1&page_size=6`)
      .then(r => r.json()).then(d => {
        setRoasters(d.data ?? []);
        setTotalRoasters(d.total ?? 0);
      }).catch(() => {});

    fetch(`${API_BASE}/api/v1/coffees?page_size=1`)
      .then(r => r.json()).then(d => setTotalCoffees(d.total ?? 0)).catch(() => {});

    fetch(`${API_BASE}/api/v1/origins`)
      .then(r => r.json()).then(d => {
        setOrigins((d.origins ?? []).slice(0, 6));
      }).catch(() => {});
  }, []);

  return (
    <div className="hp-root">

      {/* ── 1. Hero ─────────────────────────────────────────────────────── */}
      <HeroSection totalCoffees={totalCoffees} totalRoasters={totalRoasters} />

      {/* ── 3. New releases ─────────────────────────────────────────────── */}
      {newReleases.length > 0 && <NewReleasesSection coffees={newReleases} />}

      {/* ── 4. Origin highlights ────────────────────────────────────────── */}
      {origins.length > 0 && <OriginHighlights origins={origins} />}

      {/* ── 5. Roaster strip ────────────────────────────────────────────── */}
      {roasters.length > 0 && <RoasterStrip roasters={roasters} total={totalRoasters} />}

      {/* ── 6. How it works ─────────────────────────────────────────────── */}
      <HowItWorks />

      <style jsx>{styles}</style>
    </div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────

function HeroSection({ totalCoffees, totalRoasters }: { totalCoffees: number; totalRoasters: number }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const PLACEHOLDERS = [
    "something juicy and floral for V60…",
    "chocolatey espresso under £12…",
    "clean washed Kenya…",
    "bright Ethiopian natural…",
    "syrupy and full-bodied…",
  ];
  const [phIdx, setPhIdx] = useState(0);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    const iv = setInterval(() => {
      if (!focused && !query) setPhIdx(i => (i + 1) % PLACEHOLDERS.length);
    }, 3000);
    return () => clearInterval(iv);
  }, [focused, query]);

  const submit = () => {
    const q = query.trim();
    if (q) router.push(`/search?q=${encodeURIComponent(q)}`);
    else router.push("/flavour-atlas");
  };

  return (
    <section className="hero-section">
      {/* Wordmark area */}
      <div className="hero-wordmark">
        <span className="hero-eyebrow">UK Specialty Coffee</span>
      </div>

      {/* Large headline */}
      <div className="hero-headline-wrap">
        <h1 className="hero-headline">
          Discover coffee<br />
          by <em className="hero-headline-em">flavour.</em>
        </h1>
        {(totalCoffees > 0 || totalRoasters > 0) && (
          <div className="hero-stats">
            {totalCoffees > 0 && (
              <span className="hero-stat">
                <span className="hero-stat-n">{totalCoffees}</span>
                <span className="hero-stat-l">coffees</span>
              </span>
            )}
            {totalRoasters > 0 && (
              <span className="hero-stat">
                <span className="hero-stat-n">{totalRoasters}+</span>
                <span className="hero-stat-l">roasters</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Smart search */}
      <div className={`hero-search ${focused ? "hero-search-focused" : ""}`}>
        <svg className="hero-search-icon" width="16" height="16" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" /><path d="M16.5 16.5L21 21" />
        </svg>
        <input
          ref={inputRef}
          className="hero-search-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={e => e.key === "Enter" && submit()}
          placeholder={PLACEHOLDERS[phIdx]}
          aria-label="Describe the coffee you're looking for"
          autoComplete="off"
        />
        <button className="hero-search-btn" onClick={submit}>
          {query ? "Search" : "Explore"}
        </button>
      </div>

      {/* Quick links */}
      <div className="hero-links">
        {[
          { href: "/flavour-atlas", label: "Flavour Atlas" },
          { href: "/origins", label: "Origins" },
          { href: "/coffees", label: "Browse all" },
          { href: "/new-releases", label: "New releases" },
        ].map(({ href, label }) => (
          <Link key={href} href={href} className="hero-link">{label}</Link>
        ))}
      </div>
    </section>
  );
}

// ── Flavour Atlas Teaser ──────────────────────────────────────────────────────

function FlavourAtlasTeaser() {
  const families = [
    { slug: "fruity",    label: "Fruity",    colour: "#e05c3a", w: 28 },
    { slug: "sweet",     label: "Sweet",     colour: "#d4a84b", w: 22 },
    { slug: "chocolate", label: "Chocolate", colour: "#7c4b2a", w: 16 },
    { slug: "fermented", label: "Fermented", colour: "#8b6bab", w: 14 },
    { slug: "floral",    label: "Floral",    colour: "#c084c0", w: 10 },
    { slug: "nutty",     label: "Nutty",     colour: "#a07850", w: 8 },
    { slug: "earthy",    label: "Earthy",    colour: "#6b7c4a", w: 5 },
  ];

  return (
    <section className="atlas-teaser">
      <div className="atlas-teaser-inner">
        <div className="atlas-teaser-text">
          <span className="section-eyebrow">Flavour Atlas</span>
          <h2 className="section-title">Explore by taste,<br />not filter.</h2>
          <p className="atlas-teaser-body">
            Select a flavour family. Reveal sub-notes. Discover matching coffees.
            A different way to browse.
          </p>
          <Link href="/flavour-atlas" className="atlas-teaser-cta">
            Open Flavour Atlas →
          </Link>
        </div>

        <Link href="/flavour-atlas" className="atlas-teaser-visual" aria-label="Open Flavour Atlas">
          {/* Orbital preview — simplified static version */}
          <div className="atlas-orbit">
            <div className="atlas-centre">
              <span className="atlas-centre-n">{families.reduce((s,f)=>s+f.w,0)}</span>
              <span className="atlas-centre-l">coffees</span>
            </div>
            {families.map((f, i) => {
              const angle = (360 / families.length) * i - 90;
              const rad = angle * Math.PI / 180;
              const r = 72;
              const x = 50 + r * Math.cos(rad);
              const y = 50 + r * Math.sin(rad);
              return (
                <div
                  key={f.slug}
                  className="atlas-node"
                  style={{
                    left: `${x}%`, top: `${y}%`,
                    background: f.colour,
                    width: Math.max(28, f.w * 1.2) + "px",
                    height: Math.max(28, f.w * 1.2) + "px",
                    fontSize: Math.max(8, f.w * 0.35) + "px",
                    opacity: 0.75 + (f.w / 28) * 0.25,
                  }}
                  title={f.label}
                >
                  {f.label.slice(0, 3)}
                </div>
              );
            })}
          </div>
        </Link>
      </div>
    </section>
  );
}

// ── New Releases ──────────────────────────────────────────────────────────────

function NewReleasesSection({ coffees }: { coffees: Coffee[] }) {
  return (
    <section className="releases-section">
      <div className="releases-header">
        <div>
          <span className="section-eyebrow">Just landed</span>
          <h2 className="section-title-sm">New releases</h2>
        </div>
        <Link href="/new-releases" className="section-see-all">See all →</Link>
      </div>

      <div className="releases-scroll">
        {coffees.slice(0, 8).map((c) => {
          const pc = PROCESS_COLOURS[c.process ?? ""] ?? "var(--border)";
          return (
            <Link key={c.id} href={`/coffees/${c.id}`} className="release-card">
              <div className="release-card-bar" style={{ background: pc }} />
              <div className="release-card-body">
                <span className="release-card-origin">
                  {[c.origin_country, c.origin_region].filter(Boolean).join(" · ") || "—"}
                </span>
                <h3 className="release-card-name">{c.canonical_name}</h3>
                <div className="release-card-notes">
                  {c.flavour_notes.slice(0, 2).map(n => (
                    <span key={n} className="release-card-note">{n}</span>
                  ))}
                </div>
                {c.min_price_gbp != null && (
                  <span className="release-card-price">from £{c.min_price_gbp.toFixed(2)}</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

// ── Origin Highlights ─────────────────────────────────────────────────────────

function OriginHighlights({ origins }: { origins: OriginSummary[] }) {
  return (
    <section className="origins-section">
      <div className="origins-header">
        <div>
          <span className="section-eyebrow">By origin</span>
          <h2 className="section-title-sm">Where coffee grows</h2>
        </div>
        <Link href="/origins" className="section-see-all">Explore →</Link>
      </div>

      <div className="origins-grid">
        {origins.slice(0, 6).map((o) => {
          const maxFam = Math.max(1, ...o.top_flavour_families.map(f => f.count));
          return (
            <Link key={o.country} href={`/origins?country=${encodeURIComponent(o.country)}`} className="origin-tile">
              <div className="origin-tile-top">
                <span className="origin-tile-emoji">{o.emoji}</span>
                <span className="origin-tile-name">{o.country}</span>
                <span className="origin-tile-count">{o.coffee_count}</span>
              </div>
              {/* Flavour strip */}
              <div className="origin-tile-strip">
                {o.top_flavour_families.map(f => (
                  <div
                    key={f.slug}
                    className="origin-tile-band"
                    style={{ flex: f.count, background: f.colour }}
                    title={f.label}
                  />
                ))}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

// ── Roaster Strip ─────────────────────────────────────────────────────────────

function RoasterStrip({ roasters, total }: { roasters: Roaster[]; total: number }) {
  return (
    <section className="roasters-section">
      <div className="roasters-header">
        <div>
          <span className="section-eyebrow">Roasters</span>
          <h2 className="section-title-sm">UK's finest</h2>
        </div>
        <Link href="/roasters" className="section-see-all">All {total}+ →</Link>
      </div>

      <div className="roasters-strip">
        {roasters.map(r => (
          <Link key={r.id} href={`/roasters/${r.id}`} className="roaster-pill">
            <span className="roaster-pill-avatar">{r.name.charAt(0)}</span>
            <span className="roaster-pill-name">{r.name}</span>
            {r.uk_region && <span className="roaster-pill-region">{r.uk_region}</span>}
          </Link>
        ))}
      </div>
    </section>
  );
}

// ── How It Works ──────────────────────────────────────────────────────────────

function HowItWorks() {
  const steps = [
    { n: "01", title: "We track", body: "Prices and new releases across UK specialty roasters, updated daily." },
    { n: "02", title: "You discover", body: "Browse by flavour, origin, process, or describe what you want in plain language." },
    { n: "03", title: "Then compare", body: "Side-by-side comparisons with price-per-100g, brew fit, and sensory profiles." },
  ];

  return (
    <section className="hiw-section">
      <span className="section-eyebrow">How it works</span>
      <div className="hiw-grid">
        {steps.map(s => (
          <div key={s.n} className="hiw-step">
            <span className="hiw-n">{s.n}</span>
            <h3 className="hiw-title">{s.title}</h3>
            <p className="hiw-body">{s.body}</p>
          </div>
        ))}
      </div>
      <div className="hiw-footer">
        <Link href="/methodology" className="hiw-link">About Grounds →</Link>
      </div>
    </section>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = `
  .hp-root {
    min-height: 100vh;
    background: var(--bg);
  }

  /* ── Shared ── */
  .section-eyebrow {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-faint);
    display: block;
    margin-bottom: 6px;
  }
  .section-title {
    font-family: var(--font-display);
    font-size: clamp(26px, 5vw, 40px);
    font-weight: 300;
    font-style: italic;
    color: var(--text);
    margin: 0;
    line-height: 1.15;
  }
  .section-title-sm {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 400;
    font-style: italic;
    color: var(--text);
    margin: 0;
    line-height: 1.2;
  }
  .section-see-all {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--accent);
    text-decoration: none;
    letter-spacing: 0.04em;
    transition: opacity 0.15s;
    flex-shrink: 0;
  }
  .section-see-all:hover { opacity: 0.7; }

  /* ── Hero ── */
  .hero-section {
    padding: 52px 28px 40px;
    max-width: 640px;
    margin: 0 auto;
  }
  .hero-wordmark {
    margin-bottom: 28px;
  }
  .hero-eyebrow {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .hero-headline-wrap {
    margin-bottom: 32px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
  }
  .hero-headline {
    font-family: var(--font-display);
    font-size: clamp(40px, 10vw, 72px);
    font-weight: 300;
    line-height: 1.05;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.02em;
  }
  .hero-headline-em {
    color: var(--accent);
    font-style: italic;
  }
  .hero-stats {
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-align: right;
    flex-shrink: 0;
  }
  .hero-stat {
    display: flex;
    flex-direction: column;
    gap: 1px;
    align-items: flex-end;
  }
  .hero-stat-n {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 400;
    color: var(--text);
    line-height: 1;
  }
  .hero-stat-l {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-faint);
  }

  /* Hero search */
  .hero-search {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 16px;
    padding: 0 6px 0 16px;
    margin-bottom: 20px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .hero-search-focused {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-dim);
  }
  .hero-search-icon {
    color: var(--text-faint);
    flex-shrink: 0;
  }
  .hero-search-input {
    flex: 1;
    border: none;
    background: transparent;
    color: var(--text);
    font-family: var(--font-body);
    font-size: 15px;
    padding: 14px 0;
    outline: none;
    min-width: 0;
  }
  .hero-search-input::placeholder {
    color: var(--text-faint);
    font-style: italic;
  }
  .hero-search-btn {
    padding: 8px 16px;
    border: none;
    border-radius: 10px;
    background: var(--accent);
    color: white;
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    margin: 5px 0;
    flex-shrink: 0;
    transition: background 0.15s;
  }
  .hero-search-btn:hover { background: var(--accent-light); }

  /* Hero quick links */
  .hero-links {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .hero-link {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-muted);
    text-decoration: none;
    padding: 6px 13px;
    border-radius: 100px;
    border: 1px solid var(--border-light);
    transition: border-color 0.15s, color 0.15s;
  }
  .hero-link:hover { border-color: var(--accent); color: var(--accent); }

  /* ── Flavour Atlas teaser ── */
  .atlas-teaser {
    padding: 0 28px 48px;
    max-width: 640px;
    margin: 0 auto;
  }
  .atlas-teaser-inner {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
    align-items: center;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 20px;
    padding: 28px;
  }
  .atlas-teaser-body {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 10px 0 16px;
  }
  .atlas-teaser-cta {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--accent);
    text-decoration: none;
    font-weight: 500;
    transition: opacity 0.15s;
  }
  .atlas-teaser-cta:hover { opacity: 0.7; }

  /* Orbit visual */
  .atlas-teaser-visual {
    display: block;
    text-decoration: none;
  }
  .atlas-orbit {
    position: relative;
    width: 100%;
    padding-bottom: 100%;
  }
  .atlas-centre {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 44px; height: 44px;
    border-radius: 50%;
    background: var(--surface-raised);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 2;
    gap: 1px;
  }
  .atlas-centre-n {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 400;
    color: var(--text);
    line-height: 1;
  }
  .atlas-centre-l {
    font-family: var(--font-body);
    font-size: 7px;
    letter-spacing: 0.08em;
    color: var(--text-faint);
    text-transform: uppercase;
  }
  .atlas-node {
    position: absolute;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-family: var(--font-body);
    font-weight: 600;
    text-align: center;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.2s;
    z-index: 1;
    letter-spacing: 0;
  }
  .atlas-teaser-visual:hover .atlas-node { transform: translate(-50%, -50%) scale(1.1); }

  /* ── New releases ── */
  .releases-section {
    padding: 0 0 48px;
    max-width: 640px;
    margin: 0 auto;
  }
  .releases-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    padding: 0 28px;
    margin-bottom: 16px;
  }
  .releases-scroll {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding: 4px 28px 8px;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  .releases-scroll::-webkit-scrollbar { display: none; }
  .release-card {
    flex-shrink: 0;
    width: 160px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 14px;
    overflow: hidden;
    text-decoration: none;
    transition: border-color 0.18s, transform 0.18s;
    display: block;
  }
  .release-card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .release-card-bar { height: 3px; width: 100%; }
  .release-card-body { padding: 12px; }
  .release-card-origin {
    font-family: var(--font-body);
    font-size: 9px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    display: block;
    margin-bottom: 5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .release-card-name {
    font-family: var(--font-display);
    font-size: 14px;
    font-style: italic;
    font-weight: 400;
    color: var(--text);
    margin: 0 0 8px;
    line-height: 1.25;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .release-card-notes {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }
  .release-card-note {
    font-family: var(--font-body);
    font-size: 9px;
    padding: 2px 6px;
    border-radius: 100px;
    background: var(--bg-warm);
    color: var(--text-muted);
    text-transform: capitalize;
  }
  .release-card-price {
    font-family: var(--font-body);
    font-size: 11px;
    font-weight: 600;
    color: var(--accent);
  }

  /* ── Origins ── */
  .origins-section {
    padding: 0 28px 48px;
    max-width: 640px;
    margin: 0 auto;
  }
  .origins-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .origins-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .origin-tile {
    display: block;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 12px 10px 8px;
    text-decoration: none;
    transition: border-color 0.18s, transform 0.15s;
  }
  .origin-tile:hover { border-color: var(--accent); transform: translateY(-1px); }
  .origin-tile-top {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 10px;
  }
  .origin-tile-emoji { font-size: 16px; flex-shrink: 0; }
  .origin-tile-name {
    font-family: var(--font-body);
    font-size: 11px;
    font-weight: 500;
    color: var(--text);
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .origin-tile-count {
    font-family: var(--font-body);
    font-size: 10px;
    color: var(--text-faint);
    flex-shrink: 0;
  }
  .origin-tile-strip {
    display: flex;
    height: 4px;
    border-radius: 2px;
    overflow: hidden;
    gap: 1px;
  }
  .origin-tile-band { height: 100%; min-width: 2px; border-radius: 1px; }

  /* ── Roasters ── */
  .roasters-section {
    padding: 0 28px 48px;
    max-width: 640px;
    margin: 0 auto;
  }
  .roasters-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .roasters-strip {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .roaster-pill {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    text-decoration: none;
    transition: border-color 0.15s;
  }
  .roaster-pill:hover { border-color: var(--accent); }
  .roaster-pill-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--accent-dim);
    color: var(--accent);
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .roaster-pill-name {
    font-family: var(--font-body);
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    flex: 1;
  }
  .roaster-pill-region {
    font-family: var(--font-body);
    font-size: 11px;
    color: var(--text-faint);
    flex-shrink: 0;
  }

  /* ── How it works ── */
  .hiw-section {
    padding: 0 28px 64px;
    max-width: 640px;
    margin: 0 auto;
    border-top: 1px solid var(--border-light);
    padding-top: 36px;
    margin-top: 4px;
  }
  .hiw-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    margin: 16px 0 24px;
  }
  .hiw-step {}
  .hiw-n {
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 300;
    color: var(--border);
    display: block;
    margin-bottom: 6px;
    line-height: 1;
  }
  .hiw-title {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 500;
    font-style: italic;
    color: var(--text);
    margin: 0 0 6px;
  }
  .hiw-body {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 0;
  }
  .hiw-footer { }
  .hiw-link {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-faint);
    text-decoration: none;
    transition: color 0.15s;
  }
  .hiw-link:hover { color: var(--accent); }

  /* ── Mobile ── */
  @media (max-width: 480px) {
    .hero-section { padding: 36px 20px 32px; }
    .hero-headline { font-size: 36px; }
    .atlas-teaser { padding: 0 20px 40px; }
    .atlas-teaser-inner { grid-template-columns: 1fr; gap: 20px; }
    .atlas-teaser-visual { display: none; }
    .releases-section { padding-bottom: 36px; }
    .releases-scroll { padding: 4px 20px 8px; }
    .origins-section, .roasters-section, .hiw-section { padding: 0 20px 36px; }
    .hiw-section { padding-top: 28px; }
    .origins-grid { grid-template-columns: repeat(2, 1fr); }
    .hiw-grid { grid-template-columns: 1fr; gap: 16px; }
  }
`;
