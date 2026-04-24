"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getCanonicalBeans, type CanonicalBean } from "@/lib/api";
import { Badge, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSearch, FilterSelect, CompletenessRing } from "@/components/ui";

export default function BeansPage() {
  const [beans, setBeans] = useState<CanonicalBean[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [processFilter, setProcessFilter] = useState("");
  const [roastFilter, setRoastFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCanonicalBeans({ q: q || undefined, process: processFilter || undefined, roast_level: roastFilter || undefined, page, page_size: 50 });
      setBeans(data.data);
      setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [q, processFilter, roastFilter, page]);

  useEffect(() => { setPage(1); }, [q, processFilter, roastFilter]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader title="Canonical Beans" subtitle={`${total} deduplicated coffee entities`} />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      <FilterBar>
        <FilterSearch value={q} onChange={setQ} placeholder="Search name or origin…" />
        <FilterSelect value={processFilter} onChange={setProcessFilter} placeholder="All processes"
          options={["washed","natural","honey","anaerobic","wet_hulled","carbonic_maceration","experimental"].map(v => ({ value: v, label: v.replace("_"," ") }))} />
        <FilterSelect value={roastFilter} onChange={setRoastFilter} placeholder="All roasts"
          options={["light","medium_light","medium","medium_dark","dark"].map(v => ({ value: v, label: v.replace("_"," ") }))} />
        <span className="text-xs text-neutral-600 ml-auto">{total} beans</span>
      </FilterBar>

      <DataTable headers={["Name", "Origin", "Process", "Roast", "Varietal", "Harvest", "Complete", ""]}>
        {loading ? <SkeletonRows cols={8} /> : beans.length === 0 ? (
          <tr><td colSpan={8}><EmptyState message="No canonical beans found." /></td></tr>
        ) : beans.map(bean => (
          <tr key={bean.id} className="border-b border-neutral-800/40 hover:bg-neutral-900/30 transition-colors group">
            <td className="px-4 py-2.5">
              <div className="text-sm text-neutral-200 max-w-xs truncate">{bean.canonical_name}</div>
              {bean.farm_or_estate && <div className="text-xs text-neutral-600 truncate">{bean.farm_or_estate}</div>}
            </td>
            <td className="px-4 py-2.5 text-xs text-neutral-400">
              {[bean.origin_country, bean.origin_region].filter(Boolean).join(", ") || <span className="text-neutral-700">—</span>}
            </td>
            <td className="px-4 py-2.5">
              {bean.process ? <Badge value={bean.process} /> : <span className="text-neutral-700 text-xs">—</span>}
            </td>
            <td className="px-4 py-2.5">
              {bean.roast_level ? <Badge value={bean.roast_level} /> : <span className="text-neutral-700 text-xs">—</span>}
            </td>
            <td className="px-4 py-2.5 text-xs text-neutral-500 max-w-[120px] truncate">
              {bean.varietal?.join(", ") || <span className="text-neutral-700">—</span>}
            </td>
            <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">{bean.harvest_year ?? "—"}</td>
            <td className="px-4 py-2.5"><CompletenessRing value={bean.data_completeness_score} /></td>
            <td className="px-4 py-2.5 text-right opacity-0 group-hover:opacity-100 transition-opacity">
              <Link href={`/beans/${bean.id}`}
                className="text-xs text-amber-600 hover:text-amber-400 px-2 py-1 rounded border border-amber-800/50 hover:border-amber-600 transition-colors">
                Edit →
              </Link>
            </td>
          </tr>
        ))}
      </DataTable>
      <Pagination page={page} total={total} pageSize={50} onPage={setPage} />
    </div>
  );
}
