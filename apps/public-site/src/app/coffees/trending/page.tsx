"use client";

import { useState, useEffect, useCallback } from "react";
import CoffeeCard from "@/components/CoffeeCard";
import { getTrendingCoffees, getMarketAverages } from "@/lib/api";
import type { Coffee } from "@/lib/api";

function SkeletonCard() {
  return (
    <div className="rounded-2xl p-5 animate-pulse" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
      <div className="h-3 w-16 rounded mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-5 w-3/4 rounded mb-2" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-3 w-1/2 rounded mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="flex gap-1.5 mb-4">{[40,55,45].map(w => <div key={w} className="h-5 rounded-full" style={{ width: w, backgroundColor: "var(--border)" }} />)}</div>
      <div className="h-px mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="flex justify-between">
        <div className="h-4 w-20 rounded" style={{ backgroundColor: "var(--border)" }} />
        <div className="h-4 w-12 rounded" style={{ backgroundColor: "var(--border)" }} />
      </div>
    </div>
  );
}

export default function TrendingPage() {
  const [coffees, setCoffees] = useState<Coffee[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marketMedian, setMarketMedian] = useState<number | null>(null);

  useEffect(() => {
    getMarketAverages().then(d => setMarketMedian(d.median_per_100g_gbp)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTrendingCoffees({ days: 30, page, page_size: 24 });
      setCoffees(data.data);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.ceil(total / 24);

  return (
    <div className="max-w-4xl mx-auto px-4 py-4">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--text-faint)" }}>Newest releases</div>
        <h1 className="text-4xl font-light" style={{ fontFamily: "var(--font-display)" }}>Just added</h1>
        <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>Recently discovered coffees from roasters</p>
      </div>

      {error && (
        <div className="py-6 text-center rounded-2xl mb-6" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
          <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Couldn't load trending coffees</p>
          <button onClick={load} className="text-xs px-4 py-2 rounded-full" style={{ backgroundColor: "var(--accent)", color: "#fff" }}>
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : coffees.length === 0 && !error ? (
        <div className="py-20 text-center">
          <div className="text-3xl mb-3" style={{ fontFamily: "var(--font-display)" }}>No trending coffees</div>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Check back soon for new releases</p>
        </div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {coffees.map(c => <CoffeeCard key={c.id} coffee={c} marketMedianPer100g={marketMedian} />)}
          </div>

          {totalPages > 1 && (
            <div className="mt-10 flex items-center justify-center gap-2">
              <button onClick={() => setPage(p => p - 1)} disabled={page <= 1}
                className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                ← Prev
              </button>
              <span className="px-3 text-sm" style={{ color: "var(--text-muted)" }}>{page} / {totalPages}</span>
              <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
                className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
