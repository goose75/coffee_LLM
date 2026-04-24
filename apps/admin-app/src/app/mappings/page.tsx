"use client";

import { useEffect, useState, useCallback } from "react";
import { getMappings, getVocabSummary, createMapping, updateMapping, deleteMapping, normaliseValue, type Mapping, type VocabSummary } from "@/lib/api";
import { Badge, DataTable, SkeletonRows, PageHeader, Pagination, EmptyState, ErrorBanner, FilterBar, FilterSearch, Btn } from "@/components/ui";

const TYPE_LABELS: Record<string, string> = { roast_level: "Roast Level", grind: "Grind", process: "Process", country: "Country", region: "Region", varietal: "Varietal" };
const VALID_VALUES: Record<string, string[]> = {
  roast_level: ["light","medium_light","medium","medium_dark","dark","unknown"],
  grind: ["whole_bean","espresso","filter","cafetiere","moka","aeropress","pour_over","omni","unknown"],
  process: ["washed","natural","honey","anaerobic","wet_hulled","carbonic_maceration","experimental","unknown"],
};

function MappingRow({ m, validValues, onUpdated, onDeleted }: { m: Mapping; validValues: string[]; onUpdated: () => void; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(m.normalised_value);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (val === m.normalised_value) { setEditing(false); return; }
    setSaving(true);
    try { await updateMapping(m.id, { normalised_value: val, source: "manual" }); onUpdated(); setEditing(false); }
    finally { setSaving(false); }
  };

  const del = async () => {
    if (!confirm(`Delete "${m.raw_value}" → "${m.normalised_value}"?`)) return;
    await deleteMapping(m.id);
    onDeleted();
  };

  return (
    <tr className="border-b border-neutral-800/40 hover:bg-neutral-900/30 group transition-colors">
      <td className="px-4 py-2.5 font-mono text-sm text-neutral-300">{m.raw_value}</td>
      <td className="px-4 py-2.5 text-neutral-700 text-xs">→</td>
      <td className="px-4 py-2.5">
        {editing ? (
          <div className="flex items-center gap-2">
            {validValues.length > 0 ? (
              <select value={val} onChange={e => setVal(e.target.value)} autoFocus
                className="bg-neutral-900 border border-amber-700 rounded px-2 py-1 text-xs text-neutral-200 focus:outline-none">
                {validValues.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            ) : (
              <input value={val} onChange={e => setVal(e.target.value)} autoFocus
                onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
                className="bg-neutral-900 border border-amber-700 rounded px-2 py-1 text-xs text-neutral-200 focus:outline-none w-32" />
            )}
            <button onClick={save} disabled={saving} className="text-xs text-emerald-400 hover:text-emerald-300">{saving ? "…" : "✓"}</button>
            <button onClick={() => setEditing(false)} className="text-xs text-neutral-600">✕</button>
          </div>
        ) : (
          <button onClick={() => setEditing(true)} className="font-mono text-xs text-amber-400/80 hover:text-amber-300 text-left">{m.normalised_value}</button>
        )}
      </td>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="w-16 h-1 bg-neutral-800 rounded-full overflow-hidden">
            <div className="h-full bg-amber-700/60 rounded-full" style={{ width: `${m.confidence_score * 100}%` }} />
          </div>
          <span className="text-[10px] text-neutral-700">{(m.confidence_score * 100).toFixed(0)}%</span>
        </div>
      </td>
      <td className="px-4 py-2.5"><Badge value={m.source} /></td>
      <td className="px-4 py-2.5 text-right opacity-0 group-hover:opacity-100 transition-opacity">
        <Btn size="xs" variant="danger" onClick={del}>Delete</Btn>
      </td>
    </tr>
  );
}

export default function MappingsPage() {
  const [vocab, setVocab] = useState<VocabSummary[]>([]);
  const [activeType, setActiveType] = useState("roast_level");
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Add form
  const [addRaw, setAddRaw] = useState("");
  const [addNorm, setAddNorm] = useState("");
  const [adding, setAdding] = useState(false);
  // Test normalise
  const [testRaw, setTestRaw] = useState("");
  const [testResult, setTestResult] = useState<{ normalised_value: string; confidence: number; source: string; is_unknown: boolean } | null>(null);

  const activeVocab = vocab.find(v => v.mapping_type === activeType);
  const validValues = VALID_VALUES[activeType] ?? [];

  const loadVocab = useCallback(async () => {
    try { const d = await getVocabSummary(); setVocab(d); } catch {}
  }, []);

  const loadMappings = useCallback(async () => {
    setLoading(true);
    try {
      const d = await getMappings({ mapping_type: activeType, q: q || undefined, page, page_size: 50 });
      setMappings(d.data); setTotal(d.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [activeType, q, page]);

  useEffect(() => { loadVocab(); }, [loadVocab]);
  useEffect(() => { setPage(1); }, [activeType, q]);
  useEffect(() => { loadMappings(); }, [loadMappings]);

  const handleAdd = async () => {
    if (!addRaw.trim() || !addNorm.trim()) return;
    setAdding(true);
    try {
      await createMapping({ mapping_type: activeType, raw_value: addRaw.trim(), normalised_value: addNorm.trim(), confidence_score: 1.0, source: "manual" });
      setAddRaw(""); setAddNorm("");
      loadMappings(); loadVocab();
    } catch (e: any) { setError(e.message); }
    finally { setAdding(false); }
  };

  const handleTest = async () => {
    if (!testRaw.trim()) return;
    try { const r = await normaliseValue(testRaw.trim(), activeType); setTestResult(r); } catch (e: any) { setError(e.message); }
  };

  return (
    <div className="p-6 max-w-5xl">
      <PageHeader title="Mapping Dictionary" subtitle="Raw source text → controlled vocabulary. Click any normalised value to edit." />
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* Type tabs */}
      <div className="flex gap-0 border-b border-neutral-800 mb-5">
        {Object.entries(TYPE_LABELS).map(([type, label]) => {
          const count = vocab.find(v => v.mapping_type === type)?.count ?? 0;
          return (
            <button key={type} onClick={() => { setActiveType(type); setQ(""); }}
              className={`px-4 py-2.5 text-[13px] border-b-2 transition-colors -mb-px ${activeType === type ? "text-amber-400 border-amber-600" : "text-neutral-600 border-transparent hover:text-neutral-300"}`}>
              {label} <span className="text-neutral-700 ml-1">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Valid values chips */}
      {validValues.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          <span className="text-[10px] text-neutral-700 self-center">Valid:</span>
          {validValues.map(v => (
            <span key={v} className="text-[10px] font-mono bg-neutral-900 border border-neutral-800 rounded px-2 py-0.5 text-neutral-500">{v}</span>
          ))}
        </div>
      )}

      {/* Test normaliser */}
      <div className="border border-neutral-800 rounded-lg p-3 mb-3 bg-neutral-900/20">
        <div className="text-[10px] uppercase tracking-wider text-neutral-700 mb-2">Test normaliser</div>
        <div className="flex items-center gap-2">
          <input value={testRaw} onChange={e => { setTestRaw(e.target.value); setTestResult(null); }}
            onKeyDown={e => e.key === "Enter" && handleTest()}
            placeholder={`Raw ${TYPE_LABELS[activeType] ?? ""} text…`}
            className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-700 focus:outline-none focus:border-amber-600" />
          <Btn onClick={handleTest} disabled={!testRaw.trim()}>Test</Btn>
        </div>
        {testResult && (
          <div className="mt-2 flex items-center gap-3 text-sm">
            <span className="text-neutral-500 font-mono">{testRaw}</span>
            <span className="text-neutral-700">→</span>
            <span className={`font-mono font-medium ${testResult.is_unknown ? "text-neutral-600" : "text-amber-400"}`}>
              {testResult.normalised_value || "(no match)"}
            </span>
            <span className="text-[10px] text-neutral-700">{(testResult.confidence * 100).toFixed(0)}% · {testResult.source}</span>
            {testResult.is_unknown && <span className="text-[10px] text-amber-700 bg-amber-950/30 px-2 py-0.5 rounded border border-amber-900/40">No mapping — consider adding one</span>}
          </div>
        )}
      </div>

      {/* Add row */}
      <div className="border border-neutral-800 rounded-lg p-3 mb-4 bg-neutral-900/20">
        <div className="text-[10px] uppercase tracking-wider text-neutral-700 mb-2">Add mapping</div>
        <div className="flex items-center gap-2">
          <input value={addRaw} onChange={e => setAddRaw(e.target.value)} placeholder='Raw value, e.g. "Full City+"'
            className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-700 focus:outline-none focus:border-amber-600" />
          <span className="text-neutral-700">→</span>
          {validValues.length > 0 ? (
            <select value={addNorm} onChange={e => setAddNorm(e.target.value)}
              className="w-40 bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 focus:outline-none focus:border-amber-600">
              <option value="">Choose…</option>
              {validValues.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          ) : (
            <input value={addNorm} onChange={e => setAddNorm(e.target.value)} placeholder="Normalised value"
              className="w-40 bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-700 focus:outline-none focus:border-amber-600" />
          )}
          <Btn variant="primary" onClick={handleAdd} disabled={adding || !addRaw.trim() || !addNorm.trim()}>
            {adding ? "Adding…" : "Add"}
          </Btn>
        </div>
      </div>

      <FilterBar>
        <FilterSearch value={q} onChange={setQ} placeholder="Search raw or normalised…" />
        <span className="text-xs text-neutral-600">{total} mappings</span>
      </FilterBar>

      <DataTable headers={["Raw value", "", "Normalised value", "Confidence", "Source", ""]}>
        {loading ? <SkeletonRows cols={6} /> : mappings.length === 0 ? (
          <tr><td colSpan={6}><EmptyState message="No mappings yet. Add one above." /></td></tr>
        ) : mappings.map(m => (
          <MappingRow key={m.id} m={m} validValues={validValues} onUpdated={loadMappings} onDeleted={() => { loadMappings(); loadVocab(); }} />
        ))}
      </DataTable>
      <Pagination page={page} total={total} pageSize={50} onPage={setPage} />
    </div>
  );
}
