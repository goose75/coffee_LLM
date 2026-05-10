"use client";

/**
 * NaturalSearchBox — Reusable natural language search input.
 *
 * Used on both the homepage (compact) and the search page (expanded).
 * Submits to /search?q=... which handles interpretation + results.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const PLACEHOLDERS = [
  "something juicy and floral for V60…",
  "syrupy espresso under £12…",
  "chocolatey but not too dark…",
  "clean washed Kenya…",
  "blueberry and tea-like with high clarity…",
  "fruity natural for filter…",
  "smooth Brazilian for everyday…",
  "bright Ethiopian with citrus notes…",
];

const QUICK_CHIPS = [
  { label: "Fruity & bright", q: "something fruity and bright for V60" },
  { label: "Espresso under £12", q: "syrupy espresso under £12" },
  { label: "Chocolatey", q: "chocolatey and nutty" },
  { label: "Floral Ethiopian", q: "floral Ethiopian natural" },
  { label: "Clean & light", q: "clean washed light roast" },
  { label: "Decaf", q: "decaf with chocolate notes" },
];

interface NaturalSearchBoxProps {
  variant?: "hero" | "page";
  initialValue?: string;
  autoFocus?: boolean;
}

export default function NaturalSearchBox({
  variant = "hero",
  initialValue = "",
  autoFocus = false,
}: NaturalSearchBoxProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(initialValue);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [focused, setFocused] = useState(false);

  // Cycle placeholder text
  useEffect(() => {
    const iv = setInterval(() => {
      if (!focused && !value) {
        setPlaceholderIdx((i) => (i + 1) % PLACEHOLDERS.length);
      }
    }, 3200);
    return () => clearInterval(iv);
  }, [focused, value]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const submit = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    },
    [router]
  );

  const isPage = variant === "page";

  return (
    <div className={`nsb-root ${isPage ? "nsb-page" : "nsb-hero"}`}>
      {/* Search input */}
      <div className={`nsb-field ${focused ? "nsb-focused" : ""}`}>
        <svg
          className="nsb-icon"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="M16.5 16.5L21 21" />
        </svg>

        <input
          ref={inputRef}
          className="nsb-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit(value);
            if (e.key === "Escape") {
              setValue("");
              inputRef.current?.blur();
            }
          }}
          placeholder={PLACEHOLDERS[placeholderIdx]}
          aria-label="Describe the coffee you're looking for"
          autoComplete="off"
          spellCheck="false"
        />

        {value && (
          <button
            className="nsb-clear"
            onClick={() => {
              setValue("");
              inputRef.current?.focus();
            }}
            aria-label="Clear"
            tabIndex={-1}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        )}

        <button
          className="nsb-submit"
          onClick={() => submit(value)}
          aria-label="Search"
          disabled={!value.trim()}
        >
          {isPage ? "Search" : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>
      </div>

      {/* Quick chips — shown when not typing */}
      {!value && (
        <div className="nsb-chips" aria-label="Quick searches">
          {QUICK_CHIPS.map((chip) => (
            <button
              key={chip.q}
              className="nsb-chip"
              onClick={() => submit(chip.q)}
              tabIndex={0}
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}

      <style jsx>{`
        .nsb-root {
          width: 100%;
        }
        .nsb-hero {
          max-width: 560px;
        }
        .nsb-page {
          max-width: 720px;
          margin: 0 auto;
        }

        /* Field */
        .nsb-field {
          display: flex;
          align-items: center;
          gap: 10px;
          background: var(--surface);
          border: 1.5px solid var(--border);
          border-radius: 14px;
          padding: 0 6px 0 16px;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .nsb-focused {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px var(--accent-dim);
        }

        .nsb-icon {
          color: var(--text-faint);
          flex-shrink: 0;
          transition: color 0.2s;
        }
        .nsb-focused .nsb-icon {
          color: var(--accent);
        }

        .nsb-input {
          flex: 1;
          border: none;
          background: transparent;
          color: var(--text);
          font-family: var(--font-body);
          font-size: 15px;
          line-height: 1;
          padding: 14px 0;
          outline: none;
          min-width: 0;
        }
        .nsb-input::placeholder {
          color: var(--text-faint);
          font-style: italic;
          transition: color 0.3s;
        }
        .nsb-input:focus::placeholder {
          color: transparent;
        }

        .nsb-clear {
          padding: 6px;
          border: none;
          background: transparent;
          color: var(--text-faint);
          cursor: pointer;
          border-radius: 6px;
          display: flex;
          align-items: center;
          transition: color 0.15s;
          flex-shrink: 0;
        }
        .nsb-clear:hover { color: var(--text); }

        .nsb-submit {
          padding: 8px 16px;
          border: none;
          border-radius: 10px;
          background: var(--accent);
          color: white;
          font-family: var(--font-body);
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          gap: 4px;
          transition: opacity 0.15s, background 0.15s;
          margin: 5px 0;
        }
        .nsb-submit:disabled {
          opacity: 0.35;
          cursor: default;
        }
        .nsb-submit:not(:disabled):hover {
          background: var(--accent-light);
        }

        /* Chips */
        .nsb-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 7px;
          margin-top: 12px;
        }
        .nsb-chip {
          padding: 6px 13px;
          border-radius: 100px;
          border: 1px solid var(--border-light);
          background: transparent;
          color: var(--text-muted);
          font-family: var(--font-body);
          font-size: 12px;
          cursor: pointer;
          transition: border-color 0.15s, color 0.15s, background 0.15s;
          white-space: nowrap;
        }
        .nsb-chip:hover {
          border-color: var(--accent);
          color: var(--accent);
          background: var(--accent-dim);
        }

        @media (max-width: 480px) {
          .nsb-submit { padding: 8px 12px; font-size: 12px; }
          .nsb-input { font-size: 14px; }
          .nsb-chips { gap: 6px; }
          .nsb-chip { font-size: 11px; padding: 5px 10px; }
        }
      `}</style>
    </div>
  );
}
