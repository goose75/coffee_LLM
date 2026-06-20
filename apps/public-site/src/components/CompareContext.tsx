"use client";

/**
 * CompareContext — Global state for the compare tray.
 *
 * Up to 3 coffees can be added. A floating tray appears at the bottom
 * of the screen when 2+ are selected. Clicking "Compare" navigates
 * to /coffees/compare?ids=...
 */

import {
  createContext, useContext, useState, useCallback,
  useEffect, type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

interface CompareEntry { id: string; name: string; }
interface CompareCtx {
  items: CompareEntry[];
  add: (id: string, name: string) => void;
  remove: (id: string) => void;
  has: (id: string) => boolean;
  clear: () => void;
}

const Ctx = createContext<CompareCtx>({
  items: [], add: () => {}, remove: () => {}, has: () => false, clear: () => {},
});

export function CompareProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CompareEntry[]>([]);

  const add = useCallback((id: string, name: string) => {
    setItems((prev) => {
      if (prev.find((i) => i.id === id)) return prev;
      if (prev.length >= 3) return prev;
      return [...prev, { id, name }];
    });
  }, []);

  const remove = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const has = useCallback((id: string) => items.some((i) => i.id === id), [items]);

  const clear = useCallback(() => setItems([]), []);

  return (
    <Ctx.Provider value={{ items, add, remove, has, clear }}>
      {children}
      <CompareTray />
    </Ctx.Provider>
  );
}

export function useCompare() { return useContext(Ctx); }

// ── Compare Tray ──────────────────────────────────────────────────────────────

const COLOURS = ["#c4763a", "#6b9e8c", "#8b6bab"];

function CompareTray() {
  const { items, remove, clear } = useCompare();
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(items.length >= 1);
  }, [items.length]);

  if (!visible) return null;

  const canCompare = items.length >= 2;

  return (
    <div className="tray-root" role="region" aria-label="Compare tray">
      <div className="tray-inner">
        <div className="tray-slots">
          {items.map((item, i) => (
            <div key={item.id} className="tray-slot">
              <span className="tray-dot" style={{ background: COLOURS[i] }} />
              <span className="tray-name">{item.name.split(",")[0].trim()}</span>
              <button
                className="tray-remove"
                onClick={() => remove(item.id)}
                aria-label={`Remove ${item.name}`}
              >×</button>
            </div>
          ))}
          {items.length < 3 && (
            <div className="tray-slot tray-empty">
              <span className="tray-plus">+</span>
              <span className="tray-empty-label">Add coffee</span>
            </div>
          )}
        </div>
        <div className="tray-actions">
          <button className="tray-clear" onClick={clear}>Clear</button>
          <button
            className={`tray-compare ${canCompare ? "tray-compare-ready" : ""}`}
            disabled={!canCompare}
            onClick={() => {
              router.push(`/coffees/compare?ids=${items.map((i) => i.id).join(",")}`);
            }}
          >
            Compare {items.length >= 2 ? `(${items.length})` : ""}
          </button>
        </div>
      </div>

      <style jsx>{`
        .tray-root {
          position: fixed;
          bottom: calc(var(--tab-h) + var(--safe-bottom) + 8px);
          left: 50%;
          transform: translateX(-50%);
          z-index: 100;
          width: calc(100% - 32px);
          max-width: 640px;
          animation: tray-up 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        @keyframes tray-up {
          from { transform: translateX(-50%) translateY(20px); opacity: 0; }
          to   { transform: translateX(-50%) translateY(0);    opacity: 1; }
        }
        .tray-inner {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 12px 16px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          box-shadow: 0 8px 32px rgba(0,0,0,0.15);
          backdrop-filter: blur(12px);
        }
        .tray-slots {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;
        }
        .tray-slot {
          display: flex;
          align-items: center;
          gap: 6px;
          background: var(--surface-raised);
          border-radius: 100px;
          padding: 5px 10px;
          min-width: 0;
          flex-shrink: 1;
        }
        .tray-empty {
          border: 1.5px dashed var(--border);
          background: transparent;
          opacity: 0.5;
        }
        .tray-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .tray-name {
          font-family: var(--font-body);
          font-size: 12px;
          color: var(--text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100px;
        }
        .tray-remove {
          background: none;
          border: none;
          color: var(--text-faint);
          cursor: pointer;
          font-size: 14px;
          line-height: 1;
          padding: 0;
          flex-shrink: 0;
        }
        .tray-remove:hover { color: var(--text); }
        .tray-plus { color: var(--text-faint); font-size: 14px; }
        .tray-empty-label {
          font-family: var(--font-body);
          font-size: 11px;
          color: var(--text-faint);
        }
        .tray-actions { display: flex; gap: 8px; flex-shrink: 0; }
        .tray-clear {
          padding: 7px 12px;
          border-radius: 100px;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-faint);
          font-family: var(--font-body);
          font-size: 12px;
          cursor: pointer;
          transition: all 0.15s;
        }
        .tray-clear:hover { color: var(--text); border-color: var(--text-muted); }
        .tray-compare {
          padding: 7px 16px;
          border-radius: 100px;
          border: none;
          background: var(--border);
          color: var(--text-faint);
          font-family: var(--font-body);
          font-size: 12px;
          font-weight: 500;
          cursor: not-allowed;
          transition: all 0.15s;
          white-space: nowrap;
        }
        .tray-compare-ready {
          background: var(--accent);
          color: white;
          cursor: pointer;
        }
        .tray-compare-ready:hover { background: var(--accent-light); }
      `}</style>
    </div>
  );
}
