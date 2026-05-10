"use client";

import { useEffect, useState, useCallback } from "react";
import { getSources, rescanSource, triggerIngest, importSeed, type Store, type SourceFilters } from "@/lib/api";
import { Badge, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSearch, FilterSelect, Btn } from "@/components/ui";

function fmtAge(iso: string | null, freqH: number): string {
  if (!iso) return "Never";
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
  if (h < 1) return "< 1h";
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
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

  const setFilter = (k: keyof SourceFilters, v: unknown) => setFilters(f => ({ ...f, [k]: v || undefined }));

  return (
    <div className="p-6 max-w-7xl">
      <PageHeader
        title="Source Inventory"
        subtitle="All tracked UK coffee domains with detection strategy and crawl health."
        actions={
          <Btn onClick={handleSeed} disabled={actioning === "seed"} variant="primary">
            {actioning === "seed" ? "Importing…" : "Import seed CSV"}
          </Btn>
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
        <FilterSearch value={filters.q ?? ""} onChange={v => setFilter("q", v)} placeholder="Name or domain…" />
        <FilterSelect value={filters.parser_strategy ?? ""} onChange={v => setFilter("parser_strategy", v)} placeholder="All strategies"
          options={["shopify","schema_org","html","llm","unknown"].map(v => ({ value: v, label: v }))} />
        <FilterSelect value={filters.health_status ?? ""} onChange={v => setFilter("health_status", v)} placeholder="All health"
          options={["healthy","degraded","failing","stale","unknown","no_pipeline","inactive"].map(v => ({ value: v, label: v }))} />
        <FilterSelect value={filters.uk_region ?? ""} onChange={v => setFilter("uk_region", v)} placeholder="All regions"
          options={["London","South West","Yorkshire","Midlands","Scotland","Wales","East of England"].map(v => ({ value: v, label: v }))} />
        <label className="flex items-center gap-2 text-xs text-neutral-500 cursor-pointer select-none">
          <input type="checkbox" checked={!!filters.roaster_only} onChange={e => setFilter("roaster_only", e.target.checked)}
            className="accent-amber-500" />
          Roasters only
        </label>
        <label className="flex items-center gap-2 text-xs text-neutral-500 cursor-pointer select-none">
          <input type="checkbox" checked={filters.active_only !== false} onChange={e => setFilter("active_only", e.target.checked)}
            className="accent-amber-500" />
          Active only
        </label>
        <span className="ml-auto text-xs text-neutral-600">{total} sources</span>
      </FilterBar>

      <DataTable headers={["Health", "Store / Domain", "Strategy", "Region", "Last run", ""]}>
        {loading ? <SkeletonRows cols={6} /> : stores.length === 0 ? (
          <tr><td colSpan={6}><EmptyState message="No sources. Import the seed CSV to get started." action={<Btn onClick={handleSeed} variant="primary">Import seed CSV</Btn>} /></td></tr>
        ) : stores.flatMap(store => {
          const isActioning = actioning === store.id || actioning === `ingest-${store.id}`;
          const crawlAge = fmtAge(store.last_successful_crawl_at, store.crawl_frequency_hours);
          const stale = store.last_successful_crawl_at && (Date.now() - new Date(store.last_successful_crawl_at).getTime()) / 3_600_000 > store.crawl_frequency_hours * 2;
          const lr = store.last_run;
          const hasErrors = lr != null && lr.error_count > 0;
          const isOpen = !!expanded[store.id];
          const rows = [
            <tr key={store.id} className="border-b border-neutral-800/40 hover:bg-neutral-900/30 transition-colors group">
              <td className="px-4 py-2.5"><Badge value={store.health_status} /></td>
              <td className="px-4 py-2.5">
                <div className="text-sm text-neutral-200">{store.name}</div>
                <div className="text-xs font-mono text-neutral-600">{store.domain}</div>
              </td>
              <td className="px-4 py-2.5">
                <div className="flex flex-wrap gap-1">
                  <Badge value={store.parser_strategy} />
                  {store.roaster_flag && <Badge value="roaster" label="roaster" />}
                </div>
              </td>
              <td className="px-4 py-2.5 text-xs text-neutral-500">{store.uk_region ?? "—"}</td>
              <td className="px-4 py-2.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className={stale ? "text-amber-500" : "text-neutral-500"}>{crawlAge}</span>
                  {lr && (
                    <span className="text-[10px] text-neutral-600">
                      · {lr.records_seen} seen
                      {lr.error_count > 0 && <span className="text-rose-400 ml-1">· {lr.error_count} err</span>}
                      {lr.warning_count > 0 && <span className="text-amber-500 ml-1">· {lr.warning_count} warn</span>}
                    </span>
                  )}
                  {hasErrors && (
                    <button
                      onClick={() => setExpanded(e => ({ ...e, [store.id]: !e[store.id] }))}
                      className="text-[10px] text-neutral-500 hover:text-neutral-200 underline"
                    >{isOpen ? "hide" : "why?"}</button>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5 text-right">
                <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <a href={store.homepage_url} target="_blank" rel="noopener"
                    className="text-[11px] text-neutral-600 hover:text-neutral-300 px-2 py-1 rounded border border-neutral-800 hover:border-neutral-600 transition-colors">↗</a>
                  <Btn size="xs" onClick={() => handleRescan(store.id, store.domain)} disabled={isActioning}>
                    {actioning === store.id ? "…" : "Rescan"}
                  </Btn>
                  {store.parser_strategy === "shopify" && (
                    <Btn size="xs" variant="primary" onClick={() => handleIngest(store.id, store.domain)} disabled={isActioning}>
                      {actioning === `ingest-${store.id}` ? "…" : "Ingest"}
                    </Btn>
                  )}
                </div>
              </td>
            </tr>
          ];
          if (isOpen && lr) {
            rows.push(
              <tr key={`${store.id}-detail`} className="bg-neutral-950/60 border-b border-neutral-800/40">
                <td colSpan={6} className="px-6 py-3">
                  <div className="text-[11px] uppercase tracking-wider text-neutral-600 mb-2">
                    Last run · {lr.status} · {new Date(lr.started_at).toLocaleString()}
                  </div>
                  {Object.keys(lr.top_error_buckets).length > 0 ? (
                    <div className="space-y-1">
                      {Object.entries(lr.top_error_buckets).map(([msg, count]) => (
                        <div key={msg} className="flex items-start gap-3 text-xs">
                          <span className="font-mono text-rose-400 min-w-[2rem]">{count}×</span>
                          <span className="text-neutral-300 break-all">{msg}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-neutral-500">No grouped errors recorded.</div>
                  )}
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
