"use client";

import { useEffect, useState } from "react";
import { Badge, SkeletonRows } from "@/components/ui";

interface ErrorCorrection {
  domain: string;
  store_id: string;
  current_strategy: string;
  suggested_strategy: string;
  confidence: number;
  reason: string;
  error_messages: string[];
  auto_applied: boolean;
}

interface AnalysisResult {
  analyzed: number;
  corrections: ErrorCorrection[];
}

interface CorrectionSummary {
  total_failures_24h: number;
  top_error_patterns: Array<{
    pattern: string;
    count: number;
    affected_stores: string[];
  }>;
  affected_parser_strategies: Record<string, number>;
}

export default function DiagnosticsPage() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [summary, setSummary] = useState<CorrectionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correcting, setCorrecting] = useState(false);
  const [corrected, setCorrected] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const analysisRes = await fetch("/api/v1/admin/error-recovery/analysis");
        const summaryRes = await fetch("/api/v1/admin/error-recovery/summary");

        if (!analysisRes.ok || !summaryRes.ok) {
          setError("Failed to fetch diagnostics data");
          setLoading(false);
          return;
        }

        const analysisData = await analysisRes.json();
        const summaryData = await summaryRes.json();

        setAnalysis(analysisData || { analyzed: 0, corrections: [] });
        setSummary(summaryData || { total_failures_24h: 0, top_error_patterns: [], affected_parser_strategies: {} });
      } catch (err) {
        setError(`Error loading diagnostics: ${err instanceof Error ? err.message : "Unknown error"}`);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleAutoCorrect = async () => {
    setCorrecting(true);
    try {
      const result = await fetch("/api/v1/admin/error-recovery/auto-correct?min_confidence=0.85", {
        method: "POST",
      });

      if (!result.ok) {
        setError("Failed to apply corrections");
        return;
      }

      const data = await result.json();
      setCorrected(data.corrected || 0);

      // Refresh analysis
      setAnalysis(null);
      setLoading(true);
      setError(null);

      const analysisRes = await fetch("/api/v1/admin/error-recovery/analysis");
      const summaryRes = await fetch("/api/v1/admin/error-recovery/summary");

      if (analysisRes.ok && summaryRes.ok) {
        const analysisData = await analysisRes.json();
        const summaryData = await summaryRes.json();
        setAnalysis(analysisData || { analyzed: 0, corrections: [] });
        setSummary(summaryData || { total_failures_24h: 0, top_error_patterns: [], affected_parser_strategies: {} });
      }
    } catch (err) {
      setError(`Error applying corrections: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setCorrecting(false);
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-lg font-medium text-neutral-100">Ingestion Diagnostics</h1>
        <p className="text-sm text-neutral-500 mt-0.5">Analyze and fix ingestion failures.</p>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 p-4 border border-red-800/50 bg-red-950/20 rounded-lg">
          <div className="text-sm text-red-400">⚠️ {error}</div>
          <div className="text-xs text-red-500 mt-2">
            Make sure the API server is running and endpoints are accessible.
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-2">
              Failures (24h)
            </div>
            <div className="text-3xl font-semibold text-neutral-100">
              {summary.total_failures_24h}
            </div>
          </div>

          <div className="border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-2">
              Top Error Pattern
            </div>
            {summary.top_error_patterns.length > 0 ? (
              <>
                <div className="text-2xl font-semibold text-red-400">
                  {summary.top_error_patterns[0].pattern}
                </div>
                <div className="text-xs text-neutral-500 mt-1">
                  {summary.top_error_patterns[0].count} occurrences
                </div>
              </>
            ) : (
              <div className="text-green-400">No failures detected</div>
            )}
          </div>

          <div className="border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-2">
              Suggested Fixes
            </div>
            <div className="text-2xl font-semibold text-amber-400">
              {analysis?.corrections.length || 0}
            </div>
            <button
              onClick={handleAutoCorrect}
              disabled={correcting || (analysis?.corrections.length || 0) === 0}
              className="text-xs text-amber-600 hover:text-amber-400 disabled:text-neutral-600 mt-2 underline"
            >
              {correcting ? "Applying..." : corrected > 0 ? `Applied ${corrected}` : "Auto-fix"}
            </button>
          </div>
        </div>
      )}

      {/* Error Patterns */}
      {summary && summary.top_error_patterns.length > 0 && (
        <div className="border border-neutral-800 rounded-lg overflow-hidden mb-6">
          <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-900/40">
            <span className="text-sm font-medium text-neutral-300">Top Error Patterns</span>
          </div>
          <div className="p-4">
            {summary.top_error_patterns.map((pattern, i) => (
              <div key={i} className="mb-4 last:mb-0">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-mono text-red-400">{pattern.pattern}</span>
                  <span className="text-xs text-neutral-500">{pattern.count} errors</span>
                </div>
                <div className="text-xs text-neutral-600 mb-1">
                  Affected: {pattern.affected_stores.slice(0, 3).join(", ")}
                  {pattern.affected_stores.length > 3 && ` +${pattern.affected_stores.length - 3}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggested Corrections */}
      {analysis && (
        <div className="border border-neutral-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-900/40">
            <span className="text-sm font-medium text-neutral-300">
              Suggested Corrections ({analysis.corrections.length})
            </span>
          </div>
          {loading ? (
            <SkeletonRows cols={5} rows={5} />
          ) : analysis.corrections.length === 0 ? (
            <div className="p-4 text-center text-neutral-500">No corrections needed</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/40">
                  {["Domain", "Current", "Suggested", "Confidence", "Reason"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2 text-left text-[11px] font-medium text-neutral-600 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {analysis.corrections.map((correction) => (
                  <tr key={correction.store_id} className="border-b border-neutral-800/40 hover:bg-neutral-900/20">
                    <td className="px-4 py-2 text-xs text-neutral-400">{correction.domain}</td>
                    <td className="px-4 py-2">
                      <Badge value={correction.current_strategy} />
                    </td>
                    <td className="px-4 py-2">
                      <Badge value={correction.suggested_strategy} />
                    </td>
                    <td className="px-4 py-2 text-xs">
                      <span className={correction.confidence >= 0.9 ? "text-emerald-400" : correction.confidence >= 0.85 ? "text-amber-400" : "text-neutral-400"}>
                        {Math.round(correction.confidence * 100)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-neutral-500 max-w-xs truncate">
                      {correction.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
