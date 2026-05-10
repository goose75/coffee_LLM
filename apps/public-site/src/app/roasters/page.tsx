"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { getRoasters } from "@/lib/api";
import type { Roaster } from "@/lib/api";

const UK_REGIONS = ["London", "South West", "Yorkshire", "Midlands", "Scotland", "Wales", "East of England", "North West", "South East", "Northern Ireland"];

function RoasterCard({ roaster }: { roaster: Roaster }) {
  return (
    <a href={`/roasters/${roaster.id}`}
      className="group block rounded-2xl p-5 transition-all hover:-translate-y-0.5"
      style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
      <div className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-semibold mb-4"
        style={{ backgroundColor: "var(--bg-warm)", fontFamily: "var(--font-display)", color: "var(--accent)" }}>
        {roaster.name.charAt(0)}
      </div>
      <h3 className="font-medium mb-1 group-hover:opacity-80 transition-opacity"
        style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem" }}>
        {roaster.name}
      </h3>
      <div className="flex items-center gap-2 mb-3">
        {roaster.uk_region && (
          <span className="text-xs px-2 py-0.5 rounded-full"
            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-faint)" }}>
            {roaster.uk_region}
          </span>
        )}
        {roaster.cafe_flag && (
          <span className="text-xs px-2 py-0.5 rounded-full"
            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-faint)" }}>
            ☕ Café
          </span>
        )}
      </div>
      <div className="text-xs" style={{ color: "var(--text-faint)" }}>
        {roaster.domain}
      </div>
      {roaster.listing_count != null && (
        <div className="mt-3 pt-3 text-xs" style={{ borderTop: "1px solid var(--border)", color: "var(--text-faint)" }}>
          {roaster.listing_count} coffees indexed
        </div>
      )}
    </a>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl p-5 animate-pulse" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
      <div className="w-12 h-12 rounded-full mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-5 w-2/3 rounded mb-2" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-3 w-1/3 rounded mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-3 w-1/2 rounded" style={{ backgroundColor: "var(--border)" }} />
    </div>
  );
}

export default function RoastersPage() {
  const [q, setQ]               = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [roasters, setRoasters] = useState<Roaster[]>([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => { const t = setTimeout(() => setDebouncedQ(q), 350); return () => clearTimeout(t); }, [q]);
  useEffect(() => { setPage(1); }, [debouncedQ, selectedRegion]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params: Record<string, string | number | undefined> = { page, page_size: 48 };
      if (debouncedQ) params.q = debouncedQ;
      if (selectedRegion) params.uk_region = selectedRegion;
      const data = await getRoasters(params);
      setRoasters(data.data); setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [page, debouncedQ, selectedRegion]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / 48);

  // Region counts derived from current full set — approximate
  const regionCounts: Record<string, number> = useMemo(() => {
    const counts: Record<string, number> = {};
    roasters.forEach(r => { if (r.uk_region) counts[r.uk_region] = (counts[r.uk_region] ?? 0) + 1; });
    return counts;
  }, [roasters]);

  return (
    <div className="max-w-4xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="mb-8">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--text-faint)" }}>Directory</div>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-4xl font-light mb-1" style={{ fontFamily: "var(--font-display)" }}>UK Roasters</h1>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {loading ? "…" : `${total.toLocaleString()} roasters`} currently indexed. Updated daily.
            </p>
          </div>
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: "var(--text-faint)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search roasters…"
              className="pl-8 pr-4 py-2 text-sm rounded-full w-52 focus:outline-none"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }} />
          </div>
        </div>
      </div>

      {/* Region filter strip */}
      <div className="flex flex-wrap gap-2 mb-8">
        <button onClick={() => setSelectedRegion(null)}
          className="text-xs px-3 py-1.5 rounded-full border transition-all"
          style={{
            backgroundColor: selectedRegion === null ? "var(--accent)" : "transparent",
            borderColor: selectedRegion === null ? "var(--accent)" : "var(--border)",
            color: selectedRegion === null ? "#fff" : "var(--text-muted)",
          }}>
          All regions
        </button>
        {UK_REGIONS.map(region => (
          <button key={region} onClick={() => setSelectedRegion(selectedRegion === region ? null : region)}
            className="text-xs px-3 py-1.5 rounded-full border transition-all"
            style={{
              backgroundColor: selectedRegion === region ? "var(--accent)" : "transparent",
              borderColor: selectedRegion === region ? "var(--accent)" : "var(--border)",
              color: selectedRegion === region ? "#fff" : "var(--text-muted)",
            }}>
            {region}
            {!debouncedQ && !selectedRegion && regionCounts[region] ? (
              <span className="ml-1 opacity-50">{regionCounts[region]}</span>
            ) : null}
          </button>
        ))}
      </div>

      {error && (
        <div className="py-10 text-center rounded-2xl mb-8" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
          <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Couldn't reach the API</p>
          <button onClick={load} className="text-xs px-4 py-2 rounded-full" style={{ backgroundColor: "var(--accent)", color: "#fff" }}>Retry</button>
        </div>
      )}

      {loading ? (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 16 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : roasters.length === 0 && !error ? (
        <div className="py-20 text-center">
          <div className="text-3xl mb-3" style={{ fontFamily: "var(--font-display)" }}>No roasters found</div>
          <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Try a different search or region</p>
          <button onClick={() => { setQ(""); setSelectedRegion(null); }} className="text-sm" style={{ color: "var(--accent)" }}>Clear filters</button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {roasters.map(r => <RoasterCard key={r.id} roaster={r} />)}
        </div>
      )}

      {totalPages > 1 && !loading && (
        <div className="mt-10 flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => p - 1)} disabled={page <= 1}
            className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
            style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>← Prev</button>
          <span className="px-3 text-sm" style={{ color: "var(--text-muted)" }}>{page} / {totalPages}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
            className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
            style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>Next →</button>
        </div>
      )}
    </div>
  );
}
