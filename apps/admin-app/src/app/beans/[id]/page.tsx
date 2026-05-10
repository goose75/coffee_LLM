"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCanonicalBean, getCanonicalBeans, updateCanonicalBean, previewEnhancement, applyEnhancement, mergeBeans, type CanonicalBean, type EnhancementProposal } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Badge, Btn, ErrorBanner, PageHeader, SectionLabel, CompletenessRing } from "@/components/ui";

// ── Editable field ────────────────────────────────────────────────────────────

function Field({ label, value, onSave, type = "text", options }: {
  label: string;
  value: string | number | boolean | string[] | null | undefined;
  onSave: (v: string | string[] | boolean) => Promise<void>;
  type?: "text" | "number" | "select" | "toggle" | "tags";
  options?: string[];
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(Array.isArray(value) ? value.join(", ") : String(value ?? ""));
  const [saving, setSaving] = useState(false);

  const display = Array.isArray(value) ? (value.length > 0 ? value.join(", ") : "—") : (value == null || value === "" ? "—" : String(value));

  const save = async () => {
    setSaving(true);
    try {
      let parsed: string | string[] | boolean = draft;
      if (type === "tags") parsed = draft.split(",").map(s => s.trim()).filter(Boolean);
      if (type === "toggle") parsed = draft === "true";
      await onSave(parsed);
      setEditing(false);
    } finally { setSaving(false); }
  };

  if (type === "toggle") {
    return (
      <div className="flex items-center justify-between py-2 border-b border-neutral-800/50">
        <span className="text-xs text-neutral-500">{label}</span>
        <button
          onClick={async () => { setSaving(true); await onSave(!value); setSaving(false); }}
          disabled={saving}
          className={`text-xs px-2 py-0.5 rounded border transition-colors ${value ? "bg-emerald-900/40 text-emerald-400 border-emerald-800" : "bg-neutral-800 text-neutral-500 border-neutral-700"}`}>
          {saving ? "…" : value ? "Yes" : "No"}
        </button>
      </div>
    );
  }

  return (
    <div className="py-2 border-b border-neutral-800/50">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-xs text-neutral-500">{label}</span>
        {!editing && (
          <button onClick={() => setEditing(true)} className="text-[10px] text-neutral-700 hover:text-neutral-400 opacity-0 group-hover:opacity-100">edit</button>
        )}
      </div>
      {editing ? (
        <div className="flex items-center gap-2">
          {type === "select" && options ? (
            <select value={draft} onChange={e => setDraft(e.target.value)}
              className="flex-1 bg-neutral-900 border border-amber-700 rounded px-2 py-1 text-sm text-neutral-200 focus:outline-none">
              <option value="">—</option>
              {options.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input
              type={type === "number" ? "number" : "text"}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
              autoFocus
              className="flex-1 bg-neutral-900 border border-amber-700 rounded px-2 py-1 text-sm text-neutral-200 focus:outline-none"
            />
          )}
          <button onClick={save} disabled={saving} className="text-xs text-emerald-400 hover:text-emerald-300 px-2 py-1">{saving ? "…" : "✓"}</button>
          <button onClick={() => setEditing(false)} className="text-xs text-neutral-600 hover:text-neutral-400 px-1">✕</button>
        </div>
      ) : (
        <button onClick={() => setEditing(true)} className="text-sm text-neutral-300 w-full text-left hover:text-neutral-100 transition-colors">
          {type === "tags" && Array.isArray(value) && value.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {value.map(v => <span key={v} className="text-xs bg-neutral-800 border border-neutral-700 rounded px-1.5 py-0.5">{v}</span>)}
            </div>
          ) : display}
        </button>
      )}
    </div>
  );
}

export default function BeanEditorPage() {
  const params = useParams();
  const id = params?.id as string;
  const [bean, setBean] = useState<CanonicalBean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [proposal, setProposal] = useState<EnhancementProposal | null>(null);
  const [enhanceLoading, setEnhanceLoading] = useState(false);
  const [acceptedFields, setAcceptedFields] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);

  // Merge UI state
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeQuery, setMergeQuery] = useState("");
  const [mergeCandidates, setMergeCandidates] = useState<CanonicalBean[]>([]);
  const [mergeTarget, setMergeTarget] = useState<CanonicalBean | null>(null);
  const [merging, setMerging] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!id) return;
    getCanonicalBean(id).then(setBean).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  const save = async (field: string, value: unknown) => {
    const updated = await updateCanonicalBean(id, { [field]: value } as Partial<CanonicalBean>);
    setBean(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const openEnhance = async () => {
    setEnhanceLoading(true);
    setError(null);
    try {
      const p = await previewEnhancement(id);
      setProposal(p);
      // Pre-select high-confidence suggestions
      setAcceptedFields(new Set(p.suggestions.filter(s => s.confidence >= 0.8).map(s => s.field)));
    } catch (e: any) { setError(e.message); }
    finally { setEnhanceLoading(false); }
  };

  const closeEnhance = () => { setProposal(null); setAcceptedFields(new Set()); };

  const applyProposal = async () => {
    if (!proposal) return;
    setApplying(true);
    try {
      await applyEnhancement(id, Array.from(acceptedFields));
      const fresh = await getCanonicalBean(id);
      setBean(fresh);
      closeEnhance();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) { setError(e.message); }
    finally { setApplying(false); }
  };

  // Search merge candidates whenever the query or merge panel changes
  useEffect(() => {
    if (!mergeOpen || !mergeQuery.trim()) { setMergeCandidates([]); return; }
    let cancelled = false;
    getCanonicalBeans({ q: mergeQuery, page_size: 8 })
      .then(res => { if (!cancelled) setMergeCandidates(res.data.filter(b => b.id !== id)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [mergeQuery, mergeOpen, id]);

  const runMerge = async () => {
    if (!bean || !mergeTarget) return;
    if (!confirm(`Merge "${bean.canonical_name}" into "${mergeTarget.canonical_name}"? This will delete the source bean and re-link all its listings & matches. Cannot be undone.`)) return;
    setMerging(true);
    try {
      const r = await mergeBeans({ source_bean_id: id, target_bean_id: mergeTarget.id });
      router.push(`/beans/${r.target_bean_id}`);
    } catch (e: any) { setError(e.message); setMerging(false); }
  };

  if (loading) return <div className="p-6 text-neutral-600 text-sm animate-pulse">Loading bean…</div>;
  if (!bean) return <div className="p-6 text-red-400 text-sm">{error ?? "Not found"}</div>;

  return (
    <div className="p-6 max-w-4xl">
      <PageHeader
        title={<span className="flex items-center gap-2">{bean.canonical_name} {saved && <span className="text-xs text-emerald-500">Saved ✓</span>}</span>}
        subtitle="Click any field value to edit. Changes save immediately."
        actions={
          <>
            <CompletenessRing value={bean.data_completeness_score} />
            <Btn onClick={openEnhance} disabled={enhanceLoading}>{enhanceLoading ? "Analysing…" : "✨ Enhance"}</Btn>
            <Btn onClick={() => setMergeOpen(o => !o)} disabled={merging}>{mergeOpen ? "Cancel merge" : "⇆ Merge"}</Btn>
            <a href="/beans" className="text-xs text-neutral-500 hover:text-neutral-300">← All beans</a>
          </>
        }
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {mergeOpen && (
        <div className="mb-4 border border-neutral-700 bg-neutral-950/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm text-neutral-200">Merge this bean into another</div>
              <div className="text-xs text-neutral-500">
                Search for the target bean. All listings &amp; matches on this bean will move to the target,
                missing fields are copied across, and this bean is deleted.
              </div>
            </div>
            <button onClick={() => { setMergeOpen(false); setMergeTarget(null); setMergeQuery(""); }} className="text-xs text-neutral-500 hover:text-neutral-300">close ×</button>
          </div>
          <input
            type="text"
            value={mergeQuery}
            onChange={e => { setMergeQuery(e.target.value); setMergeTarget(null); }}
            placeholder="Search canonical bean name…"
            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 mb-2 focus:outline-none focus:border-amber-700"
          />
          {mergeCandidates.length > 0 && (
            <div className="max-h-60 overflow-auto border border-neutral-800 rounded divide-y divide-neutral-800">
              {mergeCandidates.map(c => {
                const selected = mergeTarget?.id === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => setMergeTarget(c)}
                    className={`w-full text-left px-3 py-2 hover:bg-neutral-900 ${selected ? "bg-amber-950/40" : ""}`}>
                    <div className="text-sm text-neutral-200">{c.canonical_name}</div>
                    <div className="text-[11px] text-neutral-600">
                      {[c.origin_country, c.origin_region, c.process].filter(Boolean).join(" · ")}
                      {" · completeness "}{(c.data_completeness_score * 100).toFixed(0)}%
                    </div>
                  </button>
                );
              })}
            </div>
          )}
          {mergeTarget && (
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-neutral-300">
                Merge <span className="text-amber-400">{bean.canonical_name}</span> →{" "}
                <span className="text-emerald-400">{mergeTarget.canonical_name}</span>
              </span>
              <Btn variant="danger" onClick={runMerge} disabled={merging}>
                {merging ? "Merging…" : "Merge & delete source"}
              </Btn>
            </div>
          )}
        </div>
      )}

      {proposal && (
        <div className="mb-4 border border-amber-700/60 bg-amber-950/20 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm text-amber-300">Enhancement proposal</div>
              <div className="text-xs text-neutral-500">
                Based on {proposal.listings_considered} linked listing(s).
                Current completeness: {(proposal.current_completeness * 100).toFixed(0)}%.
              </div>
            </div>
            <button onClick={closeEnhance} className="text-xs text-neutral-500 hover:text-neutral-300">close ×</button>
          </div>

          {proposal.suggestions.length === 0 ? (
            <div className="text-xs text-neutral-500">{proposal.notes ?? "No suggestions."}</div>
          ) : (
            <>
              <div className="space-y-2 mb-3">
                {proposal.suggestions.map(s => {
                  const checked = acceptedFields.has(s.field);
                  return (
                    <label key={s.field} className="flex items-start gap-3 p-2 rounded border border-neutral-800 hover:bg-neutral-900/40 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setAcceptedFields(prev => {
                            const next = new Set(prev);
                            checked ? next.delete(s.field) : next.add(s.field);
                            return next;
                          });
                        }}
                        className="accent-amber-500 mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-neutral-400 font-mono">{s.field}</span>
                          <span className="text-neutral-700">→</span>
                          <span className="text-emerald-400">{s.suggested_value}</span>
                          <span className="ml-auto font-mono text-neutral-600">{(s.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="text-[10px] text-neutral-600 mt-0.5">{s.source_summary}</div>
                      </div>
                    </label>
                  );
                })}
              </div>
              <div className="flex items-center gap-2">
                <Btn variant="primary" onClick={applyProposal} disabled={applying || acceptedFields.size === 0}>
                  {applying ? "Applying…" : `Apply ${acceptedFields.size} field${acceptedFields.size === 1 ? "" : "s"}`}
                </Btn>
                <Btn onClick={closeEnhance} disabled={applying}>Cancel</Btn>
                {proposal.notes && <span className="text-[11px] text-neutral-600 ml-2">{proposal.notes}</span>}
              </div>
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {/* Identity */}
        <div className="border border-neutral-800 rounded-lg p-4 group">
          <SectionLabel>Identity</SectionLabel>
          <Field label="Canonical name" value={bean.canonical_name} onSave={v => save("canonical_name", v)} />
          <Field label="Harvest year" value={bean.harvest_year} type="number" onSave={v => save("harvest_year", Number(v))} />
          <Field label="Decaf" value={bean.decaf_flag} type="toggle" onSave={v => save("decaf_flag", v)} />
          <Field label="Espresso suitable" value={bean.espresso_suitable_flag} type="toggle" onSave={v => save("espresso_suitable_flag", v)} />
          <Field label="Filter suitable" value={bean.filter_suitable_flag} type="toggle" onSave={v => save("filter_suitable_flag", v)} />
        </div>

        {/* Origin */}
        <div className="border border-neutral-800 rounded-lg p-4 group">
          <SectionLabel>Origin</SectionLabel>
          <Field label="Country" value={bean.origin_country} onSave={v => save("origin_country", v)} />
          <Field label="Region" value={bean.origin_region} onSave={v => save("origin_region", v)} />
          <Field label="Farm / Estate" value={bean.farm_or_estate} onSave={v => save("farm_or_estate", v)} />
          <Field label="Washing station" value={bean.washing_station} onSave={v => save("washing_station", v)} />
          <Field label="Producer" value={bean.producer} onSave={v => save("producer", v)} />
          <Field label="Altitude (min masl)" value={bean.altitude_masl_min} type="number" onSave={v => save("altitude_masl_min", Number(v))} />
          <Field label="Altitude (max masl)" value={bean.altitude_masl_max} type="number" onSave={v => save("altitude_masl_max", Number(v))} />
        </div>

        {/* Cultivar & Processing */}
        <div className="border border-neutral-800 rounded-lg p-4 group">
          <SectionLabel>Cultivar & Processing</SectionLabel>
          <Field label="Varietal(s)" value={bean.varietal} type="tags" onSave={v => save("varietal", v)} />
          <Field label="Process" value={bean.process} type="select"
            options={["washed","natural","honey","anaerobic","wet_hulled","carbonic_maceration","experimental","unknown"]}
            onSave={v => save("process", v)} />
          <Field label="Process detail" value={bean.process_detail} onSave={v => save("process_detail", v)} />
        </div>

        {/* Roast & Sensory */}
        <div className="border border-neutral-800 rounded-lg p-4 group">
          <SectionLabel>Roast & Sensory</SectionLabel>
          <Field label="Roast level" value={bean.roast_level} type="select"
            options={["light","medium_light","medium","medium_dark","dark","unknown"]}
            onSave={v => save("roast_level", v)} />
          <Field label="Flavour notes" value={bean.flavour_notes} type="tags" onSave={v => save("flavour_notes", v)} />
        </div>
      </div>

      {/* Metadata */}
      <div className="mt-4 border border-neutral-800 rounded-lg p-4">
        <SectionLabel>Metadata</SectionLabel>
        <div className="grid grid-cols-3 gap-4 text-xs text-neutral-600">
          <div>ID: <span className="font-mono text-neutral-500 text-[10px]">{bean.id}</span></div>
          <div>Created: {new Date(bean.created_at).toLocaleString("en-GB")}</div>
          <div>Updated: {new Date(bean.updated_at).toLocaleString("en-GB")}</div>
        </div>
      </div>
    </div>
  );
}
