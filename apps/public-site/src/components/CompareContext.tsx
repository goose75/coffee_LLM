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
  useEffect, useRef, type ReactNode,
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

interface CoffeeSearchResult {
  id: string;
  canonical_name: string;
  origin_country?: string;
}

function CompareTray() {
  const { items, remove, clear, add } = useCompare();
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CoffeeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setVisible(items.length >= 1);
  }, [items.length]);

  // Search for coffees
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    fetch(`${apiBase}/api/v1/coffees?q=${encodeURIComponent(searchQuery)}&page_size=5`)
      .then(r => {
        if (!r.ok) throw new Error("Search failed");
        return r.json();
      })
      .then(data => {
        setSearchResults((data.data || []).map((coffee: any) => ({
          id: coffee.id,
          canonical_name: coffee.canonical_name,
          origin_country: coffee.origin_country,
        })));
        setSearching(false);
      })
      .catch(() => {
        setSearchResults([]);
        setSearching(false);
      });
  }, [searchQuery]);

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
            <div className="tray-slot tray-empty tray-search-trigger" onClick={() => setShowSearch(!showSearch)} style={{ cursor: "pointer" }}>
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

      {/* Search overlay */}
      {showSearch && (
        <div className="tray-search-container">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search coffees..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setShowSearch(false);
                setSearchQuery("");
              }
            }}
            autoFocus
            className="tray-search-input"
          />

          {searchQuery && (
            <div className="tray-search-results">
              {searching ? (
                <div className="tray-result-item disabled">Searching...</div>
              ) : searchResults.length > 0 ? (
                searchResults.map((coffee) => {
                  const alreadyAdded = items.some(i => i.id === coffee.id);
                  return (
                    <button
                      key={coffee.id}
                      className={`tray-result-item ${alreadyAdded ? "disabled" : ""}`}
                      disabled={alreadyAdded}
                      onClick={() => {
                        if (!alreadyAdded) {
                          add(coffee.id, coffee.canonical_name);
                          setSearchQuery("");
                          setShowSearch(false);
                        }
                      }}
                    >
                      <span className="tray-result-name">{coffee.canonical_name}</span>
                      {coffee.origin_country && (
                        <span className="tray-result-origin">{coffee.origin_country}</span>
                      )}
                    </button>
                  );
                })
              ) : (
                <div className="tray-result-item disabled">No coffees found</div>
              )}
            </div>
          )}
        </div>
      )}

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

        /* Search overlay */
        .tray-search-container {
          position: absolute;
          bottom: 100%;
          left: 0;
          right: 0;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 12px 12px 0 0;
          padding: 12px;
          margin-bottom: 8px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 280px;
          overflow-y: auto;
        }
        .tray-search-input {
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 8px;
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-body);
          font-size: 14px;
          outline: none;
        }
        .tray-search-input:focus {
          border-color: var(--accent);
          box-shadow: 0 0 0 2px var(--accent-dim);
        }
        .tray-search-results {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .tray-result-item {
          padding: 10px 12px;
          border: none;
          border-radius: 6px;
          background: var(--surface-raised);
          color: var(--text);
          font-family: var(--font-body);
          font-size: 13px;
          text-align: left;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: background 0.15s;
        }
        .tray-result-item:hover:not(.disabled) {
          background: var(--bg-warm);
        }
        .tray-result-item.disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .tray-result-name {
          flex: 1;
          font-weight: 500;
        }
        .tray-result-origin {
          font-size: 11px;
          color: var(--text-faint);
        }
      `}</style>
    </div>
  );
}
