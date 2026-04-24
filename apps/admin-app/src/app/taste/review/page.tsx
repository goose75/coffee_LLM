"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader, ErrorBanner, EmptyState, ConfidenceBar, SkeletonRows, DataTable, Btn } from "@/components/ui";

interface TagReview {
  tag_id: string;
  bean_id: string;
  bean_name: string;
  raw_note: string;
  slug: string;
  label: string;
  confidence: number;
  source: string;
  review_status: string;
  llm_audit: { reasoning?: string; prompt_version?: string } | null;
  created_at: string;
}

// Derive family from slug
function familyLabel(slug: string): string {
  const families: Record<string, string> = {
    fruity: "Fruity 🍋", floral: "Floral 🌸", sweet: "Sweet 🍯",
    chocolate: "Chocolate 🍫", nutty: "Nutty 🌰", spice: "Spice 🌶",
    earthy: "Earthy 🌿", fermented: "Fermented 🍷",
  };
  return families[slug.split(".")[0]] ?? slug.split(".")[0];
}

export default function TasteReviewPage() {
  const [tags, setTags] = useState<TagReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioning, setActioning] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<TagReview[]>("/taste/review?max_confidence=0.75&page_size=100");
      setTags(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (tagId: string, action: "accept" | "reject") => {
    setActioning(tagId);
    try {
      await apiFetch(`/taste/review/${tagId}/${action}`, { method: "POST" });
      setTags(prev => prev.filter(t => t.tag_id !== tagId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActioning(null);
    }
  };

  const triggerTagAll = async () => {
    try {
      const r = await apiFetch<{ beans_processed: number; total_tags_upserted: number }>(
        "/taste/tag-all?use_llm=false", { method: "POST" }
      );
      alert(`Tagged ${r.beans_processed} beans, ${r.total_tags_upserted} tags created.`);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-6">
        <PageHeader
          title="Taste Tag Review"
          subtitle={`${tags.length} low-confidence LLM tags awaiting review`}
        />
        <button onClick={triggerTagAll}
          className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-neutral-300 transition-colors">
          ↻ Re-run rule tagger
        </button>
      </div>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {/* Legend */}
      <div className="mb-4 p-3 bg-neutral-900/40 border border-neutral-800 rounded-lg text-xs text-neutral-500">
        <strong className="text-neutral-400">How to review:</strong> Each row is a raw tasting note the LLM mapped
        to a taxonomy tag with low confidence. Accept if the mapping looks right; reject if it's wrong.
        Rejected tags are removed from the public profile.
      </div>

      <DataTable headers={["Coffee", "Raw note", "→ Tag", "Family", "Confidence", "LLM reasoning", "Actions"]}>
        {loading ? <SkeletonRows cols={7} rows={8} /> :
          tags.length === 0 ? (
            <tr><td colSpan={7}><EmptyState
              message="No tags pending review. All LLM mappings are either high-confidence or already reviewed."
            /></td></tr>
          ) : tags.map(tag => (
            <tr key={tag.tag_id} className="border-b border-neutral-800/40 hover:bg-neutral-900/20 group">
              <td className="px-4 py-2.5 text-xs text-neutral-300 max-w-[160px] truncate">{tag.bean_name}</td>
              <td className="px-4 py-2.5">
                <span className="font-mono text-xs bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800 text-neutral-300">
                  {tag.raw_note}
                </span>
              </td>
              <td className="px-4 py-2.5 text-xs text-amber-400 font-mono">{tag.label}</td>
              <td className="px-4 py-2.5 text-xs text-neutral-500">{familyLabel(tag.slug)}</td>
              <td className="px-4 py-2.5"><ConfidenceBar value={tag.confidence} /></td>
              <td className="px-4 py-2.5 text-xs text-neutral-600 max-w-[200px] truncate italic"
                title={tag.llm_audit?.reasoning ?? ""}>
                {tag.llm_audit?.reasoning ?? "—"}
              </td>
              <td className="px-4 py-2.5">
                <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    disabled={actioning === tag.tag_id}
                    onClick={() => act(tag.tag_id, "accept")}
                    className="px-2 py-1 text-[11px] bg-emerald-900/40 hover:bg-emerald-800 text-emerald-400 rounded border border-emerald-800 transition-colors disabled:opacity-40">
                    ✓
                  </button>
                  <button
                    disabled={actioning === tag.tag_id}
                    onClick={() => act(tag.tag_id, "reject")}
                    className="px-2 py-1 text-[11px] bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded border border-red-900 transition-colors disabled:opacity-40">
                    ✕
                  </button>
                </div>
              </td>
            </tr>
          ))
        }
      </DataTable>
    </div>
  );
}
