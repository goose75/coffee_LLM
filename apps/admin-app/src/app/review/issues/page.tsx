"use client";

import { useEffect, useState } from "react";
import { getDataQuality, type DataQualityReport, type DataQualityIssue } from "@/lib/api";
import { PageHeader, ErrorBanner, Btn, Badge } from "@/components/ui";

const SEVERITY_COLOURS: Record<string, string> = {
  high: "border-red-700 bg-red-950/30 text-red-300",
  medium: "border-amber-700 bg-amber-950/20 text-amber-300",
  low: "border-neutral-700 bg-neutral-900/30 text-neutral-400",
};

const TYPE_LABELS: Record<string, string> = {
  field_disagreement: "Field disagreement",
  duplicate_suspect: "Duplicate suspect",
  stale_auto_accept: "Stale auto-accept",
  very_sparse: "Very sparse",
};

function IssueRow({ issue }: { issue: DataQualityIssue }) {
  const sev = SEVERITY_COLOURS[issue.severity] ?? SEVERITY_COLOURS.low;
  return (
    <div className={`border rounded-lg p-3 mb-2 ${sev}`}>
      <div className="flex items-center gap-2 mb-1">
        <Badge value={issue.severity} />
        <span className="text-xs text-neutral-500">{TYPE_LABELS[issue.issue_type] ?? issue.issue_type}</span>
        <a href={`/beans/${issue.bean_id}`} className="text-sm text-neutral-200 hover:underline ml-auto">
          {issue.canonical_name} →
        </a>
      </div>
      <div className="text-xs text-neutral-300 mb-1">{issue.summary}</div>

      {issue.field_disagreements.length > 0 && (
        <div className="mt-2 grid grid-cols-[80px_1fr_1fr_60px] gap-2 text-[11px]">
          <span className="text-neutral-600">Field</span>
          <span className="text-neutral-600">Canonical says</span>
          <span className="text-neutral-600">Listings say (majority)</span>
          <span className="text-neutral-600 text-right">Disagree</span>
          {issue.field_disagreements.map(d => (
            <>
              <span className="text-neutral-300">{d.field}</span>
              <span className="text-neutral-400 truncate" title={d.canonical_value ?? ""}>{d.canonical_value ?? "—"}</span>
              <span className="text-amber-400 truncate" title={d.listing_majority_value ?? ""}>{d.listing_majority_value ?? "—"}</span>
              <span className="text-right font-mono text-neutral-500">{d.listings_disagreeing}/{d.total_listings}</span>
            </>
          ))}
        </div>
      )}

      {issue.duplicate_of_bean_id && (
        <div className="mt-2 text-[11px] text-neutral-500">
          Other bean: <a href={`/beans/${issue.duplicate_of_bean_id}`} className="text-neutral-300 hover:underline">{issue.duplicate_of_name}</a>
          <span className="ml-2 text-neutral-600">— consider merging via the bean detail page.</span>
        </div>
      )}
    </div>
  );
}

export default function ReviewIssuesPage() {
  const [data, setData] = useState<DataQualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");

  const load = async () => {
    setLoading(true); setError(null);
    try { setData(await getDataQuality()); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = data?.issues.filter(i => filterType === "all" || i.issue_type === filterType) ?? [];

  return (
    <div className="p-6 max-w-5xl">
      <PageHeader
        title="Match Review · Issues"
        subtitle="Canonical beans worth a second look — disagreements, duplicates, and overly sparse records."
        actions={
          <div className="flex gap-2">
            <a href="/review/matches" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Queue</a>
            <a href="/review/analytics" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Analytics</a>
            <Btn onClick={load}>↻ Refresh</Btn>
          </div>
        }
      />
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {loading || !data ? (
        <div className="text-sm text-neutral-600">Loading issues…</div>
      ) : (
        <>
          <div className="flex items-center gap-2 mb-3 text-xs">
            <span className="text-neutral-600 mr-2">Showing</span>
            <button onClick={() => setFilterType("all")} className={`px-2 py-1 rounded border ${filterType === "all" ? "border-neutral-400 text-neutral-200" : "border-neutral-800 text-neutral-500 hover:text-neutral-300"}`}>
              all <span className="font-mono ml-1">{data.total}</span>
            </button>
            {Object.entries(data.counts_by_type).map(([t, c]) => (
              <button key={t} onClick={() => setFilterType(t)} className={`px-2 py-1 rounded border ${filterType === t ? "border-neutral-400 text-neutral-200" : "border-neutral-800 text-neutral-500 hover:text-neutral-300"}`}>
                {TYPE_LABELS[t] ?? t} <span className="font-mono ml-1">{c}</span>
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div className="text-sm text-neutral-600 mt-8 text-center">
              {data.total === 0 ? "No data-quality issues detected. ✨" : "No issues of this type."}
            </div>
          ) : (
            filtered.map(i => <IssueRow key={`${i.issue_type}-${i.bean_id}-${i.duplicate_of_bean_id ?? ""}-${i.stale_match_id ?? ""}`} issue={i} />)
          )}
        </>
      )}
    </div>
  );
}
