"use client";

/**
 * BrewFit — Brew suitability visual component.
 *
 * Visual model: Calibrated Brew Tokens
 *
 * Each brew method gets a horizontal lane. The lane has a filled track
 * whose length shows the score. The fill colour shifts from warm amber
 * (excellent) through neutral (works) to cool grey (avoid).
 * The tier label and icon sit at the start. A short grounded reason
 * sits below on expand.
 *
 * Why tokens over stars:
 * - Stars imply subjective opinion; these are derived from coffee attributes
 * - The horizontal fill makes differences between methods immediately comparable
 * - The tier system (excellent/good/works/possible/avoid) gives language
 *   without false precision
 * - Expanding any row shows the exact reasoning — fully transparent
 */

import { useEffect, useState } from "react";



interface BrewScore {
  method: string;
  label: string;
  icon: string;
  score: number;
  tier: "excellent" | "good" | "works" | "possible" | "avoid";
  reasons: string[];
  short_reason: string;
}

interface BrewFitData {
  coffee_id: string;
  canonical_name: string;
  scores: BrewScore[];
}

const TIER_COLOURS: Record<string, string> = {
  excellent: "#c4763a",
  good:      "#d4a84b",
  works:     "#6b9e8c",
  possible:  "#9a9890",
  avoid:     "#d5d0c8",
};

const TIER_LABELS: Record<string, string> = {
  excellent: "Excellent",
  good:      "Good",
  works:     "Works",
  possible:  "Possible",
  avoid:     "Skip",
};

export default function BrewFit({ coffeeId }: { coffeeId: string }) {
  const [data, setData] = useState<BrewFitData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`/api/coffees/${coffeeId}/brew-fit`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [coffeeId]);

  if (loading) return <BrewSkeleton />;
  if (error || !data) return null;

  const scores = data.scores ?? [];
  if (scores.length === 0) return null;

  // Show excellent/good prominently, rest collapsed by default
  const topScores = scores.filter((s: BrewScore) => s.tier !== "avoid");
  const avoidScores = scores.filter((s: BrewScore) => s.tier === "avoid");

  return (
    <div className="brewfit-root">
      <div className="brewfit-header">
        <span className="brewfit-title">Brew Fit</span>
        <span className="brewfit-subtitle">How this coffee brews across different methods</span>
      </div>

      <div className="brewfit-list">
        {topScores.map((score) => (
          <BrewRow
            key={score.method}
            score={score}
            expanded={expanded === score.method}
            onToggle={() => setExpanded(expanded === score.method ? null : score.method)}
          />
        ))}

        {avoidScores.length > 0 && (
          <div className="brewfit-avoid-section">
            <span className="brewfit-avoid-label">Less suitable</span>
            {avoidScores.map((score) => (
              <BrewRow
                key={score.method}
                score={score}
                expanded={expanded === score.method}
                onToggle={() => setExpanded(expanded === score.method ? null : score.method)}
                dimmed
              />
            ))}
          </div>
        )}
      </div>

      <style jsx>{styles}</style>
    </div>
  );
}

function BrewRow({
  score,
  expanded,
  onToggle,
  dimmed = false,
}: {
  score: BrewScore;
  expanded: boolean;
  onToggle: () => void;
  dimmed?: boolean;
}) {
  const colour = TIER_COLOURS[score.tier];
  const tierLabel = TIER_LABELS[score.tier];
  const hasDetail = score.short_reason || score.reasons.length > 0;

  return (
    <div className={`brew-row ${dimmed ? "brew-row-dimmed" : ""}`}>
      <button
        className="brew-row-main"
        onClick={hasDetail ? onToggle : undefined}
        aria-expanded={expanded}
        style={{ cursor: hasDetail ? "pointer" : "default" }}
      >
        {/* Icon + label */}
        <div className="brew-method-id">
          <span className="brew-icon">{score.icon}</span>
          <span className="brew-label">{score.label}</span>
        </div>

        {/* Track */}
        <div className="brew-track-wrap">
          <div
            className="brew-track-fill"
            style={{
              width: `${score.score}%`,
              background: colour,
              opacity: dimmed ? 0.4 : 1,
            }}
          />
        </div>

        {/* Tier badge */}
        <span
          className="brew-tier"
          style={{
            color: dimmed ? "var(--text-faint)" : colour,
            opacity: dimmed ? 0.6 : 1,
          }}
        >
          {tierLabel}
        </span>

        {/* Expand chevron */}
        {hasDetail && (
          <span className={`brew-chevron ${expanded ? "brew-chevron-open" : ""}`}>
            ›
          </span>
        )}
      </button>

      {/* Expanded detail */}
      {expanded && hasDetail && (
        <div className="brew-detail">
          {score.short_reason && (
            <p className="brew-short-reason">{score.short_reason}</p>
          )}
          {score.reasons.length > 0 && (
            <ul className="brew-reasons">
              {score.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function BrewSkeleton() {
  return (
    <div className="brewfit-skeleton">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="brew-skeleton-row" style={{ animationDelay: `${i * 0.07}s` }} />
      ))}
    </div>
  );
}

const styles = `
  .brewfit-root {
    padding: 20px 0;
  }
  .brewfit-header {
    margin-bottom: 16px;
  }
  .brewfit-title {
    font-family: var(--font-body);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    display: block;
    margin-bottom: 3px;
  }
  .brewfit-subtitle {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-faint);
    display: block;
  }

  .brewfit-list { display: flex; flex-direction: column; gap: 2px; }

  .brew-row {
    border-radius: 8px;
    overflow: hidden;
    transition: background 0.15s;
  }
  .brew-row:hover { background: var(--surface-raised); }
  .brew-row-dimmed { opacity: 0.7; }

  .brew-row-main {
    width: 100%;
    display: grid;
    grid-template-columns: 130px 1fr 64px 16px;
    align-items: center;
    gap: 10px;
    padding: 9px 10px;
    background: none;
    border: none;
    text-align: left;
  }

  .brew-method-id {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }
  .brew-icon { font-size: 15px; flex-shrink: 0; }
  .brew-label {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .brew-track-wrap {
    height: 6px;
    background: var(--surface-raised);
    border-radius: 3px;
    overflow: hidden;
  }
  .brew-track-fill {
    height: 100%;
    border-radius: 3px;
    min-width: 3px;
    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .brew-tier {
    font-family: var(--font-body);
    font-size: 11px;
    font-weight: 600;
    text-align: right;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  .brew-chevron {
    font-size: 16px;
    color: var(--text-faint);
    transition: transform 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .brew-chevron-open { transform: rotate(90deg); }

  .brew-detail {
    padding: 0 10px 12px 47px;
    animation: detail-fade 0.18s ease;
  }
  @keyframes detail-fade {
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .brew-short-reason {
    font-family: var(--font-display);
    font-size: 14px;
    font-style: italic;
    color: var(--text-muted);
    margin: 0 0 6px;
    line-height: 1.5;
  }
  .brew-reasons {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .brew-reasons li {
    font-family: var(--font-body);
    font-size: 12px;
    color: var(--text-faint);
    padding-left: 12px;
    position: relative;
    line-height: 1.4;
  }
  .brew-reasons li::before {
    content: "·";
    position: absolute;
    left: 0;
    color: var(--accent);
  }

  .brewfit-avoid-section { margin-top: 8px; }
  .brewfit-avoid-label {
    font-family: var(--font-body);
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-faint);
    display: block;
    padding: 4px 10px 6px;
  }

  .brewfit-skeleton {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 20px 0;
  }
  .brew-skeleton-row {
    height: 36px;
    border-radius: 8px;
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @media (max-width: 480px) {
    .brew-row-main {
      grid-template-columns: 110px 1fr 54px 14px;
      gap: 7px;
    }
    .brew-label { font-size: 12px; }
  }
`;
