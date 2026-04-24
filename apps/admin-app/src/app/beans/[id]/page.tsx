"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCanonicalBean, updateCanonicalBean, type CanonicalBean } from "@/lib/api";
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

  if (loading) return <div className="p-6 text-neutral-600 text-sm animate-pulse">Loading bean…</div>;
  if (!bean) return <div className="p-6 text-red-400 text-sm">{error ?? "Not found"}</div>;

  return (
    <div className="p-6 max-w-4xl">
      <PageHeader
        title={<span className="flex items-center gap-2">{bean.canonical_name} {saved && <span className="text-xs text-emerald-500">Saved ✓</span>}</span>}
        subtitle="Click any field value to edit. Changes save immediately."
        actions={<><CompletenessRing value={bean.data_completeness_score} /><a href="/beans" className="text-xs text-neutral-500 hover:text-neutral-300">← All beans</a></>}
      />

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

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
