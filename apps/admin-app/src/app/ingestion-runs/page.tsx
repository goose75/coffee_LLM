"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { getIngestionRuns, type IngestionRun, type IngestionFilters } from "@/lib/api";

// ============================================================================
// STATUS BADGE - Visual status indicator
// ============================================================================
function StatusBadge({ status }: { status: string }) {
  const statusConfig = {
    running: { color: "bg-blue-500/20 border-blue-500 text-blue-400", icon: "↻" },
    completed: { color: "bg-green-500/20 border-green-500 text-green-400", icon: "✓" },
    failed: { color: "bg-red-500/20 border-red-500 text-red-400", icon: "✕" },
    partial: { color: "bg-amber-500/20 border-amber-500 text-amber-400", icon: "⚠" },
  };

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.completed;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-mono ${config.color}`}>
      <span>{config.icon}</span>
      <span className="uppercase tracking-widest">{status}</span>
    </span>
  );
}

// ============================================================================
// PROGRESS BAR - Visual record progress
// ============================================================================
function RecordsBar({ seen, created, updated, unchanged, error }: { seen: number; created: number; updated: number; unchanged: number; error: number }) {
  const total = seen || 1;
  return (
    <div className="space-y-1">
      <div className="flex gap-1 h-2 rounded-full overflow-hidden bg-slate-800">
        {created > 0 && <div className="bg-green-500" style={{ width: `${(created / total) * 100}%` }} />}
        {updated > 0 && <div className="bg-blue-500" style={{ width: `${(updated / total) * 100}%` }} />}
        {unchanged > 0 && <div className="bg-slate-600" style={{ width: `${(unchanged / total) * 100}%` }} />}
        {error > 0 && <div className="bg-red-500" style={{ width: `${(error / total) * 100}%` }} />}
      </div>
      <div className="flex gap-4 text-xs text-slate-500">
        <span>{created} ✓</span>
        <span>{updated} ↑</span>
        <span>{unchanged} =</span>
        {error > 0 && <span className="text-red-500">{error} ✕</span>}
      </div>
    </div>
  );
}

// ============================================================================
// MAIN INGESTION RUNS PAGE
// ============================================================================
export default function IngestionRunsPage() {
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<"started" | "duration" | "status">("started");

  // Load data
  const load = useCallback(async () => {
    try {
      const filters: IngestionFilters = {
        page,
        page_size: 100,
        status: filterStatus || undefined,
        run_type: filterType || undefined,
      };

      const data = await getIngestionRuns(filters);
      setRuns(data.data);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to load ingestion runs:", e);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus, filterType]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh every 8 seconds if any runs are active
  useEffect(() => {
    const hasActive = runs.some(r => r.status === "running");
    if (!autoRefresh || !hasActive) return;
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [runs, autoRefresh, load]);

  // Sort runs
  const sortedRuns = useMemo(() => {
    const copy = [...runs];
    if (sortBy === "started") {
      copy.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
    } else if (sortBy === "duration") {
      copy.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
    } else if (sortBy === "status") {
      const statusOrder = { running: 0, failed: 1, partial: 2, completed: 3 };
      copy.sort((a, b) => {
        const aOrder = statusOrder[a.status as keyof typeof statusOrder] ?? 99;
        const bOrder = statusOrder[b.status as keyof typeof statusOrder] ?? 99;
        return aOrder - bOrder;
      });
    }
    return copy;
  }, [runs, sortBy]);

  // Calculate stats
  const stats = useMemo(() => {
    const running = runs.filter(r => r.status === "running").length;
    const completed = runs.filter(r => r.status === "completed").length;
    const failed = runs.filter(r => r.status === "failed").length;
    const partial = runs.filter(r => r.status === "partial").length;
    const totalRecords = runs.reduce((sum, r) => sum + r.records_seen, 0);
    const totalCreated = runs.reduce((sum, r) => sum + r.records_created, 0);
    return { running, completed, failed, partial, totalRecords, totalCreated };
  }, [runs]);

  const toggleExpanded = (runId: string) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(runId)) {
      newExpanded.delete(runId);
    } else {
      newExpanded.add(runId);
    }
    setExpanded(newExpanded);
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return "—";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${(seconds / 60).toFixed(1)}m`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono">
      {/* HEADER */}
      <div className="mb-8">
        <h1 className="text-4xl font-black text-cyan-400 mb-2" style={{ textShadow: "0 0 20px rgba(34, 211, 238, 0.5)" }}>
          ↻ INGESTION RUNS
        </h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest">Monitor data extraction jobs and their results</p>
      </div>

      {/* STATS BAR */}
      <div className="grid grid-cols-6 gap-4 mb-8">
        <div className="border border-blue-500/30 rounded bg-blue-500/5 p-4">
          <div className="text-sm font-black text-blue-400">{stats.running}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Running</div>
        </div>
        <div className="border border-green-500/30 rounded bg-green-500/5 p-4">
          <div className="text-sm font-black text-green-400">{stats.completed}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Completed</div>
        </div>
        <div className="border border-amber-500/30 rounded bg-amber-500/5 p-4">
          <div className="text-sm font-black text-amber-400">{stats.partial}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Partial</div>
        </div>
        <div className="border border-red-500/30 rounded bg-red-500/5 p-4">
          <div className="text-sm font-black text-red-400">{stats.failed}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Failed</div>
        </div>
        <div className="border border-green-500/30 rounded bg-green-500/5 p-4">
          <div className="text-sm font-black text-green-400">{stats.totalCreated}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Created Today</div>
        </div>
        <div className="border border-cyan-500/30 rounded bg-cyan-500/5 p-4">
          <div className="text-sm font-black text-cyan-400">{total}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Total Runs</div>
        </div>
      </div>

      {/* CONTROLS */}
      <div className="mb-6 flex gap-4 flex-wrap items-center">
        <select
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400"
        >
          <option value="">All Status</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="partial">Partial</option>
        </select>

        <select
          value={filterType}
          onChange={(e) => {
            setFilterType(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400"
        >
          <option value="">All Types</option>
          <option value="full">Full Scan</option>
          <option value="incremental">Incremental</option>
          <option value="single_store">Single Store</option>
          <option value="single_page">Single Page</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400 ml-auto"
        >
          <option value="started">Sort by Started</option>
          <option value="duration">Sort by Duration</option>
          <option value="status">Sort by Status</option>
        </select>

        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className="px-4 py-2 border border-amber-500/30 rounded bg-amber-500/5 hover:bg-amber-500/10 text-xs uppercase tracking-widest text-amber-400 transition"
        >
          {autoRefresh ? "⏸ PAUSE" : "▶ LIVE"}
        </button>
      </div>

      {/* RUNS TABLE */}
      <div className="border border-cyan-500/20 rounded bg-slate-900/50 overflow-hidden">
        {loading ? (
          <div className="px-6 py-8 text-center text-slate-500">Loading runs...</div>
        ) : sortedRuns.length === 0 ? (
          <div className="px-6 py-8 text-center text-slate-500">No ingestion runs found</div>
        ) : (
          <div className="space-y-0 divide-y divide-slate-800">
            {sortedRuns.map((run) => {
              const isExpanded = expanded.has(run.id);
              const totalProcessed = run.records_created + run.records_updated + run.records_unchanged;

              return (
                <div key={run.id} className="hover:bg-slate-800/30 transition">
                  {/* RUN ROW */}
                  <div
                    onClick={() => toggleExpanded(run.id)}
                    className="px-6 py-4 cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-6">
                      {/* LEFT: Status and Store */}
                      <div className="flex items-start gap-4 flex-1 min-w-0">
                        <div className="flex flex-col gap-2 mt-1">
                          <StatusBadge status={run.status} />
                          <span className={`text-xs ${isExpanded ? "text-cyan-400" : "text-slate-600"}`}>
                            {isExpanded ? "▲" : "▼"}
                          </span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-sm font-mono font-black text-slate-100 truncate">
                            {run.store_name || "System-wide Scan"}
                          </h3>
                          <p className="text-xs text-slate-600 mt-1">
                            {new Date(run.started_at).toLocaleString()}
                          </p>
                          <p className="text-xs text-slate-700 mt-1">
                            {run.run_type.replace("_", " ")}
                          </p>
                        </div>
                      </div>

                      {/* RIGHT: Metrics */}
                      <div className="flex gap-8 items-start text-right">
                        <div className="min-w-24">
                          <div className="text-xs text-slate-600 mb-1">Duration</div>
                          <div className="text-sm font-mono text-slate-300">
                            {formatDuration(run.duration_seconds)}
                          </div>
                        </div>

                        <div className="min-w-32">
                          <div className="text-xs text-slate-600 mb-1">Records</div>
                          <div className="flex gap-2 text-xs font-mono justify-end">
                            {run.records_seen > 0 && <span className="text-slate-400">{run.records_seen} seen</span>}
                            {run.records_created > 0 && <span className="text-green-400">{run.records_created}✓</span>}
                            {run.records_updated > 0 && <span className="text-blue-400">{run.records_updated}↑</span>}
                            {run.error_count > 0 && <span className="text-red-400">{run.error_count}✕</span>}
                          </div>
                        </div>

                        <div className="min-w-32">
                          <div className="text-xs text-slate-600 mb-1">Issues</div>
                          <div className="flex gap-2 justify-end text-xs">
                            {run.error_count > 0 && (
                              <span className="text-red-400 font-mono">{run.error_count} errors</span>
                            )}
                            {run.warning_count > 0 && (
                              <span className="text-amber-400 font-mono">{run.warning_count} warnings</span>
                            )}
                            {run.error_count === 0 && run.warning_count === 0 && (
                              <span className="text-slate-600">—</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* EXPANDED DETAILS */}
                  {isExpanded && (
                    <div className="bg-slate-800/20 border-t border-slate-800 px-6 py-6 space-y-6">
                      {/* PROGRESS */}
                      <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-cyan-400 mb-3">Progress</h4>
                        <RecordsBar
                          seen={run.records_seen}
                          created={run.records_created}
                          updated={run.records_updated}
                          unchanged={run.records_unchanged}
                          error={run.error_count}
                        />
                      </div>

                      {/* PAGES */}
                      <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-cyan-400 mb-3">Pages</h4>
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div className="border border-slate-700 rounded p-3 bg-slate-800/20">
                            <div className="text-slate-400">Fetched</div>
                            <div className="text-lg font-black text-cyan-400">{run.pages_fetched}</div>
                          </div>
                          <div className="border border-slate-700 rounded p-3 bg-slate-800/20">
                            <div className="text-slate-400">Failed</div>
                            <div className={`text-lg font-black ${run.pages_failed > 0 ? "text-red-400" : "text-slate-600"}`}>
                              {run.pages_failed}
                            </div>
                          </div>
                          <div className="border border-slate-700 rounded p-3 bg-slate-800/20">
                            <div className="text-slate-400">Success Rate</div>
                            <div className={`text-lg font-black ${run.pages_fetched > 0 ? "text-green-400" : "text-slate-600"}`}>
                              {run.pages_fetched > 0 ? ((100 * (run.pages_fetched - run.pages_failed)) / run.pages_fetched).toFixed(0) : "—"}%
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* ERRORS */}
                      {run.errors.length > 0 && (
                        <div>
                          <h4 className="text-xs font-black uppercase tracking-widest text-red-400 mb-3">
                            🚨 Errors ({run.errors.length})
                          </h4>
                          <div className="space-y-2 max-h-48 overflow-y-auto">
                            {run.errors.map((err, i) => (
                              <div key={i} className="p-3 rounded border border-red-500/30 bg-red-500/5 text-xs">
                                <div className="font-mono text-red-400">{err.message}</div>
                                {err.detail && <div className="text-red-600 mt-1 text-[10px]">{err.detail}</div>}
                                {err.url && <div className="text-red-700 mt-1 text-[10px] truncate">{err.url}</div>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* WARNINGS */}
                      {run.warnings.length > 0 && (
                        <div>
                          <h4 className="text-xs font-black uppercase tracking-widest text-amber-400 mb-3">
                            ⚠️ Warnings ({run.warnings.length})
                          </h4>
                          <div className="space-y-2 max-h-32 overflow-y-auto">
                            {run.warnings.slice(0, 5).map((warn, i) => (
                              <div key={i} className="p-2 rounded border border-amber-500/30 bg-amber-500/5 text-xs text-amber-400">
                                {warn.message}
                              </div>
                            ))}
                            {run.warnings.length > 5 && (
                              <div className="text-xs text-amber-600">... and {run.warnings.length - 5} more warnings</div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* RUN ID */}
                      <div className="text-xs text-slate-600 pt-3 border-t border-slate-800">
                        <span>Run ID: </span>
                        <span className="font-mono text-slate-500">{run.id}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* PAGINATION */}
      {total > 100 && (
        <div className="mt-6 flex justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-cyan-500/30 rounded text-sm text-cyan-400 disabled:opacity-50"
          >
            ← Previous
          </button>
          <span className="px-4 py-2 text-sm text-slate-500">
            Page {page} of {Math.ceil(total / 100)}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= Math.ceil(total / 100)}
            className="px-4 py-2 border border-cyan-500/30 rounded text-sm text-cyan-400 disabled:opacity-50"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
