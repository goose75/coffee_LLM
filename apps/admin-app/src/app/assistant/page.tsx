"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { StatCard, Badge, PageHeader, ErrorBanner, EmptyState, SkeletonRows, DataTable, ConfidenceBar } from "@/components/ui";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AssistantLog {
  id: string;
  session_id: string;
  user_message: string;
  intent: string | null;
  retrieval_calls: { tool: string; params: Record<string, unknown>; results: number }[];
  retrieved_context: unknown[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  assistant_response: string | null;
  hallucination_risk: number | null;
  answered_without_grounding: boolean;
  error: string | null;
  duration_ms: number | null;
  flagged: boolean;
  flag_reason: string | null;
  prompt_version: string;
  created_at: string;
}

interface AssistantStats {
  days: number;
  total_interactions: number;
  high_risk_count: number;
  ungrounded_count: number;
  flagged_count: number;
  avg_hallucination_risk: number;
  avg_duration_ms: number;
  intent_distribution: { intent: string; count: number }[];
}

interface PaginatedLogs {
  data: AssistantLog[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── Risk indicator ─────────────────────────────────────────────────────────────

function RiskBadge({ risk }: { risk: number | null }) {
  if (risk == null) return <span className="text-neutral-700 text-xs">—</span>;
  const color = risk >= 0.6 ? "text-red-400" : risk >= 0.3 ? "text-amber-400" : "text-emerald-400";
  const label = risk >= 0.6 ? "High" : risk >= 0.3 ? "Med" : "Low";
  return <span className={`text-xs font-mono ${color}`}>{label} {(risk * 100).toFixed(0)}%</span>;
}

// ── Log detail drawer ──────────────────────────────────────────────────────────

function LogDrawer({ log, onClose, onFlag }: {
  log: AssistantLog;
  onClose: () => void;
  onFlag: (id: string, flagged: boolean, reason: string) => Promise<void>;
}) {
  const [flagging, setFlagging] = useState(false);
  const [reason, setReason] = useState(log.flag_reason ?? "");

  const handleFlag = async () => {
    setFlagging(true);
    await onFlag(log.id, !log.flagged, reason);
    setFlagging(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/60" onClick={onClose} />
      <div className="w-[640px] bg-neutral-900 border-l border-neutral-800 overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-800 flex items-center justify-between sticky top-0 bg-neutral-900 z-10">
          <div>
            <div className="text-sm font-medium text-neutral-100">Interaction Detail</div>
            <div className="text-[10px] text-neutral-600 font-mono mt-0.5">{log.id}</div>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200 text-lg leading-none">✕</button>
        </div>

        <div className="p-5 space-y-5 flex-1">
          {/* Meta strip */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-neutral-800/50 rounded p-3">
              <div className="text-[10px] text-neutral-600 uppercase tracking-wide mb-1">Intent</div>
              <div className="text-xs text-neutral-200">{log.intent ?? "—"}</div>
            </div>
            <div className="bg-neutral-800/50 rounded p-3">
              <div className="text-[10px] text-neutral-600 uppercase tracking-wide mb-1">Risk</div>
              <RiskBadge risk={log.hallucination_risk} />
            </div>
            <div className="bg-neutral-800/50 rounded p-3">
              <div className="text-[10px] text-neutral-600 uppercase tracking-wide mb-1">Duration</div>
              <div className="text-xs font-mono text-neutral-300">{log.duration_ms ? `${log.duration_ms}ms` : "—"}</div>
            </div>
          </div>

          {/* Flags */}
          <div className="flex gap-2 flex-wrap">
            {log.answered_without_grounding && (
              <span className="text-[10px] px-2 py-0.5 bg-amber-900/30 text-amber-400 border border-amber-800 rounded">No grounding</span>
            )}
            {log.error && (
              <span className="text-[10px] px-2 py-0.5 bg-red-900/30 text-red-400 border border-red-800 rounded">Error</span>
            )}
            {log.flagged && (
              <span className="text-[10px] px-2 py-0.5 bg-purple-900/30 text-purple-400 border border-purple-800 rounded">Flagged</span>
            )}
          </div>

          {/* User message */}
          <div>
            <div className="text-[10px] text-neutral-500 uppercase tracking-widest mb-1.5">User message</div>
            <div className="bg-neutral-800 rounded p-3 text-sm text-neutral-200">{log.user_message}</div>
          </div>

          {/* Retrieval calls */}
          {log.retrieval_calls.length > 0 && (
            <div>
              <div className="text-[10px] text-neutral-500 uppercase tracking-widest mb-1.5">
                Retrieval ({log.retrieval_calls.length} call{log.retrieval_calls.length !== 1 ? "s" : ""})
              </div>
              <div className="space-y-1.5">
                {log.retrieval_calls.map((call, i) => (
                  <div key={i} className="bg-neutral-800 rounded p-2.5">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] text-amber-400 font-mono">{call.tool}</span>
                      <span className="text-[10px] text-neutral-500">{call.results} record{call.results !== 1 ? "s" : ""} returned</span>
                    </div>
                    <pre className="text-[10px] text-neutral-500 font-mono overflow-auto">
                      {JSON.stringify(call.params, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Context count */}
          <div className="text-[10px] text-neutral-600">
            {log.retrieved_context.length} records injected into context ·{" "}
            {log.prompt_tokens ? `${log.prompt_tokens} prompt tokens` : "tokens unknown"} ·{" "}
            {log.completion_tokens ? `${log.completion_tokens} completion tokens` : ""}
          </div>

          {/* Assistant response */}
          {log.assistant_response && (
            <div>
              <div className="text-[10px] text-neutral-500 uppercase tracking-widest mb-1.5">Assistant response</div>
              <div className="bg-neutral-800 rounded p-3 text-sm text-neutral-300 whitespace-pre-wrap leading-relaxed">
                {log.assistant_response}
              </div>
            </div>
          )}

          {/* Error */}
          {log.error && (
            <div>
              <div className="text-[10px] text-red-500 uppercase tracking-widest mb-1.5">Error</div>
              <div className="bg-red-950/30 border border-red-900 rounded p-3 text-xs text-red-400 font-mono">
                {log.error}
              </div>
            </div>
          )}

          {/* Flag controls */}
          <div className="border-t border-neutral-800 pt-4">
            <div className="text-[10px] text-neutral-500 uppercase tracking-widest mb-2">Flag this interaction</div>
            <textarea
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="Reason (optional)…"
              rows={2}
              className="w-full bg-neutral-800 border border-neutral-700 rounded p-2 text-xs text-neutral-300 resize-none mb-2 focus:outline-none focus:border-neutral-600"
            />
            <button
              onClick={handleFlag}
              disabled={flagging}
              className={`px-3 py-1.5 text-xs rounded border transition-colors disabled:opacity-40 ${
                log.flagged
                  ? "bg-neutral-800 text-neutral-400 border-neutral-700 hover:border-neutral-600"
                  : "bg-amber-900/30 text-amber-400 border-amber-800 hover:bg-amber-900/50"
              }`}
            >
              {flagging ? "…" : log.flagged ? "Unflag" : "Flag for review"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AssistantAdminPage() {
  const [stats, setStats] = useState<AssistantStats | null>(null);
  const [logs, setLogs] = useState<AssistantLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AssistantLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterIntent, setFilterIntent] = useState("");
  const [filterFlagged, setFilterFlagged] = useState(false);
  const [filterHighRisk, setFilterHighRisk] = useState(false);
  const [filterUngrounded, setFilterUngrounded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "40", days: "30" });
      if (filterIntent) params.set("intent", filterIntent);
      if (filterFlagged) params.set("flagged", "true");
      if (filterHighRisk) params.set("min_risk", "0.4");
      if (filterUngrounded) params.set("answered_without_grounding", "true");

      const [s, l] = await Promise.all([
        apiFetch<AssistantStats>("/assistant/stats?days=30"),
        apiFetch<PaginatedLogs>(`/assistant/logs?${params}`),
      ]);
      setStats(s);
      setLogs(l.data);
      setTotal(l.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, filterIntent, filterFlagged, filterHighRisk, filterUngrounded]);

  useEffect(() => { setPage(1); }, [filterIntent, filterFlagged, filterHighRisk, filterUngrounded]);
  useEffect(() => { load(); }, [load]);

  const handleFlag = async (id: string, flagged: boolean, reason: string) => {
    await apiFetch(`/assistant/logs/${id}/flag`, {
      method: "POST",
      body: JSON.stringify({ flagged, reason: reason || null }),
    });
    setSelected(prev => prev ? { ...prev, flagged, flag_reason: reason } : null);
    await load();
  };

  const fmtTime = (iso: string) =>
    new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

  const INTENT_COLORS: Record<string, string> = {
    search: "text-blue-400", compare: "text-purple-400", recommend: "text-emerald-400",
    brew_advice: "text-amber-400", price: "text-green-400", general: "text-neutral-400",
    off_topic: "text-red-400",
  };

  return (
    <div className="p-6 max-w-7xl">
      <PageHeader title="Assistant Logs" subtitle="Interaction history, grounding quality, and hallucination risk." />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* Stats strip */}
      {stats && (
        <div className="grid grid-cols-6 gap-3 mb-6">
          <StatCard label="Interactions (30d)" value={stats.total_interactions} sub="total turns" />
          <StatCard label="High risk" value={stats.high_risk_count}
            sub="risk ≥ 40%" color={stats.high_risk_count > 0 ? "text-red-400" : "text-neutral-200"} />
          <StatCard label="Ungrounded" value={stats.ungrounded_count}
            sub="no context" color={stats.ungrounded_count > 0 ? "text-amber-400" : "text-neutral-200"} />
          <StatCard label="Flagged" value={stats.flagged_count}
            sub="manual flags" color={stats.flagged_count > 0 ? "text-purple-400" : "text-neutral-200"} />
          <StatCard label="Avg risk" value={`${(stats.avg_hallucination_risk * 100).toFixed(0)}%`} sub="all interactions" />
          <StatCard label="Avg latency" value={`${Math.round(stats.avg_duration_ms)}ms`} sub="end-to-end" />
        </div>
      )}

      <div className="grid grid-cols-[1fr_200px] gap-4 mb-5">
        {/* Intent distribution mini-chart */}
        {stats && stats.intent_distribution.length > 0 && (
          <div className="border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-3">Intent distribution</div>
            <div className="grid grid-cols-4 gap-2">
              {stats.intent_distribution.slice(0, 8).map(({ intent, count }) => {
                const pct = stats.total_interactions > 0
                  ? Math.round((count / stats.total_interactions) * 100)
                  : 0;
                return (
                  <div key={intent} className="flex items-center justify-between text-xs">
                    <span className={INTENT_COLORS[intent] ?? "text-neutral-400"}>{intent}</span>
                    <span className="text-neutral-500 font-mono">{pct}%</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Filter controls */}
        <div className="border border-neutral-800 rounded-lg p-4 flex flex-col gap-2">
          <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-1">Filters</div>
          {[
            { label: "High risk only", state: filterHighRisk, set: setFilterHighRisk },
            { label: "Ungrounded only", state: filterUngrounded, set: setFilterUngrounded },
            { label: "Flagged only", state: filterFlagged, set: setFilterFlagged },
          ].map(({ label, state, set }) => (
            <label key={label} className="flex items-center gap-2 text-xs text-neutral-500 cursor-pointer hover:text-neutral-300">
              <input type="checkbox" checked={state} onChange={e => set(e.target.checked)}
                className="accent-amber-500" />
              {label}
            </label>
          ))}
          <select
            value={filterIntent}
            onChange={e => setFilterIntent(e.target.value)}
            className="mt-1 bg-neutral-900 border border-neutral-800 rounded text-[11px] text-neutral-400 px-2 py-1 focus:outline-none"
          >
            <option value="">All intents</option>
            {["search", "compare", "recommend", "brew_advice", "price", "general", "off_topic"].map(i => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Logs table */}
      <DataTable headers={["Time", "Intent", "Message", "Retrieval", "Context", "Risk", "Flags", ""]}>
        {loading ? <SkeletonRows cols={8} rows={10} /> :
          logs.length === 0 ? (
            <tr><td colSpan={8}><EmptyState message="No interactions found for the selected filters." /></td></tr>
          ) : logs.map(log => (
            <tr key={log.id}
              className="border-b border-neutral-800/40 hover:bg-neutral-900/30 transition-colors cursor-pointer group"
              onClick={() => setSelected(log)}>
              <td className="px-4 py-2.5 text-xs text-neutral-600 whitespace-nowrap">{fmtTime(log.created_at)}</td>
              <td className="px-4 py-2.5">
                <span className={`text-xs ${INTENT_COLORS[log.intent ?? ""] ?? "text-neutral-500"}`}>
                  {log.intent ?? "—"}
                </span>
              </td>
              <td className="px-4 py-2.5 max-w-[220px]">
                <div className="text-xs text-neutral-300 truncate">{log.user_message}</div>
              </td>
              <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">
                {log.retrieval_calls.length > 0
                  ? log.retrieval_calls.map(c => `${c.tool.replace("_", " ")} (${c.results})`).join(", ")
                  : <span className="text-neutral-700">—</span>}
              </td>
              <td className="px-4 py-2.5 text-xs font-mono text-neutral-500">
                {log.retrieved_context.length}
              </td>
              <td className="px-4 py-2.5"><RiskBadge risk={log.hallucination_risk} /></td>
              <td className="px-4 py-2.5">
                <div className="flex gap-1.5">
                  {log.answered_without_grounding && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-amber-900/20 text-amber-500 border border-amber-900 rounded">
                      ungrounded
                    </span>
                  )}
                  {log.error && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-red-900/20 text-red-500 border border-red-900 rounded">
                      error
                    </span>
                  )}
                  {log.flagged && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-purple-900/20 text-purple-400 border border-purple-900 rounded">
                      flagged
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5 opacity-0 group-hover:opacity-100 transition-opacity text-xs text-neutral-600">
                →
              </td>
            </tr>
          ))
        }
      </DataTable>

      {/* Pagination */}
      {total > 40 && (
        <div className="flex justify-between items-center mt-4 text-xs text-neutral-500">
          <span>{total} total</span>
          <div className="flex gap-2">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1 border border-neutral-800 rounded disabled:opacity-30 hover:border-neutral-600 transition-colors">
              ← Prev
            </button>
            <span className="px-3 py-1">Page {page}</span>
            <button disabled={page * 40 >= total} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1 border border-neutral-800 rounded disabled:opacity-30 hover:border-neutral-600 transition-colors">
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Log detail drawer */}
      {selected && (
        <LogDrawer
          log={selected}
          onClose={() => setSelected(null)}
          onFlag={handleFlag}
        />
      )}
    </div>
  );
}
