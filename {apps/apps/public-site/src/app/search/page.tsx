"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { getCoffees, getRoasters } from "@/lib/api";
import type { Coffee, Roaster } from "@/lib/api";

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c", natural: "#c4763a", honey: "#d4a03a",
  anaerobic: "#8b6bab", wet_hulled: "#5a7fa8", carbonic_maceration: "#a85a7f",
};

const COUNTRY_FLAGS: Record<string, string> = {
  "Ethiopia": "🇪🇹", "Kenya": "🇰🇪", "Colombia": "🇨🇴", "Brazil": "🇧🇷",
  "Guatemala": "🇬🇹", "Rwanda": "🇷🇼", "Panama": "🇵🇦", "Costa Rica": "🇨🇷",
  "Honduras": "🇭🇳", "Peru": "🇵🇪", "Burundi": "🇧🇮", "Uganda": "🇺🇬",
  "Indonesia": "🇮🇩", "India": "🇮🇳", "Yemen": "🇾🇪",
};

// Recent searches — persisted in localStorage
function useRecentSearches() {
  const [recents, setRecents] = useState<string[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("grounds_recent_searches");
      if (stored) setRecents(JSON.parse(stored));
    } catch {}
  }, []);

  const add = useCallback((term: string) => {
    if (!term.trim()) return;
    setRecents(prev => {
      const next = [term, ...prev.filter(r => r !== term)].slice(0, 8);
      try { localStorage.setItem("grounds_recent_searches", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const remove = useCallback((term: string) => {
    setRecents(prev => {
      const next = prev.filter(r => r !== term);
      try { localStorage.setItem("grounds_recent_searches", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setRecents([]);
    try { localStorage.removeItem("grounds_recent_searches"); } catch {}
  }, []);

  return { recents, add, remove, clear };
}

// Quick suggestions shown before typing
const SUGGESTIONS = [
  { label: "Ethiopian naturals", q: "Ethiopia", filter: { process: "natural" } },
  { label: "Kenyan AA", q: "Kenya", filter: {} },
  { label: "Anaerobic coffees", q: "", filter: { process: "anaerobic" } },
  { label: "New releases", href: "/new-releases" },
  { label: "Under £12", q: "", filter: { max_price: 12 } },
  { label: "Light roasts", q: "", filter: { roast_level: "light" } },
];

// ── Search result item ─────────────────────────────────────────────────────────

function CoffeeResult({ coffee, onSelect }: { coffee: Coffee; onSelect: () => void }) {
  const flag = COUNTRY_FLAGS[coffee.origin_country ?? ""] ?? "☕";
  const processColor = PROCESS_COLORS[coffee.process ?? ""] ?? "var(--border)";
  return (
    <Link
      href={`/coffees/${coffee.id}`}
      onClick={onSelect}
      className="flex items-center gap-3 px-4 py-3 press-active"
      style={{ borderBottom: "1px solid var(--border-light)" }}
    >
      {/* Process colour dot */}
      <div
        className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-base"
        style={{ backgroundColor: processColor + "22", border: `1.5px solid ${processColor}50` }}
      >
        <span style={{ fontSize: 16 }}>{flag}</span>
      </div>

      <div className="flex-1 min-w-0">
        <div
          className="text-sm font-medium truncate"
          style={{ fontFamily: "var(--font-display)", fontSize: "1rem", color: "var(--text)" }}
        >
          {coffee.canonical_name}
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-faint)" }}>
          <span>{coffee.origin_country}</span>
          {coffee.process && (
            <>
              <span>·</span>
              <span className="capitalize">{coffee.process.replace(/_/g, " ")}</span>
            </>
          )}
        </div>
      </div>

      {coffee.min_price_gbp != null && (
        <div className="text-sm font-medium flex-shrink-0" style={{ color: "var(--accent)" }}>
          £{coffee.min_price_gbp.toFixed(2)}
        </div>
      )}

      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
        style={{ color: "var(--text-faint)", flexShrink: 0 }}>
        <path d="M9 18l6-6-6-6" />
      </svg>
    </Link>
  );
}

function RoasterResult({ roaster, onSelect }: { roaster: Roaster; onSelect: () => void }) {
  return (
    <a
      href={`//${roaster.domain}`}
      target="_blank"
      rel="noopener"
      onClick={onSelect}
      className="flex items-center gap-3 px-4 py-3 press-active"
      style={{ borderBottom: "1px solid var(--border-light)" }}
    >
      <div
        className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold"
        style={{ backgroundColor: "var(--bg-warm)", color: "var(--accent)" }}
      >
        {roaster.name.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>{roaster.name}</div>
        <div className="text-xs truncate" style={{ color: "var(--text-faint)" }}>
          {[roaster.uk_region, roaster.domain].filter(Boolean).join(" · ")}
        </div>
      </div>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
        style={{ color: "var(--text-faint)", flexShrink: 0 }}>
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3" />
      </svg>
    </a>
  );
}

// ── Main search page ──────────────────────────────────────────────────────────

export default function SearchPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [coffees, setCoffees] = useState<Coffee[]>([]);
  const [roasters, setRoasters] = useState<Roaster[]>([]);
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);
  const { recents, add, remove, clear } = useRecentSearches();

  // Auto-focus on mount
  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 150);
    return () => clearTimeout(t);
  }, []);

  // Debounce
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 280);
    return () => clearTimeout(t);
  }, [q]);

  // Search
  useEffect(() => {
    if (!debouncedQ.trim()) {
      setCoffees([]);
      setRoasters([]);
      return;
    }
    setLoading(true);
    Promise.allSettled([
      getCoffees({ q: debouncedQ, page_size: 8 }),
      getRoasters({ q: debouncedQ, page_size: 3 }),
    ]).then(([coffeeRes, roasterRes]) => {
      if (coffeeRes.status === "fulfilled") setCoffees(coffeeRes.value.data);
      if (roasterRes.status === "fulfilled") setRoasters(roasterRes.value.data);
    }).finally(() => setLoading(false));
  }, [debouncedQ]);

  const handleSelect = () => {
    if (q.trim()) add(q.trim());
    setFocused(false);
  };

  const handleRecentSelect = (term: string) => {
    setQ(term);
    setDebouncedQ(term);
    add(term);
  };

  const clearSearch = () => {
    setQ("");
    setCoffees([]);
    setRoasters([]);
    inputRef.current?.focus();
  };

  const hasResults = coffees.length > 0 || roasters.length > 0;
  const showEmpty = debouncedQ && !loading && !hasResults;
  const showRecents = !debouncedQ && recents.length > 0;
  const showSuggestions = !debouncedQ;

  return (
    <div className="flex flex-col min-h-screen" style={{ backgroundColor: "var(--bg)" }}>

      {/* Search input bar */}
      <div className="px-4 pt-2 pb-3 sticky top-12 z-30"
        style={{ backgroundColor: "var(--bg)", borderBottom: "1px solid var(--border-light)" }}>
        <div
          className="flex items-center gap-3 px-4 h-11 rounded-2xl"
          style={{
            backgroundColor: "var(--surface)",
            border: `1.5px solid ${focused ? "var(--accent)" : "var(--border)"}`,
            transition: "border-color 0.15s ease",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ color: "var(--text-faint)", flexShrink: 0 }}>
            <circle cx="11" cy="11" r="7" /><line x1="16.5" y1="16.5" x2="21" y2="21" />
          </svg>

          <input
            ref={inputRef}
            type="search"
            value={q}
            onChange={e => setQ(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 150)}
            placeholder="Coffees, roasters, origins…"
            className="flex-1 bg-transparent outline-none text-[15px]"
            style={{ color: "var(--text)", caretColor: "var(--accent)" }}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            onKeyDown={e => { if (e.key === "Enter" && q.trim()) { add(q.trim()); } }}
          />

          {q && (
            <button
              onClick={clearSearch}
              className="w-5 h-5 flex items-center justify-center rounded-full flex-shrink-0"
              style={{ backgroundColor: "var(--text-faint)", color: "var(--surface)" }}
            >
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1">

        {/* Loading indicator */}
        {loading && (
          <div className="px-4 py-5 flex items-center gap-2" style={{ color: "var(--text-faint)" }}>
            <div className="w-4 h-4 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
            <span className="text-sm">Searching…</span>
          </div>
        )}

        {/* Results */}
        {!loading && hasResults && (
          <div className="fade-in">
            {/* Roasters first if matching */}
            {roasters.length > 0 && (
              <div>
                <div className="px-4 pt-5 pb-2 text-[11px] uppercase tracking-widest font-medium"
                  style={{ color: "var(--text-faint)" }}>
                  Roasters
                </div>
                {roasters.map(r => <RoasterResult key={r.id} roaster={r} onSelect={handleSelect} />)}
              </div>
            )}

            {coffees.length > 0 && (
              <div>
                <div className="px-4 pt-5 pb-2 text-[11px] uppercase tracking-widest font-medium"
                  style={{ color: "var(--text-faint)" }}>
                  Coffees
                </div>
                {coffees.map(c => <CoffeeResult key={c.id} coffee={c} onSelect={handleSelect} />)}
              </div>
            )}

            {/* See all link */}
            <div className="px-4 py-5">
              <Link
                href={`/coffees?q=${encodeURIComponent(q)}`}
                onClick={() => add(q)}
                className="flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-medium press-active"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
              >
                See all results for "{q}"
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </Link>
            </div>
          </div>
        )}

        {/* Empty state */}
        {showEmpty && (
          <div className="px-4 py-16 text-center fade-in">
            <div className="text-4xl mb-3">☕</div>
            <div className="text-lg font-light mb-1" style={{ fontFamily: "var(--font-display)" }}>
              No results
            </div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Nothing found for "{debouncedQ}".<br />Try a different search.
            </p>
          </div>
        )}

        {/* Recent searches */}
        {showRecents && (
          <div className="fade-in">
            <div className="px-4 pt-5 pb-2 flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-widest font-medium" style={{ color: "var(--text-faint)" }}>
                Recent
              </span>
              <button onClick={clear} className="text-xs" style={{ color: "var(--accent)" }}>Clear</button>
            </div>
            {recents.map(term => (
              <div
                key={term}
                className="flex items-center gap-3 px-4 py-3 press-active"
                style={{ borderBottom: "1px solid var(--border-light)" }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                  style={{ color: "var(--text-faint)", flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
                <button
                  className="flex-1 text-left text-sm"
                  style={{ color: "var(--text-muted)" }}
                  onClick={() => handleRecentSelect(term)}
                >
                  {term}
                </button>
                <button
                  onClick={() => remove(term)}
                  className="p-1"
                  style={{ color: "var(--text-faint)" }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Quick suggestions */}
        {showSuggestions && (
          <div className="fade-in">
            <div className="px-4 pt-5 pb-2 text-[11px] uppercase tracking-widest font-medium"
              style={{ color: "var(--text-faint)" }}>
              Explore
            </div>
            <div className="px-4 py-2 flex flex-wrap gap-2">
              {SUGGESTIONS.map(s => (
                s.href ? (
                  <Link
                    key={s.label}
                    href={s.href}
                    className="px-4 py-2 rounded-full text-sm font-medium press-active"
                    style={{
                      backgroundColor: "var(--surface)",
                      border: "1px solid var(--border)",
                      color: "var(--text-muted)",
                    }}
                  >
                    {s.label}
                  </Link>
                ) : (
                  <Link
                    key={s.label}
                    href={`/coffees?${new URLSearchParams({ ...(s.q ? { q: s.q } : {}), ...Object.fromEntries(Object.entries(s.filter ?? {}).map(([k, v]) => [k, String(v)])) }).toString()}`}
                    onClick={() => s.q && add(s.q)}
                    className="px-4 py-2 rounded-full text-sm font-medium press-active"
                    style={{
                      backgroundColor: "var(--surface)",
                      border: "1px solid var(--border)",
                      color: "var(--text-muted)",
                    }}
                  >
                    {s.label}
                  </Link>
                )
              ))}
            </div>

            {/* Popular origins */}
            <div className="px-4 pt-5 pb-2 text-[11px] uppercase tracking-widest font-medium"
              style={{ color: "var(--text-faint)" }}>
              By origin
            </div>
            <div className="grid grid-cols-3 gap-2 px-4 pb-6">
              {[
                ["🇪🇹", "Ethiopia"], ["🇰🇪", "Kenya"], ["🇨🇴", "Colombia"],
                ["🇧🇷", "Brazil"], ["🇷🇼", "Rwanda"], ["🇵🇦", "Panama"],
              ].map(([flag, country]) => (
                <Link
                  key={country}
                  href={`/coffees?origin_country=${encodeURIComponent(country)}`}
                  className="flex flex-col items-center gap-1.5 py-4 rounded-2xl press-active"
                  style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}
                >
                  <span style={{ fontSize: 24 }}>{flag}</span>
                  <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>{country}</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
