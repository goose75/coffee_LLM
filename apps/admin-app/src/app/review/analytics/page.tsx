"use client";

import { useEffect, useState } from "react";
import { getReviewAnalytics, type ReviewAnalytics, type HistogramBin, type FieldCoverage, type TopBlocker } from "@/lib/api";
import { PageHeader, ErrorBanner, Btn } from "@/components/ui";

function Histogram({ data, bandColors }: { data: HistogramBin[]; bandColors?: (b: HistogramBin) => string }) {
  const max = Math.max(...data.map(b => b.count), 1);
  return (
    <div className="flex items-end gap-1 h-32 px-1">
      {data.map(b => {
        const h = Math.max(2, (b.count / max) * 100);
        const colour = bandColors ? bandColors(b) : "bg-neutral-600";
        return (
          <div key={b.bin_label} className="flex-1 flex flex-col items-center gap-1">
            <div className="w-full flex items-end h-full">
              <div className={`w-full ${colour} rounded-t`} style={{ height: `${h}%` }} title={`${b.bin_label}: ${b.count}`} />
            </div>
            <div className="text-[9px] text-neutral-600 font-mono">{b.bin_label.replace("0.","" )}</div>
            <div className="text-[10px] text-neutral-400 font-mono">{b.count}</div>
          </div>
        );
      })}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border border-neutral-800 rounded-lg p-4">
      <div className="text-[10px] uppercase tracking-wider text-neutral-600 mb-1">{label}</div>
      <div className="text-2xl font-mono text-neutral-100">{value}</div>
      {sub && <div className="text-[10px] text-neutral-600 mt-1">{sub}</div>}
    </div>
  );
}

function CardSection({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="border border-neutral-800 rounded-lg p-4 mb-4">
      <div className="mb-3">
        <div className="text-sm text-neutral-200">{title}</div>
        {subtitle && <div className="text-[11px] text-neutral-600 mt-0.5">{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}

function FieldCoverageBar({ fc }: { fc: FieldCoverage }) {
  const total = fc.matched + fc.mismatched + fc.skipped || 1;
  const m = (fc.matched / total) * 100;
  const x = (fc.mismatched / total) * 100;
  const s = (fc.skipped / total) * 100;
  return (
    <div className="mb-3">
      <div className="flex justify-between mb-1">
        <span className="text-xs text-neutral-300">{fc.field}</span>
        <span className="text-[10px] font-mono text-neutral-600">
          ✓ {fc.matched}  ✗ {fc.mismatched}  – {fc.skipped}
        </span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-neutral-900">
        <div className="bg-emerald-700" style={{ width: `${m}%` }} title={`matched: ${fc.matched}`} />
        <div className="bg-red-800" style={{ width: `${x}%` }} title={`mismatched: ${fc.mismatched}`} />
        <div className="bg-neutral-800" style={{ width: `${s}%` }} title={`skipped (one side blank): ${fc.skipped}`} />
      </div>
    </div>
  );
}

export default function ReviewAnalyticsPage() {
  const [data, setData] = useState<ReviewAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try { setData(await getReviewAnalytics()); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  // Confidence band colours: <0.75 = red, 0.75-0.92 = amber, ≥0.92 = green
  const confidenceColors = (b: HistogramBin) => {
    if (b.bin_min >= 0.92) return "bg-emerald-700";
    if (b.bin_min >= 0.75) return "bg-amber-700";
    return "bg-red-800";
  };

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader
        title="Match Review · Analytics"
        subtitle="Where the queue is clustered, which signals are pulling weight, and which fields aren't being compared."
        actions={
          <div className="flex gap-2">
            <a href="/review/matches" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Queue</a>
            <a href="/review/issues" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Issues</a>
            <Btn onClick={load}>↻ Refresh</Btn>
          </div>
        }
      />
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {loading || !data ? (
        <div className="text-sm text-neutral-600">Loading analytics…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <Stat label="Pending" value={data.pending_count} sub="awaiting review" />
            <Stat label="Accepted" value={data.accepted_count} />
            <Stat label="Rejected" value={data.rejected_count} />
            <Stat label="Avg completeness" value={`${(data.avg_canonical_completeness * 100).toFixed(0)}%`} sub={`${data.canonical_bean_count} canonical beans`} />
          </div>

          {data.top_blockers.length > 0 && (
            <CardSection title="Top blockers" subtitle="Patterns keeping matches stuck in pending. Click a label to filter the queue.">
              <div className="space-y-2">
                {data.top_blockers.map(b => (
                  <a key={b.label} href="/review/matches" className="block border border-neutral-800 rounded p-2.5 hover:bg-neutral-900/40 transition-colors">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono text-amber-400 min-w-[2.5rem] text-right">{b.count}</span>
                      <span className="text-xs uppercase tracking-wider text-neutral-300">{b.label}</span>
                    </div>
                    <div className="text-[11px] text-neutral-500 ml-10">{b.description}</div>
                  </a>
                ))}
              </div>
            </CardSection>
          )}

          <CardSection title="Pending confidence distribution" subtitle="Where the queue clusters. Green = auto-accept range, amber = review, red = below review.">
            <Histogram data={data.pending_confidence_histogram} bandColors={confidenceColors} />
          </CardSection>

          <div className="grid grid-cols-3 gap-4 mb-4">
            <CardSection title="Exact-field score" subtitle="Structured field agreement.">
              <Histogram data={data.exact_score_histogram} />
            </CardSection>
            <CardSection title="Fuzzy-title score" subtitle="rapidfuzz token-set similarity.">
              <Histogram data={data.fuzzy_score_histogram} />
            </CardSection>
            <CardSection title="Embedding score" subtitle="Cosine on text-embedding-3-small. Stuck at 0 means no embedding generated.">
              <Histogram data={data.embedding_score_histogram} />
            </CardSection>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <CardSection title="Field-match coverage (pending)" subtitle="✓ agreed · ✗ disagreed · – skipped (one side blank)">
              {data.field_coverage.map(fc => <FieldCoverageBar key={fc.field} fc={fc} />)}
            </CardSection>

            <CardSection title="Match method breakdown (pending)" subtitle="Which scorer chose each match.">
              {Object.entries(data.method_breakdown).length === 0 ? (
                <div className="text-xs text-neutral-600">No pending matches.</div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(data.method_breakdown)
                    .sort(([, a], [, b]) => (b as number) - (a as number))
                    .map(([m, c]) => {
                      const total = Object.values(data.method_breakdown).reduce((acc, v) => acc + (v as number), 0) || 1;
                      const pct = ((c as number) / total) * 100;
                      return (
                        <div key={m}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-neutral-300">{m}</span>
                            <span className="font-mono text-neutral-500">{c} · {pct.toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 bg-neutral-900 rounded-full overflow-hidden">
                            <div className="h-full bg-neutral-500" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </CardSection>
          </div>

          <CardSection title="Canonical bean catalogue completeness" subtitle="Distribution of data_completeness_score across all canonical beans. Right-leaning is good.">
            <Histogram data={data.catalogue_completeness_histogram} />
          </CardSection>
        </>
      )}
    </div>
  );
}
