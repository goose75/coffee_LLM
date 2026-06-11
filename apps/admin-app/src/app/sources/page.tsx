"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { getSources, getIngestionRuns, rescanSource, triggerReingestionAll, type Store, type SourceFilters, type IngestionRun } from "@/lib/api";

// ============================================================================
// STATUS BADGE - Health status visual indicator
// ============================================================================
function HealthBadge({ status }: { status: string }) {
  const statusConfig = {
    healthy: { color: "bg-green-500/20 border-green-500 text-green-400", icon: "✓" },
    degraded: { color: "bg-amber-500/20 border-amber-500 text-amber-400", icon: "⚠" },
    stale: { color: "bg-amber-500/20 border-amber-500 text-amber-400", icon: "⏱" },
    failing: { color: "bg-red-500/20 border-red-500 text-red-400", icon: "✕" },
    no_pipeline: { color: "bg-slate-500/20 border-slate-500 text-slate-400", icon: "?" },
    unknown: { color: "bg-slate-500/20 border-slate-500 text-slate-400", icon: "?" },
    inactive: { color: "bg-slate-600/20 border-slate-600 text-slate-500", icon: "—" },
  };

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-mono ${config.color}`}>
      <span>{config.icon}</span>
      <span className="uppercase tracking-widest">{status}</span>
    </span>
  );
}

// ============================================================================
// PROGRESS BAR - Visual indicator of ingestion progress
// ============================================================================
function ProgressBar({ records_created, records_updated, error_count, max = 100 }: { records_created: number; records_updated: number; error_count: number; max?: number }) {
  const total = records_created + records_updated + error_count;
  const created_pct = (records_created / (total || max)) * 100;
  const updated_pct = (records_updated / (total || max)) * 100;
  const error_pct = (error_count / (total || max)) * 100;

  return (
    <div className="flex gap-1 h-1 rounded-full overflow-hidden bg-slate-800">
      {created_pct > 0 && <div className="bg-green-500" style={{ width: `${created_pct}%` }} />}
      {updated_pct > 0 && <div className="bg-blue-500" style={{ width: `${updated_pct}%` }} />}
      {error_pct > 0 && <div className="bg-red-500" style={{ width: `${error_pct}%` }} />}
    </div>
  );
}

// ============================================================================
// MAIN SOURCES PAGE
// ============================================================================
export default function SourcesPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterStrategy, setFilterStrategy] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<"name" | "status" | "updated">("name");

  // Load data
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const filters: SourceFilters = {
        page,
        page_size: 100,
        q: search || undefined,
        health_status: filterStatus || undefined,
        parser_strategy: filterStrategy || undefined,
        active_only: false,
      };

      const [sourcesData, runsData] = await Promise.all([
        getSources(filters),
        getIngestionRuns({ page_size: 50 }),
      ]);

      setStores(sourcesData.data);
      setTotal(sourcesData.total);
      setRuns(runsData.data);
    } catch (e) {
      console.error("Failed to load sources:", e);
      setMessage("Failed to load sources");
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, filterStrategy]);

  useEffect(() => {
    load();
  }, [load]);

  // Sort stores
  const sortedStores = useMemo(() => {
    const copy = [...stores];
    if (sortBy === "name") {
      copy.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === "status") {
      const statusOrder = { healthy: 0, degraded: 1, stale: 2, failing: 3, no_pipeline: 4, unknown: 5, inactive: 6 };
      copy.sort((a, b) => {
        const aOrder = statusOrder[a.health_status as keyof typeof statusOrder] ?? 99;
        const bOrder = statusOrder[b.health_status as keyof typeof statusOrder] ?? 99;
        return aOrder - bOrder;
      });
    } else if (sortBy === "updated") {
      copy.sort((a, b) => {
        const aTime = a.last_successful_crawl_at ? new Date(a.last_successful_crawl_at).getTime() : 0;
        const bTime = b.last_successful_crawl_at ? new Date(b.last_successful_crawl_at).getTime() : 0;
        return bTime - aTime;
      });
    }
    return copy;
  }, [stores, sortBy]);

  // Calculate stats
  const stats = useMemo(() => {
    const active = stores.filter(s => s.active_flag).length;
    const healthy = stores.filter(s => s.health_status === "healthy").length;
    const stale = stores.filter(s => s.health_status === "stale").length;
    const failing = stores.filter(s => s.health_status === "failing").length;
    const no_pipeline = stores.filter(s => s.health_status === "no_pipeline").length;
    return { active, healthy, stale, failing, no_pipeline };
  }, [stores]);

  // Bulk actions
  const handleBulkReingest = async () => {
    if (selected.size === 0) return;
    setActioning("bulk-reingest");
    try {
      let count = 0;
      for (const storeId of selected) {
        try {
          await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/admin/sources/${storeId}/reingest`, {
            method: 'POST',
          });
          count++;
        } catch (e) {
          console.error("Reingest failed for", storeId, e);
        }
      }
      setMessage(`Re-ingestion queued for ${count} store(s)`);
      setSelected(new Set());
      await load();
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setActioning(null);
    }
  };

  const handleBulkDetect = async () => {
    if (selected.size === 0) return;
    setActioning("bulk-detect");
    try {
      let count = 0;
      for (const storeId of selected) {
        try {
          await rescanSource(storeId);
          count++;
        } catch (e) {
          console.error("Detect failed for", storeId, e);
        }
      }
      setMessage(`Auto-detect completed for ${count} store(s)`);
      setSelected(new Set());
      await load();
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setActioning(null);
    }
  };

  const handleBulkLLMAssist = async () => {
    if (selected.size === 0) return;
    setActioning("bulk-llm");
    try {
      // Queue for LLM assist - redirect to LLM assist page with selected stores
      const ids = Array.from(selected).join(",");
      window.location.href = `/admin/llm-assist?stores=${ids}`;
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
      setActioning(null);
    }
  };

  const toggleSelect = (storeId: string) => {
    const newSelected = new Set(selected);
    if (newSelected.has(storeId)) {
      newSelected.delete(storeId);
    } else {
      newSelected.add(storeId);
    }
    setSelected(newSelected);
  };

  const toggleSelectAll = () => {
    if (selected.size === sortedStores.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sortedStores.map(s => s.id)));
    }
  };

  const filteredCount = sortedStores.length;
  const selectedCount = selected.size;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono">
      {/* HEADER */}
      <div className="mb-8">
        <h1 className="text-4xl font-black text-cyan-400 mb-2" style={{ textShadow: "0 0 20px rgba(34, 211, 238, 0.5)" }}>
          🏪 SOURCES
        </h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest">Manage {total} roasters and retailers</p>
      </div>

      {/* STATS BAR */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        <div className="border border-cyan-500/30 rounded bg-cyan-500/5 p-4">
          <div className="text-sm font-black text-cyan-400">{stats.active}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Active</div>
        </div>
        <div className="border border-green-500/30 rounded bg-green-500/5 p-4">
          <div className="text-sm font-black text-green-400">{stats.healthy}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Healthy</div>
        </div>
        <div className="border border-amber-500/30 rounded bg-amber-500/5 p-4">
          <div className="text-sm font-black text-amber-400">{stats.stale}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Stale</div>
        </div>
        <div className="border border-red-500/30 rounded bg-red-500/5 p-4">
          <div className="text-sm font-black text-red-400">{stats.failing}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Failing</div>
        </div>
        <div className="border border-slate-500/30 rounded bg-slate-500/5 p-4">
          <div className="text-sm font-black text-slate-400">{stats.no_pipeline}</div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">No Pipeline</div>
        </div>
      </div>

      {/* MESSAGE */}
      {message && (
        <div className="mb-6 p-4 border border-green-500/50 rounded bg-green-500/5 text-sm text-green-400">
          {message}
        </div>
      )}

      {/* CONTROLS */}
      <div className="mb-6 space-y-4">
        {/* Filters */}
        <div className="flex gap-4 flex-wrap">
          <input
            type="text"
            placeholder="Search stores..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-400"
          />

          <select
            value={filterStatus}
            onChange={(e) => {
              setFilterStatus(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400"
          >
            <option value="">All Status</option>
            <option value="healthy">Healthy</option>
            <option value="stale">Stale</option>
            <option value="failing">Failing</option>
            <option value="no_pipeline">No Pipeline</option>
          </select>

          <select
            value={filterStrategy}
            onChange={(e) => {
              setFilterStrategy(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400"
          >
            <option value="">All Parsers</option>
            <option value="shopify">Shopify</option>
            <option value="html">HTML</option>
            <option value="schema_org">Schema.org</option>
            <option value="llm">LLM</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="px-3 py-2 border border-cyan-500/30 rounded bg-cyan-500/5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400 ml-auto"
          >
            <option value="name">Sort by Name</option>
            <option value="status">Sort by Status</option>
            <option value="updated">Sort by Updated</option>
          </select>
        </div>

        {/* Bulk Actions */}
        {selectedCount > 0 && (
          <div className="flex gap-2 items-center p-4 border border-amber-500/30 rounded bg-amber-500/5">
            <span className="text-sm font-mono text-amber-400">{selectedCount} selected</span>
            <button
              onClick={handleBulkReingest}
              disabled={actioning === "bulk-reingest"}
              className="px-3 py-1 text-xs border border-cyan-500/50 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 disabled:opacity-50 transition"
            >
              🔄 Reingest
            </button>
            <button
              onClick={handleBulkDetect}
              disabled={actioning === "bulk-detect"}
              className="px-3 py-1 text-xs border border-blue-500/50 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 disabled:opacity-50 transition"
            >
              🔍 Auto-Detect
            </button>
            <button
              onClick={handleBulkLLMAssist}
              disabled={actioning === "bulk-llm"}
              className="px-3 py-1 text-xs border border-green-500/50 rounded bg-green-500/10 hover:bg-green-500/20 text-green-400 disabled:opacity-50 transition"
            >
              🤖 LLM Assist
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="px-3 py-1 text-xs border border-slate-500/50 rounded bg-slate-500/10 hover:bg-slate-500/20 text-slate-400 transition ml-auto"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* STORES TABLE */}
      <div className="border border-cyan-500/20 rounded bg-slate-900/50 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-cyan-500/20 bg-cyan-500/5">
              <th className="px-4 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedCount === filteredCount && filteredCount > 0}
                  onChange={toggleSelectAll}
                  className="cursor-pointer"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-widest text-slate-400">Store</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-widest text-slate-400">Status</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-widest text-slate-400">Parser</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-widest text-slate-400">Last Run</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-widest text-slate-400">Progress</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : sortedStores.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No stores found
                </td>
              </tr>
            ) : (
              sortedStores.map((store) => {
                const isSelected = selected.has(store.id);
                const lastRun = store.last_run;

                return (
                  <tr
                    key={store.id}
                    className={`border-b border-slate-800 hover:bg-slate-800/50 transition ${isSelected ? "bg-cyan-500/10" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(store.id)}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-mono text-slate-100">{store.name}</div>
                        <div className="text-xs text-slate-600">{store.domain}</div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <HealthBadge status={store.health_status} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono bg-slate-800/50 px-2 py-1 rounded text-slate-300">
                        {store.parser_strategy}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs">
                        {lastRun ? (
                          <>
                            <div className="text-slate-400">{lastRun.status}</div>
                            <div className="text-slate-600 mt-1">
                              {new Date(lastRun.started_at).toLocaleString()}
                            </div>
                          </>
                        ) : (
                          <span className="text-slate-600">Never</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {lastRun && (
                        <div>
                          <ProgressBar
                            records_created={lastRun.records_created}
                            records_updated={lastRun.records_updated}
                            error_count={lastRun.error_count}
                          />
                          <div className="text-[10px] text-slate-600 mt-1">
                            {lastRun.records_created}✓ {lastRun.records_updated}↑ {lastRun.error_count}✕
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
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
