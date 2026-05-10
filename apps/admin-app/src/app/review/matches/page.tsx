"use client";

import { useEffect, useState, useCallback } from "react";
import { getMatches, acceptMatch, rejectMatch, bulkAcceptMatches, bulkRejectMatches, type CanonicalMatch, type MatchFilters } from "@/lib/api";
import { Badge, ConfidenceBar, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSelect, Btn } from "@/components/ui";

function SignalBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  const color = value >= 0.8 ? "bg-emerald-600" : value >= 0.5 ? "bg-amber-600" : "bg-red-800";
  return (
    <div className="mb-1.5">
      <div className="flex justify-between mb-0.5">
        <span className="text-[10px] text-neutral-600">{label}</span>
        <span className="text-[10px] font-mono text-neutral-500">{(value * 100).toFixed(0)}% ×{weight}</span>
      </div>
      <div className="h-1 bg-neutral-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}

function FieldComp({ label, a, b, matched }: { label: string; a: string; b: string; matched: boolean | null }) {
  const icon = matched === null ? "–" : matched ? "✓" : "✗";
  const cls = matched === null ? "text-neutral-700" : matched ? "text-emerald-500" : "text-red-500";
  return (
    <div className="grid grid-cols-[80px_1fr_16px_1fr] gap-1 py-1 border-b border-neutral-800/40 text-xs items-start">
      <span className="text-neutral-700">{label}</span>
      <span className="text-neutral-400 truncate" title={a}>{a || <span className="text-neutral-700">—</span>}</span>
      <span className={`text-center ${cls}`}>{icon}</span>
      <span className="text-neutral-300 truncate" title={b}>{b || <span className="text-neutral-700">—</span>}</span>
    </div>
  );
}

function MatchCard({ match, onAccept, onReject, actioning, selected, onToggleSelect }: { match: CanonicalMatch; onAccept: (id: string) => Promise<void>; onReject: (id: string) => Promise<void>; actioning: string | null; selected: boolean; onToggleSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const listing = match.bean_listing;
  const canonical = match.proposed_canonical_bean;
  const sig = match.match_signals;
  const isMe = actioning === match.id;
  const conf = match.confidence_score;
  const isPending = match.review_status === "pending";

  const borderColor = conf >= 0.92 ? "border-emerald-800/50" : conf >= 0.75 ? "border-amber-800/50" : "border-neutral-800";
  const bg = selected ? "bg-blue-950/30" : conf >= 0.92 ? "bg-emerald-950/20" : conf >= 0.75 ? "bg-amber-950/20" : "";

  return (
    <div className={`border rounded-lg overflow-hidden mb-2 ${borderColor} ${bg}`}>
      <div className="flex items-center gap-3 px-4 py-3">
        {isPending && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(match.id)}
            onClick={(e) => e.stopPropagation()}
            className="accent-amber-500 cursor-pointer"
            title="Select for bulk action"
          />
        )}
        <div className="flex-1 flex items-center gap-3 cursor-pointer" onClick={() => setOpen(!open)}>
        <div className={`text-lg font-mono font-bold w-12 shrink-0 ${conf >= 0.92 ? "text-emerald-400" : conf >= 0.75 ? "text-amber-400" : "text-red-400"}`}>
          {(conf * 100).toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-neutral-200 truncate">{listing?.raw_title ?? "—"}</div>
          <div className="text-xs text-neutral-600 mt-0.5">{match.match_method} · {match.accepted_by_system_flag ? "system" : "pending"}</div>
        </div>
        <div className="text-neutral-700 text-sm shrink-0">→</div>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-neutral-300 truncate">{canonical?.canonical_name ?? "—"}</div>
          <div className="text-xs text-neutral-600 mt-0.5">{[canonical?.origin_country, canonical?.process].filter(Boolean).join(" · ")}</div>
        </div>
        <Badge value={match.review_status} />
        <span className="text-neutral-700 text-xs">{open ? "▲" : "▼"}</span>
        </div>
      </div>

      {open && (
        <div className="border-t border-neutral-800/60">
          <div className="grid grid-cols-[1fr_180px] divide-x divide-neutral-800/60">
            <div className="p-4">
              <div className="text-[10px] uppercase tracking-wider text-neutral-700 mb-2">Field comparison</div>
              <div className="grid grid-cols-[80px_1fr_16px_1fr] gap-1 mb-1">
                <span className="text-[10px] text-neutral-700">Field</span>
                <span className="text-[10px] text-neutral-700">Listing</span>
                <span></span>
                <span className="text-[10px] text-neutral-700">Canonical</span>
              </div>
              <FieldComp label="Title" a={listing?.raw_title ?? ""} b={canonical?.canonical_name ?? ""} matched={null} />
              <FieldComp label="Country" a={listing?.origin_label_raw ?? ""} b={canonical?.origin_country ?? ""} matched={sig?.field_matches?.["origin_country"] ?? null} />
              <FieldComp label="Process" a={listing?.process_label_raw ?? ""} b={canonical?.process ?? ""} matched={sig?.field_matches?.["process"] ?? null} />
              <FieldComp label="Varietal" a={listing?.varietal_label_raw ?? ""} b={(canonical?.varietal ?? []).join(", ")} matched={sig?.field_matches?.["varietal"] ?? null} />
              <FieldComp label="Farm" a="" b={canonical?.farm_or_estate ?? ""} matched={sig?.field_matches?.["farm_or_estate"] ?? null} />
              {canonical?.harvest_year && <FieldComp label="Harvest" a="" b={String(canonical.harvest_year)} matched={null} />}
              {canonical && (canonical.flavour_notes?.length ?? 0) > 0 && <FieldComp label="Notes" a="" b={(canonical.flavour_notes ?? []).slice(0,4).join(", ")} matched={null} />}
            </div>
            <div className="p-4">
              <div className="text-[10px] uppercase tracking-wider text-neutral-700 mb-2">Signals</div>
              {sig ? (
                <>
                  <SignalBar label="Exact fields" value={sig.exact_score} weight={0.45} />
                  <SignalBar label="Fuzzy title" value={sig.fuzzy_score} weight={0.30} />
                  <SignalBar label="Embedding" value={sig.embedding_score} weight={0.20} />
                  <SignalBar label="Harvest" value={sig.harvest_score} weight={0.05} />
                  <div className="mt-2 pt-2 border-t border-neutral-800">
                    <div className="flex justify-between">
                      <span className="text-[10px] text-neutral-700">Combined</span>
                      <ConfidenceBar value={sig.combined} />
                    </div>
                  </div>
                </>
              ) : <div className="text-xs text-neutral-700">No signal data</div>}
            </div>
          </div>
          {match.review_status === "pending" && (
            <div className="border-t border-neutral-800/60 px-4 py-3 flex items-center gap-2">
              <Btn variant="primary" onClick={() => onAccept(match.id)} disabled={isMe}>
                {isMe ? "…" : "✓ Accept"}
              </Btn>
              <Btn variant="danger" onClick={() => onReject(match.id)} disabled={isMe}>✕ Reject</Btn>
              <a href={`/beans/${match.proposed_canonical_bean_id}`} className="ml-auto text-xs text-neutral-600 hover:text-neutral-300">View canonical →</a>
            </div>
          )}
          {match.review_status !== "pending" && match.reviewed_at && (
            <div className="border-t border-neutral-800/60 px-4 py-2 text-xs text-neutral-700">
              {match.review_status} by {match.reviewed_by_user_id ?? "system"} · {new Date(match.reviewed_at).toLocaleString("en-GB")}
              {match.review_notes && <span className="ml-2 text-neutral-600">— {match.review_notes}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function MatchReviewPage() {
  const [matches, setMatches] = useState<CanonicalMatch[]>([]);
  const [total, setTotal] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<MatchFilters>({ status: "pending" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioning, setActioning] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMatches({ ...filters, page, page_size: 20 });
      setMatches(data.data);
      setTotal(data.total);
      setPendingCount(data.pending_count);
      setSelected(new Set());  // clear selection on reload
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [filters, page]);

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAllVisible = () => {
    setSelected(new Set(matches.filter(m => m.review_status === "pending").map(m => m.id)));
  };
  const clearSelection = () => setSelected(new Set());

  const runBulk = async (action: "accept" | "reject") => {
    if (selected.size === 0) return;
    if (!confirm(`${action === "accept" ? "Accept" : "Reject"} ${selected.size} matches?`)) return;
    setBulkRunning(true);
    try {
      const fn = action === "accept" ? bulkAcceptMatches : bulkRejectMatches;
      const r = await fn({ match_ids: Array.from(selected) });
      setBanner(`${r.outcome}: ${r.affected} matches${r.skipped.length ? ` (${r.skipped.length} skipped)` : ""}`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setBulkRunning(false); }
  };

  const runPreset = async (preset: "near_perfect" | "low_confidence") => {
    const filter = preset === "near_perfect"
      ? { min_confidence: 0.85, notes: "bulk-accept preset: near-perfect", action: "accept" as const, label: "Accept all ≥85% confidence" }
      : { max_confidence: 0.5, notes: "bulk-reject preset: low confidence", action: "reject" as const, label: "Reject all ≤50% confidence" };
    if (!confirm(`${filter.label} pending matches?`)) return;
    setBulkRunning(true);
    try {
      const fn = filter.action === "accept" ? bulkAcceptMatches : bulkRejectMatches;
      const r = await fn({
        min_confidence: "min_confidence" in filter ? filter.min_confidence : undefined,
        max_confidence: "max_confidence" in filter ? filter.max_confidence : undefined,
        notes: filter.notes,
      });
      setBanner(`${r.outcome}: ${r.affected} matches${r.skipped.length ? ` (${r.skipped.length} skipped)` : ""}`);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setBulkRunning(false); }
  };

  useEffect(() => { setPage(1); }, [filters]);
  useEffect(() => { load(); }, [load]);

  const handleAccept = async (id: string) => {
    setActioning(id);
    try { await acceptMatch(id); await load(); } catch (e: any) { setError(e.message); } finally { setActioning(null); }
  };
  const handleReject = async (id: string) => {
    setActioning(id);
    try { await rejectMatch(id); await load(); } catch (e: any) { setError(e.message); } finally { setActioning(null); }
  };

  return (
    <div className="p-6 max-w-5xl">
      <PageHeader
        title={<span className="flex items-center gap-2">Match Review {pendingCount > 0 && <span className="text-xs bg-amber-900/40 text-amber-400 border border-amber-800 px-2 py-0.5 rounded-full font-normal">{pendingCount} pending</span>}</span>}
        subtitle="Proposed links between listings and canonical beans. Click a card to expand."
        actions={
          <div className="flex gap-2">
            <a href="/review/analytics" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Analytics</a>
            <a href="/review/issues" className="text-xs px-3 py-1.5 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-900 hover:text-neutral-100 transition-colors">Issues</a>
            <Btn onClick={load}>↻ Refresh</Btn>
          </div>
        }
      />
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}
      {banner && (
        <div className="mb-4 px-4 py-2.5 bg-emerald-900/20 border border-emerald-800/50 rounded text-sm text-emerald-400 flex items-center justify-between">
          {banner}
          <button onClick={() => setBanner(null)} className="text-emerald-700 hover:text-emerald-400">×</button>
        </div>
      )}

      {/* Bulk action bar — only when at least one row is selected, or always show preset shortcuts */}
      <div className="flex items-center gap-2 mb-3 text-xs">
        {selected.size > 0 ? (
          <>
            <span className="text-neutral-300 font-mono">{selected.size} selected</span>
            <Btn size="xs" variant="primary" onClick={() => runBulk("accept")} disabled={bulkRunning}>
              ✓ Accept selected
            </Btn>
            <Btn size="xs" variant="danger" onClick={() => runBulk("reject")} disabled={bulkRunning}>
              ✕ Reject selected
            </Btn>
            <button onClick={clearSelection} className="text-neutral-600 hover:text-neutral-300">Clear</button>
          </>
        ) : (
          <>
            <button onClick={selectAllVisible} className="text-neutral-600 hover:text-neutral-300 underline">Select all on this page</button>
            <span className="text-neutral-700">·</span>
            <button onClick={() => runPreset("near_perfect")} disabled={bulkRunning} className="text-emerald-600 hover:text-emerald-400 underline">
              Bulk: accept all ≥85%
            </button>
            <button onClick={() => runPreset("low_confidence")} disabled={bulkRunning} className="text-red-500 hover:text-red-400 underline">
              Bulk: reject all ≤50%
            </button>
          </>
        )}
      </div>

      <FilterBar>
        <FilterSelect value={filters.status ?? "pending"} onChange={v => setFilters(f => ({ ...f, status: v || "pending" }))} placeholder="Status"
          options={["pending","accepted","rejected","all"].map(v => ({ value: v, label: v }))} />
        <FilterSelect value={filters.match_method ?? ""} onChange={v => setFilters(f => ({ ...f, match_method: v || undefined }))} placeholder="All methods"
          options={["exact","fuzzy","embedding","combined"].map(v => ({ value: v, label: v }))} />
        <div className="flex items-center gap-2 text-xs text-neutral-600 ml-auto">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-600 inline-block" />≥92% auto</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-600 inline-block" />75–91% review</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-800 inline-block" />&lt;75% new</span>
        </div>
      </FilterBar>

      {loading ? (
        Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border border-neutral-800 rounded-lg h-14 mb-2 animate-pulse bg-neutral-900/30" />
        ))
      ) : matches.length === 0 ? (
        <EmptyState
                    message={filters.status === "pending"
                      ? "No pending matches."
                      : "No matches found for these filters."}
                    action={filters.status === "pending" ? (
                      <span style={{ fontSize: "0.75rem", color: "var(--text-faint)" }}>
                        Run the entity resolution pipeline to generate match proposals.
                        Matches appear here after ingestion completes.
                      </span>
                    ) : undefined}
                  />
      ) : (
        matches.map(m => <MatchCard key={m.id} match={m} onAccept={handleAccept} onReject={handleReject} actioning={actioning} selected={selected.has(m.id)} onToggleSelect={toggleSelect} />)
      )}
      <Pagination page={page} total={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
