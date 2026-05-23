"use client";

import { useEffect, useState, useCallback } from "react";
import { getSources, rescanSource, triggerIngest, importSeed, triggerReingestionAll, type Store, type SourceFilters } from "@/lib/api";
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
      const data = await getSources({ ...filters, page, page_size: 50 });
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

  const handleIngest = async (id: string, domain: string) => {
    setActioning(`ingest-${id}`);
    try {
      const r = await triggerIngest(id);
      setBanner(`Ingestion triggered for ${domain}`);
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

  const handleReingestionAll = async () => {
    setActioning("reingest-all");
    try {
      const r = await triggerReingestionAll();
      setBanner(`Re-ingestion triggered for all sources${r.started_count ? ` (${r.started_count} sources)` : ""}`);
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

  const setFilter = (k: keyof SourceFilters, v: unknown) => setFilters(f => ({ ...f, [k]: v || undefined }));

  return (
    <div className="p-6 max-w-7xl">
      <PageHeader
        title="Source Inventory"
        subtitle="All tracked UK coffee domains with detection strategy and crawl health."
        actions={
          <div className="flex gap-2">
            <Btn onClick={handleReingestionAll} disabled={actioning === "reingest-all"} variant="primary">
              {actioning === "reingest-all" ? "Re-scanning…" : "Re-scan All Sources"}
            </Btn>
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
        <label title="Hide inactive/archived sources" className="flex items-center gap-2 text-xs text-neutral-500 cursor-pointer select-none">
          <input type="checkbox" checked={filters.active_only !== false} onChange={e => setFilter("active_only", e.target.checked)}
            className="accent-amber-500" />
          Active only
        </label>
        <span className="ml-auto text-xs text-neutral-600">{total} sources</span>
      </FilterBar>

      <DataTable headers={["Health", "Store / Domain", "Strategy", "Region", "Extraction Status", "Actions"]}>
        {loading ? <SkeletonRows cols={6} /> : stores.length === 0 ? (
          <tr><td colSpan={6}><EmptyState message="No sources configured. Import the seed CSV to get started." action={<Btn onClick={handleSeed} variant="primary">Import seed CSV</Btn>} /></td></tr>
        ) : stores.flatMap(store => {
          const isActioning = actioning === store.id || actioning === `ingest-${store.id}` || actioning === `reingest-${store.id}` || actioning === `edit-strategy-${store.id}`;
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
                  <Btn size="xs" onClick={() => handleRescan(store.id, store.domain)} disabled={isActioning}>
                    {actioning === store.id ? "…" : "Detect"}
                  </Btn>
                  <Btn size="xs" variant="primary" onClick={() => handleReingest(store.id, store.domain)} disabled={isActioning}>
                    {actioning === `reingest-${store.id}` ? "…" : "Re-ingest"}
                  </Btn>
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
      <Pagination page={page} total={total} pageSize={50} onPage={setPage} />
    </div>
  );
}
