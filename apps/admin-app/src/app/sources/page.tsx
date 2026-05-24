"use client";

import { useEffect, useState, useCallback } from "react";
import { getSources, rescanSource, deleteSource, triggerIngest, importSeed, triggerReingestionAll, type Store, type SourceFilters } from "@/lib/api";
import { Badge, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSearch, FilterSelect, Btn } from "@/components/ui";

function fmtAge(iso: string | null, freqH: number): string {
  if (!iso) return "Never";
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
  if (h < 1) return "< 1h";
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

interface EditingStrategy {
  [key: string]: string;
}

type RecommendedAction = "detect" | "reingest" | "activate";

function getRecommendedAction(store: Store): RecommendedAction {
  if (!store.active_flag) return "activate";
  if (store.health_status === "no_pipeline" || store.health_status === "unknown") return "detect";
  return "reingest";
}

export default function SourcesPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<SourceFilters>({ active_only: true });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioning, setActioning] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [editingStrategy, setEditingStrategy] = useState<EditingStrategy>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSources({ ...filters, page, page_size: 200 });
      setStores(data.data);
      setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [filters, page]);

  useEffect(() => { setPage(1); }, [filters]);
  useEffect(() => { load(); }, [load]);

  const handleRescan = async (id: string, domain: string) => {
    setActioning(id);
    try {
      const r = await rescanSource(id);
      setBanner(`Rescanned ${domain} → ${r.parser_strategy} (${r.reachable ? "reachable" : "unreachable"})`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleReingest = async (id: string, domain: string) => {
    setActioning(`reingest-${id}`);
    try {
      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/admin/sources/${id}/reingest`, { method: 'POST' });
      if (!r.ok) throw new Error(await r.text());
      setBanner(`Re-ingestion queued for ${domain}`);
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleSeed = async () => {
    setActioning("seed");
    try {
      const r = await importSeed();
      setBanner(`Seed import: ${r.inserted} inserted, ${r.updated} updated, ${r.unreachable} unreachable`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleStrategyEdit = async (storeId: string, newStrategy: string) => {
    setActioning(`edit-strategy-${storeId}`);
    try {
      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/admin/sources/${storeId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parser_strategy: newStrategy })
      });
      if (!r.ok) throw new Error(await r.text());
      setBanner(`Parser strategy updated to ${newStrategy}`);
      setEditingStrategy(e => {
        const copy = { ...e };
        delete copy[storeId];
        return copy;
      });
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleBulkAction = async (action: RecommendedAction, targetStores: Store[]) => {
    if (targetStores.length === 0) return;
    setActioning(`bulk-${action}`);
    try {
      let successCount = 0;
      let errorCount = 0;

      for (const store of targetStores) {
        try {
          if (action === "detect") {
            await rescanSource(store.id);
            successCount++;
          } else if (action === "reingest") {
            const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/admin/sources/${store.id}/reingest`, { method: 'POST' });
            if (r.ok) successCount++;
            else errorCount++;
          } else if (action === "activate") {
            const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/admin/sources/${store.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ active_flag: true })
            });
            if (r.ok) successCount++;
            else errorCount++;
          }
        } catch (e) {
          errorCount++;
        }
      }

      const actionLabel = action === "detect" ? "Auto-detect" : action === "reingest" ? "Re-ingest" : "Activate";
      setBanner(`${actionLabel}: ${successCount} started${errorCount > 0 ? `, ${errorCount} failed` : ""}`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleBulkDelete = async (targetStores: Store[]) => {
    if (targetStores.length === 0) return;
    const confirmed = window.confirm(`⚠️ Permanently delete ${targetStores.length} roaster(s) and all their data?\n\nThis cannot be undone.`);
    if (!confirmed) return;

    setActioning("bulk-delete");
    try {
      let successCount = 0;
      let errorCount = 0;

      for (const store of targetStores) {
        try {
          await deleteSource(store.id);
          successCount++;
        } catch (e) {
          errorCount++;
        }
      }

      setBanner(`Deleted: ${successCount} roaster(s)${errorCount > 0 ? `, ${errorCount} failed` : ""}`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const handleDeleteSingle = async (id: string, domain: string) => {
    const confirmed = window.confirm(`⚠️ Permanently delete "${domain}" and all its data?\n\nThis cannot be undone.`);
    if (!confirmed) return;

    setActioning(`delete-${id}`);
    try {
      await deleteSource(id);
      setBanner(`Deleted: ${domain}`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setActioning(null); }
  };

  const setFilter = (k: keyof SourceFilters, v: unknown) => setFilters(f => ({ ...f, [k]: v || undefined }));

  // Group stores by recommended action
  const detectStores = stores.filter(s => getRecommendedAction(s) === "detect");
  const reingestStores = stores.filter(s => getRecommendedAction(s) === "reingest");
  const activateStores = stores.filter(s => getRecommendedAction(s) === "activate");

  const renderStoreTable = (title: string, action: RecommendedAction, storeList: Store[], actionLabel: string, actionLabelBulk: string) => {
    if (storeList.length === 0) return null;

    // For unknown sources, show both auto-detect and delete buttons
    const unknownStores = action === "detect" ? storeList.filter(s => s.health_status === "unknown") : [];

    return (
      <div key={action} className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-neutral-100">
            {title} <span className="text-xs text-neutral-500">({storeList.length})</span>
          </h2>
          <div className="flex gap-2">
            <Btn
              onClick={() => handleBulkAction(action, storeList)}
              disabled={actioning === `bulk-${action}`}
              variant="primary"
              size="sm"
            >
              {actioning === `bulk-${action}` ? "…" : actionLabelBulk}
            </Btn>
            {unknownStores.length > 0 && (
              <Btn
                onClick={() => handleBulkDelete(unknownStores)}
                disabled={actioning === "bulk-delete"}
                variant="default"
                size="sm"
                className="text-red-500 border-red-900 hover:border-red-700"
              >
                {actioning === "bulk-delete" ? "…" : `Delete ${unknownStores.length}`}
              </Btn>
            )}
          </div>
        </div>
        <DataTable headers={["Health", "Store / Domain", "Strategy", "Region", "Extraction Status", "Actions"]}>
          {storeList.flatMap(store => {
            const isActioning = actioning === store.id || actioning === `reingest-${store.id}` || actioning === `edit-strategy-${store.id}`;
            const crawlAge = fmtAge(store.last_successful_crawl_at, store.crawl_frequency_hours);
            const stale = store.last_successful_crawl_at && (Date.now() - new Date(store.last_successful_crawl_at).getTime()) / 3_600_000 > store.crawl_frequency_hours * 2;
            const lr = store.last_run;
            const hasErrors = lr != null && lr.error_count > 0;
            const isOpen = !!expanded[store.id];
            const isEditingStrategy = !!editingStrategy[store.id];

            const rows = [
              <tr key={store.id} className="border-b border-neutral-800/40 hover:bg-neutral-900/30 transition-colors group">
                <td className="px-4 py-2.5"><Badge value={store.health_status} /></td>
                <td className="px-4 py-2.5">
                  <div className="text-sm text-neutral-200">{store.name}</div>
                  <div className="text-xs font-mono text-neutral-600">{store.domain}</div>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1 items-center">
                    {isEditingStrategy ? (
                      <select
                        value={editingStrategy[store.id]}
                        onChange={(e) => setEditingStrategy(s => ({ ...s, [store.id]: e.target.value }))}
                        className="text-xs px-2 py-1 rounded bg-neutral-800 border border-neutral-700 text-neutral-200"
                        autoFocus
                      >
                        <option value="shopify">Shopify</option>
                        <option value="html">HTML</option>
                        <option value="schema_org">Schema.org</option>
                        <option value="llm">LLM</option>
                        <option value="unknown">Unknown</option>
                      </select>
                    ) : (
                      <button
                        onClick={() => setEditingStrategy(s => ({ ...s, [store.id]: store.parser_strategy }))}
                        className="cursor-pointer hover:opacity-70 transition-opacity"
                        title="Click to edit extraction strategy"
                      >
                        <Badge value={store.parser_strategy} />
                      </button>
                    )}
                    {isEditingStrategy && (
                      <div className="flex gap-1">
                        <Btn size="xs" variant="primary" onClick={() => handleStrategyEdit(store.id, editingStrategy[store.id])} disabled={!!actioning}>
                          Save
                        </Btn>
                        <Btn size="xs" onClick={() => setEditingStrategy(s => {
                          const copy = { ...s };
                          delete copy[store.id];
                          return copy;
                        })} disabled={!!actioning}>
                          Cancel
                        </Btn>
                      </div>
                    )}
                    {store.roaster_flag && <Badge value="roaster" label="roaster" />}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-xs text-neutral-500">{store.uk_region ?? "—"}</td>
                <td className="px-4 py-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className={stale ? "text-amber-500" : "text-neutral-500"}>{crawlAge}</span>
                    {lr && (
                      <span className="text-[10px] text-neutral-600">
                        {lr.records_seen > 0 && <span>· {lr.records_seen} products</span>}
                        {lr.error_count > 0 && <span className="text-rose-400 ml-1">· {lr.error_count} errors</span>}
                        {lr.warning_count > 0 && <span className="text-amber-500 ml-1">· {lr.warning_count} warnings</span>}
                      </span>
                    )}
                    {hasErrors && (
                      <button
                        onClick={() => setExpanded(e => ({ ...e, [store.id]: !e[store.id] }))}
                        className="text-[10px] text-neutral-500 hover:text-neutral-200 underline"
                      >{isOpen ? "hide errors" : "show errors"}</button>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right">
                  <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <a href={store.homepage_url} target="_blank" rel="noopener" title="Visit website"
                      className="text-[11px] text-neutral-600 hover:text-neutral-300 px-2 py-1 rounded border border-neutral-800 hover:border-neutral-600 transition-colors">↗</a>
                    {action === "detect" && (
                      <>
                        <Btn size="xs" onClick={() => handleRescan(store.id, store.domain)} disabled={isActioning}>
                          {actioning === store.id ? "…" : "Detect"}
                        </Btn>
                        {store.health_status === "unknown" && (
                          <Btn
                            size="xs"
                            onClick={() => handleDeleteSingle(store.id, store.domain)}
                            disabled={isActioning || actioning === `delete-${store.id}`}
                            className="text-red-500 hover:text-red-400"
                          >
                            {actioning === `delete-${store.id}` ? "…" : "Delete"}
                          </Btn>
                        )}
                      </>
                    )}
                    {action === "reingest" && (
                      <Btn size="xs" variant="primary" onClick={() => handleReingest(store.id, store.domain)} disabled={isActioning}>
                        {actioning === `reingest-${store.id}` ? "…" : "Re-ingest"}
                      </Btn>
                    )}
                    {action === "activate" && (
                      <Btn size="xs" variant="primary" disabled={isActioning}>
                        Activate
                      </Btn>
                    )}
                  </div>
                </td>
              </tr>
            ];

            if (isOpen && lr && lr.error_count > 0) {
              rows.push(
                <tr key={`${store.id}-errors`} className="bg-neutral-950/60 border-b border-neutral-800/40">
                  <td colSpan={6} className="px-6 py-4">
                    <div className="space-y-3">
                      <div className="text-[11px] uppercase tracking-wider text-neutral-600">
                        {lr.status.toUpperCase()} · {new Date(lr.started_at).toLocaleString()} · {lr.error_count} errors {lr.warning_count > 0 && `· ${lr.warning_count} warnings`}
                      </div>

                      {lr.error_count > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-rose-400">Error Types:</div>
                          <div className="grid grid-cols-1 gap-2 max-h-[300px] overflow-y-auto">
                            {Object.keys(lr.top_error_buckets || {}).length > 0 ? (
                              Object.entries(lr.top_error_buckets).map(([msg, count]) => (
                                <div key={msg} className="flex items-start gap-2 text-xs">
                                  <span className="font-mono text-rose-400 flex-shrink-0">{count}×</span>
                                  <span className="text-neutral-300 break-all">{msg}</span>
                                </div>
                              ))
                            ) : lr.top_errors && lr.top_errors.length > 0 ? (
                              lr.top_errors.map((err, i) => (
                                <div key={i} className="text-xs text-neutral-300">{err}</div>
                              ))
                            ) : (
                              <div className="text-xs text-neutral-500">No error details available.</div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              );
            }

            return rows;
          })}
        </DataTable>
      </div>
    );
  };

  return (
    <div className="p-6 max-w-7xl">
      <PageHeader
        title="Source Inventory"
        subtitle="UK coffee roasters grouped by recommended action."
        actions={
          <div className="flex gap-2">
            {total === 0 && (
              <Btn onClick={handleSeed} disabled={actioning === "seed"} variant="default">
                {actioning === "seed" ? "Importing…" : "Import seed CSV"}
              </Btn>
            )}
          </div>
        }
      />

      {banner && (
        <div className="mb-4 px-4 py-2.5 bg-emerald-900/20 border border-emerald-800/50 rounded text-sm text-emerald-400 flex items-center justify-between">
          {banner}
          <button onClick={() => setBanner(null)} className="text-emerald-700 hover:text-emerald-400">×</button>
        </div>
      )}
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      <FilterBar>
        <FilterSearch value={filters.q ?? ""} onChange={v => setFilter("q", v)} placeholder="Search by name or domain…" />
        <FilterSelect value={filters.parser_strategy ?? ""} onChange={v => setFilter("parser_strategy", v)} placeholder="All extraction strategies"
          options={[
            { value: "shopify", label: "Shopify API" },
            { value: "html", label: "HTML/DOM" },
            { value: "schema_org", label: "Schema.org" },
            { value: "llm", label: "LLM" },
            { value: "unknown", label: "Unknown" }
          ]} />
        <FilterSelect value={filters.health_status ?? ""} onChange={v => setFilter("health_status", v)} placeholder="All health statuses"
          options={[
            { value: "healthy", label: "✓ Healthy" },
            { value: "degraded", label: "⚠ Degraded" },
            { value: "failing", label: "✗ Failing" },
            { value: "stale", label: "⏱ Stale" },
            { value: "no_pipeline", label: "⊗ No Pipeline" },
            { value: "inactive", label: "⊗ Inactive" },
            { value: "unknown", label: "? Unknown" }
          ]} />
        <FilterSelect value={filters.uk_region ?? ""} onChange={v => setFilter("uk_region", v)} placeholder="All regions"
          options={["London","South West","Yorkshire","Midlands","Scotland","Wales","East of England"].map(v => ({ value: v, label: v }))} />
        <label title="Show only verified roaster sources" className="flex items-center gap-2 text-xs text-neutral-500 cursor-pointer select-none">
          <input type="checkbox" checked={!!filters.roaster_only} onChange={e => setFilter("roaster_only", e.target.checked)}
            className="accent-amber-500" />
          Roasters only
        </label>
        <span className="ml-auto text-xs text-neutral-600">{total} sources</span>
      </FilterBar>

      {loading ? (
        <div className="space-y-6">
          <div>
            <div className="h-6 bg-neutral-800 rounded w-48 mb-4" />
            <DataTable headers={["Health", "Store / Domain", "Strategy", "Region", "Extraction Status", "Actions"]}>
              <SkeletonRows cols={6} />
            </DataTable>
          </div>
        </div>
      ) : stores.length === 0 ? (
        <EmptyState message="No sources configured. Import the seed CSV to get started." action={<Btn onClick={handleSeed} variant="primary">Import seed CSV</Btn>} />
      ) : (
        <div className="space-y-8">
          {renderStoreTable(
            "🔍 Auto-detect Strategy",
            "detect",
            detectStores,
            "Detect",
            "Auto-detect All"
          )}
          {renderStoreTable(
            "♻️ Re-ingest",
            "reingest",
            reingestStores,
            "Re-ingest",
            "Re-ingest All"
          )}
          {renderStoreTable(
            "✓ Reactivate",
            "activate",
            activateStores,
            "Activate",
            "Activate All"
          )}
        </div>
      )}
    </div>
  );
}
