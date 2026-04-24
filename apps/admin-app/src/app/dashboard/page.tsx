"use client";

import { useEffect, useState } from "react";
import { getSources, getIngestionRuns, getMatches, type Store, type IngestionRun, type CanonicalMatch } from "@/lib/api";
import { StatCard, Badge, ConfidenceBar, DataTable, SkeletonRows } from "@/components/ui";

function fmtAgo(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function DashboardPage() {
  const [sources, setSources] = useState<Store[]>([]);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [pendingMatches, setPendingMatches] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getSources({ active_only: false, page_size: 200 }),
      getIngestionRuns({ page_size: 10 }),
      getMatches({ status: "pending", page_size: 1 }),
    ]).then(([s, r, m]) => {
      setSources(s.data);
      setRuns(r.data);
      setPendingMatches(m.pending_count);
    }).finally(() => setLoading(false));
  }, []);

  const byHealth = (h: string) => sources.filter(s => s.health_status === h).length;
  const total = sources.length;
  const healthy = byHealth("healthy");
  const stale = byHealth("stale");
  const inactive = byHealth("inactive");
  const healthPct = total > 0 ? Math.round((healthy / total) * 100) : 0;

  const byStrategy = sources.reduce<Record<string, number>>((acc, s) => {
    acc[s.parser_strategy] = (acc[s.parser_strategy] ?? 0) + 1;
    return acc;
  }, {});

  const failedRuns = runs.filter(r => r.status === "failed").length;
  const recentErrors = runs.flatMap(r => r.errors.slice(0, 2).map(e => ({ ...e, run_id: r.id, started_at: r.started_at })));

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-lg font-medium text-neutral-100">Dashboard</h1>
        <p className="text-sm text-neutral-500 mt-0.5">Platform health at a glance.</p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <StatCard label="Sources" value={loading ? "…" : total} sub="tracked domains" />
        <StatCard
          label="Source health"
          value={loading ? "…" : `${healthPct}%`}
          sub={`${healthy} healthy · ${stale} stale`}
          color={healthPct >= 80 ? "text-emerald-400" : healthPct >= 60 ? "text-amber-400" : "text-red-400"}
        />
        <StatCard label="Inactive" value={loading ? "…" : inactive} sub="flagged off" color={inactive > 0 ? "text-neutral-400" : "text-neutral-600"} />
        <StatCard label="Pending matches" value={loading ? "…" : pendingMatches} sub="need review" color={pendingMatches > 0 ? "text-amber-400" : "text-neutral-200"} />
        <StatCard label="Failed runs" value={loading ? "…" : failedRuns} sub="last 10 runs" color={failedRuns > 0 ? "text-red-400" : "text-emerald-400"} />
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Strategy breakdown */}
        <div className="border border-neutral-800 rounded-lg p-4 col-span-1">
          <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-3">Parser strategies</div>
          {Object.entries(byStrategy).map(([strategy, count]) => (
            <div key={strategy} className="flex items-center justify-between py-1.5 border-b border-neutral-800/50 last:border-0">
              <Badge value={strategy} />
              <div className="flex items-center gap-3">
                <div className="w-24 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-700/60 rounded-full" style={{ width: `${(count / total) * 100}%` }} />
                </div>
                <span className="text-xs text-neutral-400 w-8 text-right">{count}</span>
              </div>
            </div>
          ))}
          {loading && <div className="text-xs text-neutral-700 animate-pulse">Loading…</div>}
        </div>

        {/* Health breakdown */}
        <div className="border border-neutral-800 rounded-lg p-4 col-span-1">
          <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-3">Source health</div>
          {[["healthy", "Healthy", "text-emerald-400"], ["stale", "Stale", "text-amber-400"], ["unknown", "Unknown", "text-neutral-400"], ["inactive", "Inactive", "text-neutral-600"]].map(([key, label, cls]) => {
            const n = byHealth(key);
            return (
              <div key={key} className="flex items-center justify-between py-1.5 border-b border-neutral-800/50 last:border-0">
                <span className={`text-xs ${cls}`}>{label}</span>
                <div className="flex items-center gap-3">
                  <div className="w-24 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${key === "healthy" ? "bg-emerald-700/60" : key === "stale" ? "bg-amber-700/60" : "bg-neutral-700"}`}
                      style={{ width: total > 0 ? `${(n / total) * 100}%` : "0" }} />
                  </div>
                  <span className="text-xs text-neutral-400 w-8 text-right">{n}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Recent errors */}
        <div className="border border-neutral-800 rounded-lg p-4 col-span-1">
          <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-3">Recent errors</div>
          {recentErrors.length === 0 && !loading && (
            <div className="text-xs text-neutral-700 py-4 text-center">No recent errors</div>
          )}
          {recentErrors.slice(0, 5).map((e, i) => (
            <div key={i} className="py-1.5 border-b border-neutral-800/50 last:border-0">
              <div className="text-xs text-red-400 truncate">{e.message}</div>
              {e.url && <div className="text-[10px] text-neutral-700 font-mono truncate">{e.url}</div>}
            </div>
          ))}
        </div>
      </div>

      {/* Recent ingestion runs */}
      <div className="border border-neutral-800 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
          <span className="text-sm font-medium text-neutral-300">Recent ingestion runs</span>
          <a href="/ingestion-runs" className="text-xs text-amber-600 hover:text-amber-400">View all →</a>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-800 bg-neutral-900/40">
              {["Status", "Type", "Started", "Duration", "Records", "Issues"].map(h => (
                <th key={h} className="px-4 py-2 text-left text-[11px] font-medium text-neutral-600 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? <SkeletonRows cols={6} rows={4} /> : runs.slice(0, 6).map(run => (
              <tr key={run.id} className="border-b border-neutral-800/40 hover:bg-neutral-900/30">
                <td className="px-4 py-2"><Badge value={run.status} dot /></td>
                <td className="px-4 py-2 text-xs text-neutral-400 font-mono">{run.run_type}</td>
                <td className="px-4 py-2 text-xs text-neutral-500">{new Date(run.started_at).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</td>
                <td className="px-4 py-2 text-xs text-neutral-500 font-mono">
                  {run.duration_seconds != null ? run.duration_seconds < 60 ? `${run.duration_seconds.toFixed(1)}s` : `${(run.duration_seconds / 60).toFixed(1)}m` : "—"}
                </td>
                <td className="px-4 py-2">
                  <div className="flex gap-2 text-xs">
                    <span className="text-neutral-500">{run.records_seen} seen</span>
                    {run.records_created > 0 && <span className="text-emerald-600">+{run.records_created}</span>}
                    {run.records_updated > 0 && <span className="text-blue-600">↑{run.records_updated}</span>}
                  </div>
                </td>
                <td className="px-4 py-2">
                  <div className="flex gap-2 text-xs">
                    {run.error_count > 0 && <span className="text-red-500">{run.error_count} err</span>}
                    {run.warning_count > 0 && <span className="text-amber-500">{run.warning_count} warn</span>}
                    {run.error_count === 0 && run.warning_count === 0 && <span className="text-neutral-700">—</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
