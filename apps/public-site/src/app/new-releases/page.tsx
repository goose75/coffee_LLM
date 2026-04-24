"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getNewReleases } from "@/lib/api";
import type { Coffee } from "@/lib/api";

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c",
  natural: "#c4763a",
  honey: "#d4a03a",
  anaerobic: "#8b6bab",
  wet_hulled: "#5a7fa8",
  carbonic_maceration: "#b06080",
  experimental: "#7f7f7f",
};

function daysSince(isoDate: string | null | undefined): number {
  if (!isoDate) return 99;
  const diff = Date.now() - new Date(isoDate).getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

function recencyLabel(days: number): string {
  if (days === 0) return "Today";
  if (days <= 3) return "Last 3 days";
  if (days <= 7) return "This week";
  return "Earlier";
}

function DaysBadge({ days }: { days: number }) {
  if (days === 0)
    return <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: "#d4a84b22", color: "var(--accent)", border: "1px solid var(--accent)" }}>Today</span>;
  if (days <= 3)
    return <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}>{days}d ago</span>;
  return <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>{days}d ago</span>;
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-5 py-4 px-5 rounded-xl animate-pulse" style={{ border: "1px solid var(--border-light)" }}>
      <div className="w-1 self-stretch rounded-full flex-shrink-0" style={{ backgroundColor: "var(--border)" }} />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-1/2 rounded" style={{ backgroundColor: "var(--border)" }} />
        <div className="h-3 w-1/3 rounded" style={{ backgroundColor: "var(--border)" }} />
      </div>
      <div className="h-4 w-12 rounded" style={{ backgroundColor: "var(--border)" }} />
    </div>
  );
}

export default function NewReleasesPage() {
  const [coffees, setCoffees]   = useState<Coffee[]>([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [days, setDays]         = useState(14);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await getNewReleases({ days, page, page_size: 40 });
      setCoffees(data.data); setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [days, page]);

  useEffect(() => { setPage(1); }, [days]);
  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / 40);

  // Group by recency
  const groups: Record<string, (Coffee & { daysAgo: number })[]> = {};
  coffees.forEach(c => {
    const d = daysSince(c.newest_listing_at);
    const label = recencyLabel(d);
    if (!groups[label]) groups[label] = [];
    groups[label].push({ ...c, daysAgo: d });
  });
  const groupOrder = ["Today", "Last 3 days", "This week", "Earlier"];

  return (
    <div className="max-w-4xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="mb-10">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--text-faint)" }}>Live feed</div>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-4xl font-light mb-2" style={{ fontFamily: "var(--font-display)" }}>New releases</h1>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Coffees newly detected across UK roasters.{" "}
              {!loading && <span style={{ color: "var(--text-faint)" }}>{total} in the last {days} days.</span>}
            </p>
          </div>
          {/* Days filter */}
          <div className="flex gap-1.5">
            {[7, 14, 30].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className="text-xs px-3 py-1.5 rounded-full border transition-all"
                style={{
                  backgroundColor: days === d ? "var(--accent)" : "transparent",
                  borderColor: days === d ? "var(--accent)" : "var(--border)",
                  color: days === d ? "#fff" : "var(--text-muted)",
                }}>
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="py-10 text-center rounded-2xl mb-8" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
          <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Couldn't load releases</p>
          <button onClick={load} className="text-xs px-4 py-2 rounded-full" style={{ backgroundColor: "var(--accent)", color: "#fff" }}>Retry</button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 10 }).map((_, i) => <SkeletonRow key={i} />)}
        </div>
      ) : coffees.length === 0 && !error ? (
        <div className="py-20 text-center">
          <div className="text-3xl mb-3" style={{ fontFamily: "var(--font-display)" }}>Nothing yet</div>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>No new releases in the last {days} days.</p>
        </div>
      ) : (
        <div className="space-y-12">
          {groupOrder.filter(g => groups[g]?.length).map(group => (
            <div key={group}>
              <div className="flex items-center gap-4 mb-5">
                <span className="text-xs uppercase tracking-widest font-medium" style={{ color: "var(--text-faint)" }}>{group}</span>
                <div className="flex-1 h-px" style={{ backgroundColor: "var(--border-light)" }} />
                <span className="text-xs" style={{ color: "var(--text-faint)" }}>{groups[group].length} new</span>
              </div>

              <div className="space-y-3">
                {groups[group].map(release => {
                  const processColor = PROCESS_COLORS[release.process ?? ""] ?? "var(--border)";
                  return (
                    <Link key={release.id} href={`/coffees/${release.id}`}
                      className="group flex items-center gap-5 py-4 rounded-xl px-5 transition-all hover:-translate-y-px"
                      style={{ border: "1px solid var(--border-light)", backgroundColor: "var(--surface)" }}>

                      <div className="w-1 self-stretch rounded-full flex-shrink-0" style={{ backgroundColor: processColor }} />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-3 mb-1">
                          <h3 className="text-base font-medium group-hover:opacity-80 transition-opacity truncate"
                            style={{ fontFamily: "var(--font-display)", fontSize: "1.05rem" }}>
                            {release.canonical_name}
                          </h3>
                          <DaysBadge days={release.daysAgo} />
                        </div>
                        <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-faint)" }}>
                          {release.origin_country && <span>{release.origin_country}</span>}
                          {release.origin_region && <><span>·</span><span>{release.origin_region}</span></>}
                          {release.process && <><span>·</span><span className="capitalize">{release.process.replace(/_/g, " ")}</span></>}
                          {release.harvest_year && <><span>·</span><span>{release.harvest_year}</span></>}
                        </div>
                        {release.flavour_notes.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {release.flavour_notes.slice(0, 4).map(n => (
                              <span key={n} className="text-[11px] px-2 py-0.5 rounded-full capitalize"
                                style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}>{n}</span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="text-right flex-shrink-0">
                        {release.min_price_gbp != null && (
                          <div className="text-sm font-medium" style={{ color: "var(--accent)" }}>
                            from £{release.min_price_gbp.toFixed(2)}
                          </div>
                        )}
                        <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>
                          {release.store_count ?? 0} {(release.store_count ?? 0) === 1 ? "store" : "stores"}
                        </div>
                      </div>

                      <div className="text-xs opacity-0 group-hover:opacity-40 transition-opacity flex-shrink-0" style={{ color: "var(--text)" }}>→</div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
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

      <div className="mt-12 pt-6 text-center text-xs" style={{ borderTop: "1px solid var(--border-light)", color: "var(--text-faint)" }}>
        Checking ~200 UK sources daily · updated overnight
      </div>
    </div>
  );
}
