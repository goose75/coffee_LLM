"use client";

import { useEffect, useState, useCallback } from "react";
import { getIngestionRuns, type IngestionRun, type IngestionFilters } from "@/lib/api";
import { Badge, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSelect, Btn } from "@/components/ui";

function dur(s: number | null) {
  if (s === null) return "—";
  return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60).toFixed(1)}m`;
}

export default function IngestionRunsPage() {
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<IngestionFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIngestionRuns({ ...filters, page, page_size: 50 });
      setRuns(data.data);
      setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [filters, page]);

  useEffect(() => { setPage(1); }, [filters]);
  useEffect(() => { load(); }, [load]);

  // Auto-refresh while any run is active
  useEffect(() => {
    const hasActive = runs.some(r => r.status === "running");
    if (!hasActive) return;
    const id = setInterval(load, 8_000);
    return () => clearInterval(id);
  }, [runs, load]);

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader
        title="Ingestion Runs"
        subtitle="History of all ingestion jobs, newest first."
        actions={<Btn onClick={load}>↻ Refresh</Btn>}
      />
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      <FilterBar>
        <FilterSelect value={filters.status ?? ""} onChange={v => setFilters(f => ({ ...f, status: v || undefined }))} placeholder="All statuses"
          options={["completed","running","failed","partial"].map(v => ({ value: v, label: v }))} />
        <FilterSelect value={filters.run_type ?? ""} onChange={v => setFilters(f => ({ ...f, run_type: v || undefined }))} placeholder="All types"
          options={["full","incremental","single_store","single_page"].map(v => ({ value: v, label: v.replace("_"," ") }))} />
        <span className="text-xs text-neutral-600">{total} runs</span>
      </FilterBar>

      <div className="border border-neutral-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-800 bg-neutral-900/60">
              {["Status","Type","Started","Duration","Records","Issues",""].map((h,i) => (
                <th key={i} className="px-4 py-2.5 text-left text-[11px] font-medium text-neutral-600 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? <SkeletonRows cols={7} /> : runs.length === 0 ? (
              <tr><td colSpan={7}><EmptyState message="No ingestion runs yet. Trigger one from the Sources page." /></td></tr>
            ) : runs.map(run => (
              <>
                <tr key={run.id} onClick={() => setExpanded(expanded === run.id ? null : run.id)}
                  className={`border-b border-neutral-800/40 hover:bg-neutral-900/30 cursor-pointer transition-colors ${expanded === run.id ? "bg-neutral-900/40" : ""}`}>
                  <td className="px-4 py-2.5"><Badge value={run.status} dot /></td>
                  <td className="px-4 py-2.5 text-xs text-neutral-500 font-mono">{run.run_type}</td>
                  <td className="px-4 py-2.5 text-xs text-neutral-500">
                    {new Date(run.started_at).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">{dur(run.duration_seconds)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-2 text-xs">
                      <span className="text-neutral-500">{run.records_seen}</span>
                      {run.records_created > 0 && <span className="text-emerald-600">+{run.records_created}</span>}
                      {run.records_updated > 0 && <span className="text-blue-600">↑{run.records_updated}</span>}
                      {run.records_unchanged > 0 && <span className="text-neutral-700">={run.records_unchanged}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-2 text-xs">
                      {run.error_count > 0 && <span className="text-red-500">{run.error_count} err</span>}
                      {run.warning_count > 0 && <span className="text-amber-500">{run.warning_count} warn</span>}
                      {run.error_count === 0 && run.warning_count === 0 && <span className="text-neutral-700">—</span>}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-neutral-700 text-xs">{expanded === run.id ? "▲" : "▼"}</td>
                </tr>
                {expanded === run.id && (
                  <tr key={`${run.id}-detail`} className="bg-neutral-950 border-b border-neutral-800">
                    <td colSpan={7} className="px-6 py-4">
                      <div className="grid grid-cols-4 gap-4 mb-3 text-xs text-neutral-600">
                        <div>Pages fetched: <span className="text-neutral-400">{run.pages_fetched}</span>{run.pages_failed > 0 && <span className="text-red-500 ml-2">{run.pages_failed} failed</span>}</div>
                        <div>Run ID: <span className="font-mono text-neutral-700 text-[10px]">{run.id.slice(0,8)}…</span></div>
                        {run.completed_at && <div>Completed: <span className="text-neutral-400">{new Date(run.completed_at).toLocaleTimeString("en-GB")}</span></div>}
                      </div>
                      {run.errors.length > 0 && (
                        <div className="mb-2">
                          <div className="text-[10px] uppercase tracking-wider text-red-600 mb-1">Errors</div>
                          <div className="space-y-1">
                            {run.errors.map((e, i) => (
                              <div key={i} className="text-xs text-red-400 bg-red-950/30 border border-red-900/40 rounded px-3 py-1.5">
                                {e.message}{e.detail && <span className="text-red-700"> — {e.detail}</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {run.warnings.length > 0 && (
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-amber-600 mb-1">Warnings ({run.warnings.length})</div>
                          <div className="space-y-0.5 max-h-32 overflow-y-auto">
                            {run.warnings.map((w, i) => (
                              <div key={i} className="text-xs text-amber-500/70 truncate">{w.message}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} total={total} pageSize={50} onPage={setPage} />
    </div>
  );
}
