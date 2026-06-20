"use client";

import { useCompare } from "@/components/CompareContext";

export default function CompareButtonDetail({
  coffeeId,
  coffeeName,
}: {
  coffeeId: string;
  coffeeName: string;
}) {
  const { has, add, remove, items } = useCompare();
  const inCompare = has(coffeeId);
  const full = items.length >= 3 && !inCompare;

  return (
    <button
      onClick={() => {
        if (inCompare) remove(coffeeId);
        else if (!full) add(coffeeId, coffeeName);
      }}
      disabled={full}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 10px 3px 8px",
        borderRadius: 100,
        border: inCompare
          ? "1.5px solid var(--accent)"
          : "1.5px solid var(--border)",
        background: inCompare ? "var(--accent-dim)" : "transparent",
        color: inCompare ? "var(--accent)" : "var(--text-faint)",
        fontSize: 11,
        fontFamily: "var(--font-body)",
        fontWeight: 500,
        cursor: full ? "not-allowed" : "pointer",
        opacity: full ? 0.35 : 1,
        transition: "all 0.15s",
        whiteSpace: "nowrap",
      }}
      title={full ? "Maximum 3 coffees" : undefined}
    >
      <span style={{ fontSize: 13, lineHeight: 1 }}>
        {inCompare ? "✓" : "+"}
      </span>
      {inCompare ? "In compare" : "Compare"}
    </button>
  );
}
