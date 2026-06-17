"use client";

/**
 * Explanation components for Grounds.
 *
 * useExplanation — React hook that fetches a grounded explanation.
 * ExplanationBlurb — Renders the explanation inline with a subtle label.
 *
 * Design principles:
 * - No chat UI, no expanding panels, no typing animations.
 * - The explanation appears as a single quiet sentence below the relevant content.
 * - If the API key is absent or the call fails, the fallback rules-based summary
 *   appears instead — users never see an empty state or an error.
 * - The "source" field is used only for debugging — never shown to users.
 */

import { useEffect, useState, useRef } from "react";



// ── Hook ──────────────────────────────────────────────────────────────────────

interface ExplanationResult {
  text: string;
  loading: boolean;
}

export function useExplanation(
  type: "coffee" | "compare" | "origin" | "roaster" | "search",
  params: Record<string, string>,
  enabled = true,
): ExplanationResult {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const cacheRef = useRef<Record<string, string>>({});

  useEffect(() => {
    if (!enabled) { setLoading(false); return; }

    const url = buildUrl(type, params);
    if (!url) { setLoading(false); return; }

    // Check in-memory cache
    if (cacheRef.current[url]) {
      setText(cacheRef.current[url]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const controller = new AbortController();

    fetch(url, { signal: controller.signal })
      .then((r) => r.json())
      .then((d) => {
        const explanation = d.explanation ?? "";
        cacheRef.current[url] = explanation;
        setText(explanation);
        setLoading(false);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setLoading(false);
      });

    return () => controller.abort();
  }, [type, JSON.stringify(params), enabled]);

  return { text, loading };
}

function buildUrl(type: string, params: Record<string, string>): string | null {
  switch (type) {
    case "coffee":
      return params.coffeeId
        ? `/api/explain/coffee/${params.coffeeId}`
        : null;
    case "compare":
      return params.ids
        ? `/api/explain/compare?ids=${encodeURIComponent(params.ids)}`
        : null;
    case "origin":
      return params.country
        ? `/api/explain/origin/${encodeURIComponent(params.country)}`
        : null;
    case "roaster":
      return params.roasterId
        ? `/api/explain/roaster/${params.roasterId}`
        : null;
    case "search":
      return params.q && params.coffeeId
        ? `/api/explain/search?q=${encodeURIComponent(params.q)}&coffee_id=${params.coffeeId}`
        : null;
    default:
      return null;
  }
}

// ── ExplanationBlurb ──────────────────────────────────────────────────────────

interface ExplanationBlurbProps {
  type: "coffee" | "compare" | "origin" | "roaster" | "search";
  params: Record<string, string>;
  enabled?: boolean;
  className?: string;
  /** If true, show a subtle skeleton while loading */
  showSkeleton?: boolean;
}

export function ExplanationBlurb({
  type,
  params,
  enabled = true,
  className = "",
  showSkeleton = true,
}: ExplanationBlurbProps) {
  const { text, loading } = useExplanation(type, params, enabled);

  if (!enabled) return null;

  if (loading && showSkeleton) {
    return (
      <div className={`expblurb-skeleton ${className}`}>
        <div className="expblurb-skeleton-line" style={{ width: "85%" }} />
      </div>
    );
  }

  if (!text) return null;

  return (
    <p className={`expblurb-text ${className}`}>
      {text}
    </p>
  );
}

// ── Styles are injected globally via globals.css additions ────────────────────
// Add these to your globals.css:
//
// .expblurb-text {
//   font-family: var(--font-display);
//   font-size: 14px;
//   font-style: italic;
//   color: var(--text-muted);
//   line-height: 1.6;
//   margin: 0;
// }
// .expblurb-skeleton { padding: 2px 0; }
// .expblurb-skeleton-line {
//   height: 14px;
//   border-radius: 4px;
//   background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
//   background-size: 200% 100%;
//   animation: shimmer 1.4s ease-in-out infinite;
// }
