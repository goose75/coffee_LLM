"use client";

import { useEffect, useState, useCallback } from "react";
import { getExtractionFailures, type RawExtraction } from "@/lib/api";
import { Badge, ConfidenceBar, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, Mono, FilterBar, FilterSelect } from "@/components/ui";

function PayloadInspector({ payload, errors }: { payload: Record<string, unknown>; errors: string[] | null }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)}
        className="text-xs text-amber-600 hover:text-amber-400 underline underline-offset-2">
        {open ? "Hide payload" : "Inspect payload"}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {errors && errors.length > 0 && (
            <div className="bg-red-950/40 border border-red-900/50 rounded p-3">
              <div className="text-[10px] uppercase tracking-wider text-red-600 mb-1.5">Validation errors</div>
              {errors.map((e, i) => (
                <div key={i} className="text-xs text-red-400 font-mono">{e}</div>
              ))}
            </div>
          )}
          <pre className="text-[11px] font-mono text-neutral-400 bg-neutral-900 border border-neutral-800 rounded p-3 overflow-x-auto max-h-48 leading-relaxed">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function ExtractionsPage() {
  const [extractions, setExtractions] = useState<RawExtraction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [methodFilter, setMethodFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getExtractionFailures(page, 30);
      setExtractions(data.data);
      setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const filtered = methodFilter ? extractions.filter(e => e.extraction_method === methodFilter) : extractions;

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader
        title="Extraction Failures"
        subtitle="Raw extractions that failed schema validation or returned low confidence."
        actions={<button onClick={load} className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 transition-colors">↻ Refresh</button>}
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      <FilterBar>
        <FilterSelect
          value={methodFilter}
          onChange={v => { setMethodFilter(v); setPage(1); }}
          placeholder="All methods"
          options={[
            { value: "shopify_json", label: "Shopify JSON" },
            { value: "schema_org", label: "Schema.org" },
            { value: "html_rules", label: "HTML Rules" },
            { value: "llm", label: "LLM" },
          ]}
        />
        <span className="text-xs text-neutral-600">{total} failures</span>
      </FilterBar>

      <DataTable headers={["Method", "Status", "Confidence", "Created", "Errors", "Payload"]}>
        {loading ? <SkeletonRows cols={6} /> : filtered.length === 0 ? (
          <tr><td colSpan={6}><EmptyState message="No extraction failures. Everything is healthy." /></td></tr>
        ) : filtered.map(ex => (
          <tr key={ex.id} className="border-b border-neutral-800/40 hover:bg-neutral-900/30 transition-colors">
            <td className="px-4 py-3"><Badge value={ex.extraction_method} /></td>
            <td className="px-4 py-3"><Badge value={ex.validation_status} /></td>
            <td className="px-4 py-3"><ConfidenceBar value={ex.confidence_score} /></td>
            <td className="px-4 py-3 text-xs text-neutral-500">
              {new Date(ex.created_at).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
            </td>
            <td className="px-4 py-3 max-w-xs">
              {ex.validation_errors?.errors?.slice(0, 2).map((e, i) => (
                <div key={i} className="text-xs text-red-400 truncate">{e}</div>
              ))}
              {!ex.validation_errors?.errors?.length && <span className="text-neutral-700 text-xs">—</span>}
            </td>
            <td className="px-4 py-3">
              <PayloadInspector
                payload={ex.extracted_payload}
                errors={ex.validation_errors?.errors ?? null}
              />
            </td>
          </tr>
        ))}
      </DataTable>

      <Pagination page={page} total={total} pageSize={30} onPage={setPage} />
    </div>
  );
}
