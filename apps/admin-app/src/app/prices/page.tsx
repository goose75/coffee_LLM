"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { Badge, StatCard, PageHeader, ErrorBanner, EmptyState, SkeletonRows, DataTable } from "@/components/ui";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PriceChange {
  variant_id: string;
  bean_name: string;
  store_name: string;
  weight_g: number | null;
  grind_type: string;
  old_price_gbp: number;
  new_price_gbp: number;
  change_gbp: number;
  change_pct: number;
  direction: "up" | "down";
  recorded_at: string;
}

interface PriceAnomaly {
  variant_id: string;
  bean_name: string;
  store_name: string;
  weight_g: number | null;
  grind_type: string;
  price_gbp: number;
  price_per_100g_gbp: number | null;
  reason: string;
  severity: "low" | "medium" | "high";
}

interface WeightIssue {
  variant_id: string;
  bean_name: string;
  store_name: string;
  variant_title: string;
  weight_g: number | null;
  price_gbp: number;
  issue: "missing_weight" | "suspicious_weight" | "no_per_100g";
}

// ── Components ────────────────────────────────────────────────────────────────

function ChangeArrow({ direction, pct }: { direction: string; pct: number }) {
  const isUp = direction === "up";
  return (
    <span className={`flex items-center gap-1 text-xs font-mono ${isUp ? "text-red-400" : "text-emerald-400"}`}>
      {isUp ? "↑" : "↓"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls = severity === "high"
    ? "bg-red-900/40 text-red-400 border-red-800"
    : severity === "medium"
    ? "bg-amber-900/40 text-amber-400 border-amber-800"
    : "bg-neutral-800 text-neutral-400 border-neutral-700";
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${cls}`}>
      {severity}
    </span>
  );
}

function IssueBadge({ issue }: { issue: string }) {
  const labels: Record<string, string> = {
    missing_weight: "No weight",
    suspicious_weight: "Bad weight",
    no_per_100g: "No /100g",
  };
  return (
    <span className="px-2 py-0.5 rounded text-[10px] bg-amber-900/30 text-amber-400 border border-amber-800">
      {labels[issue] ?? issue}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PricesAdminPage() {
  const [tab, setTab] = useState<"changes" | "anomalies" | "coverage">("changes");
  const [changes, setChanges] = useState<PriceChange[]>([]);
  const [anomalies, setAnomalies] = useState<PriceAnomaly[]>([]);
  const [coverage, setCoverage] = useState<WeightIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [c, a, cov] = await Promise.all([
        apiFetch<PriceChange[]>("/prices/recent-changes?days=14&min_change_pct=1"),
        apiFetch<PriceAnomaly[]>("/prices/anomalies"),
        apiFetch<WeightIssue[]>("/prices/weight-coverage"),
      ]);
      setChanges(c);
      setAnomalies(a);
      setCoverage(cov);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const highAnomalies = anomalies.filter(a => a.severity === "high").length;

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader
        title="Price Intelligence"
        subtitle="Monitor price changes, detect anomalies, and audit weight coverage."
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatCard label="Price changes (14d)" value={loading ? "…" : changes.length} sub="above 1% threshold" />
        <StatCard label="Anomalies" value={loading ? "…" : anomalies.length}
          sub={`${highAnomalies} high severity`}
          color={highAnomalies > 0 ? "text-red-400" : "text-neutral-200"} />
        <StatCard label="Weight issues" value={loading ? "…" : coverage.length} sub="missing or suspicious" />
        <StatCard label="Price rises" value={loading ? "…" : changes.filter(c => c.direction === "up").length}
          sub="of total changes" color="text-red-400" />
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-neutral-800 mb-5">
        {(["changes", "anomalies", "coverage"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors capitalize -mb-px ${
              tab === t ? "text-amber-400 border-amber-500" : "text-neutral-500 border-transparent hover:text-neutral-300"
            }`}>
            {t === "changes" ? "Recent Changes" : t === "anomalies" ? "Anomalies" : "Weight Coverage"}
            <span className="ml-1.5 text-xs text-neutral-600">
              {t === "changes" ? changes.length : t === "anomalies" ? anomalies.length : coverage.length}
            </span>
          </button>
        ))}
      </div>

      {/* Recent Changes */}
      {tab === "changes" && (
        <DataTable headers={["Coffee", "Store", "Weight", "Old", "New", "Change", "When"]}>
          {loading ? <SkeletonRows cols={7} /> :
            changes.length === 0 ? (
              <tr><td colSpan={7}><EmptyState message="No significant price changes in the last 14 days." /></td></tr>
            ) : changes.map(c => (
              <tr key={c.variant_id} className="border-b border-neutral-800/40 hover:bg-neutral-900/20">
                <td className="px-4 py-2.5 text-sm text-neutral-200 max-w-[200px] truncate">{c.bean_name}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-500">{c.store_name}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-500 font-mono">{c.weight_g ? `${c.weight_g}g` : "—"}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-500 font-mono">£{c.old_price_gbp.toFixed(2)}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-200">£{c.new_price_gbp.toFixed(2)}</td>
                <td className="px-4 py-2.5"><ChangeArrow direction={c.direction} pct={c.change_pct} /></td>
                <td className="px-4 py-2.5 text-xs text-neutral-600">
                  {new Date(c.recorded_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                </td>
              </tr>
            ))
          }
        </DataTable>
      )}

      {/* Anomalies */}
      {tab === "anomalies" && (
        <DataTable headers={["Coffee", "Store", "Weight", "Price", "Per 100g", "Severity", "Reason"]}>
          {loading ? <SkeletonRows cols={7} /> :
            anomalies.length === 0 ? (
              <tr><td colSpan={7}><EmptyState message="No price anomalies detected." /></td></tr>
            ) : anomalies.map(a => (
              <tr key={a.variant_id} className="border-b border-neutral-800/40 hover:bg-neutral-900/20">
                <td className="px-4 py-2.5 text-sm text-neutral-200 max-w-[180px] truncate">{a.bean_name}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-500">{a.store_name}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">{a.weight_g ? `${a.weight_g}g` : "—"}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-200">£{a.price_gbp.toFixed(2)}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">{a.price_per_100g_gbp ? `£${a.price_per_100g_gbp.toFixed(2)}` : "—"}</td>
                <td className="px-4 py-2.5"><SeverityBadge severity={a.severity} /></td>
                <td className="px-4 py-2.5 text-xs text-neutral-500 max-w-[200px] truncate" title={a.reason}>{a.reason}</td>
              </tr>
            ))
          }
        </DataTable>
      )}

      {/* Weight Coverage */}
      {tab === "coverage" && (
        <DataTable headers={["Coffee", "Store", "Variant", "Weight", "Price", "Issue"]}>
          {loading ? <SkeletonRows cols={6} /> :
            coverage.length === 0 ? (
              <tr><td colSpan={6}><EmptyState message="All variants have valid weight data." /></td></tr>
            ) : coverage.map(w => (
              <tr key={w.variant_id} className="border-b border-neutral-800/40 hover:bg-neutral-900/20">
                <td className="px-4 py-2.5 text-sm text-neutral-200 max-w-[180px] truncate">{w.bean_name}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-500">{w.store_name}</td>
                <td className="px-4 py-2.5 text-xs text-neutral-400 max-w-[140px] truncate">{w.variant_title}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">{w.weight_g ?? "—"}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-neutral-200">£{w.price_gbp.toFixed(2)}</td>
                <td className="px-4 py-2.5"><IssueBadge issue={w.issue} /></td>
              </tr>
            ))
          }
        </DataTable>
      )}
    </div>
  );
}
