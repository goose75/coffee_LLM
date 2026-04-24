"use client";

import { ReactNode } from "react";

// ── Badge ─────────────────────────────────────────────────────────────────────

const BADGE_VARIANTS: Record<string, string> = {
  // Status
  healthy: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  completed: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  accepted: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  valid: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  in_stock: "bg-emerald-900/40 text-emerald-400 border-emerald-800",
  stale: "bg-amber-900/40 text-amber-400 border-amber-800",
  partial: "bg-amber-900/40 text-amber-400 border-amber-800",
  pending: "bg-amber-900/40 text-amber-400 border-amber-800",
  running: "bg-blue-900/40 text-blue-400 border-blue-800",
  failed: "bg-red-900/40 text-red-400 border-red-800",
  rejected: "bg-red-900/40 text-red-400 border-red-800",
  invalid: "bg-red-900/40 text-red-400 border-red-800",
  out_of_stock: "bg-red-900/40 text-red-400 border-red-800",
  inactive: "bg-neutral-900 text-neutral-600 border-neutral-800",
  unknown: "bg-neutral-800 text-neutral-400 border-neutral-700",
  // Parser strategies
  shopify: "bg-green-900/30 text-green-400 border-green-800",
  schema_org: "bg-blue-900/30 text-blue-400 border-blue-800",
  html: "bg-orange-900/30 text-orange-400 border-orange-800",
  llm: "bg-purple-900/30 text-purple-400 border-purple-800",
  // Methods
  exact: "bg-emerald-900/30 text-emerald-400 border-emerald-800",
  fuzzy: "bg-blue-900/30 text-blue-400 border-blue-800",
  embedding: "bg-purple-900/30 text-purple-400 border-purple-800",
  combined: "bg-amber-900/30 text-amber-400 border-amber-800",
  manual: "bg-neutral-800 text-neutral-400 border-neutral-700",
  // Sources
  rule: "bg-blue-900/30 text-blue-400 border-blue-800",
  db: "bg-neutral-800 text-neutral-400 border-neutral-700",
};

interface BadgeProps { value: string; label?: string; dot?: boolean; }

export function Badge({ value, label, dot }: BadgeProps) {
  const cls = BADGE_VARIANTS[value.toLowerCase()] ?? BADGE_VARIANTS.unknown;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${cls}`}>
      {dot && value === "running" && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
      )}
      {label ?? value}
    </span>
  );
}

// ── Confidence bar ────────────────────────────────────────────────────────────

export function ConfidenceBar({ value, showPct = true }: { value: number; showPct?: boolean }) {
  const color = value >= 0.92 ? "bg-emerald-600" : value >= 0.75 ? "bg-amber-600" : "bg-red-800";
  const textColor = value >= 0.92 ? "text-emerald-400" : value >= 0.75 ? "text-amber-400" : "text-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-neutral-800 rounded-full overflow-hidden flex-shrink-0">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value * 100}%` }} />
      </div>
      {showPct && <span className={`text-xs font-mono ${textColor}`}>{(value * 100).toFixed(0)}%</span>}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

export function StatCard({ label, value, sub, color = "text-neutral-200" }: { label: string; value: ReactNode; sub?: string; color?: string }) {
  return (
    <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/40">
      <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-1.5">{label}</div>
      <div className={`text-2xl font-mono font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-neutral-600 mt-1">{sub}</div>}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="py-16 text-center">
      <div className="text-neutral-600 text-sm">{message}</div>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

// ── Skeleton row ──────────────────────────────────────────────────────────────

export function SkeletonRows({ cols = 5, rows = 6 }: { cols?: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b border-neutral-800/40">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-3 bg-neutral-800 rounded animate-pulse" style={{ width: `${50 + (i * j * 7) % 40}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────

interface PaginationProps { page: number; total: number; pageSize: number; onPage: (p: number) => void; }

export function Pagination({ page, total, pageSize, onPage }: PaginationProps) {
  if (total <= pageSize) return null;
  const pages = Math.ceil(total / pageSize);
  return (
    <div className="mt-4 flex items-center justify-between text-sm">
      <span className="text-neutral-600 text-xs">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
      </span>
      <div className="flex gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}
          className="px-3 py-1.5 rounded border border-neutral-700 text-neutral-400 hover:text-neutral-200 disabled:opacity-30 text-xs transition-colors">
          ← Prev
        </button>
        {pages <= 7 ? Array.from({ length: pages }, (_, i) => i + 1).map(p => (
          <button key={p} onClick={() => onPage(p)}
            className={`px-3 py-1.5 rounded border text-xs transition-colors ${p === page ? "border-amber-700 text-amber-400 bg-amber-900/20" : "border-neutral-700 text-neutral-400 hover:text-neutral-200"}`}>
            {p}
          </button>
        )) : (
          <span className="px-3 py-1.5 text-xs text-neutral-500">Page {page} of {pages}</span>
        )}
        <button onClick={() => onPage(page + 1)} disabled={page >= pages}
          className="px-3 py-1.5 rounded border border-neutral-700 text-neutral-400 hover:text-neutral-200 disabled:opacity-30 text-xs transition-colors">
          Next →
        </button>
      </div>
    </div>
  );
}

// ── Error banner ──────────────────────────────────────────────────────────────

export function ErrorBanner({ error, onDismiss }: { error: string; onDismiss: () => void }) {
  return (
    <div className="mb-4 px-4 py-2.5 bg-red-900/20 border border-red-800/50 rounded text-sm text-red-400 flex items-center justify-between">
      <span>{error}</span>
      <button onClick={onDismiss} className="text-red-700 hover:text-red-400 ml-4">×</button>
    </div>
  );
}

// ── Page header ───────────────────────────────────────────────────────────────

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-lg font-medium text-neutral-100">{title}</h1>
        {subtitle && <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

// ── Table wrapper ─────────────────────────────────────────────────────────────

export function DataTable({ headers, children, className = "" }: { headers: string[]; children: ReactNode; className?: string }) {
  return (
    <div className={`border border-neutral-800 rounded-lg overflow-hidden ${className}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-neutral-800 bg-neutral-900/60">
            {headers.map((h, i) => (
              <th key={i} className="px-4 py-2.5 text-left text-[11px] font-medium text-neutral-500 uppercase tracking-wider whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-3 flex-wrap mb-4">{children}</div>;
}

export function FilterSelect({ value, onChange, options, placeholder }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; placeholder?: string }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-300 focus:outline-none focus:border-amber-600">
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function FilterSearch({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input type="search" value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder ?? "Search…"}
      className="bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-amber-600 w-52" />
  );
}

// ── Button ────────────────────────────────────────────────────────────────────

type BtnVariant = "default" | "primary" | "danger" | "ghost";

const BTN_CLS: Record<BtnVariant, string> = {
  default: "bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700",
  primary: "bg-amber-700 hover:bg-amber-600 text-amber-50 border-amber-700",
  danger: "bg-red-900/60 hover:bg-red-800 text-red-200 border-red-800",
  ghost: "bg-transparent hover:bg-neutral-800 text-neutral-400 border-transparent",
};

export function Btn({ children, onClick, variant = "default", disabled, className = "", size = "sm" }: { children: ReactNode; onClick?: () => void; variant?: BtnVariant; disabled?: boolean; className?: string; size?: "sm" | "xs" }) {
  const sz = size === "xs" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-sm";
  return (
    <button onClick={onClick} disabled={disabled}
      className={`${sz} rounded border font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${BTN_CLS[variant]} ${className}`}>
      {children}
    </button>
  );
}

// ── Mono value ────────────────────────────────────────────────────────────────

export function Mono({ children, dim }: { children: ReactNode; dim?: boolean }) {
  return <span className={`font-mono text-xs ${dim ? "text-neutral-600" : "text-neutral-300"}`}>{children}</span>;
}

// ── Section divider ───────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="text-[10px] uppercase tracking-widest text-neutral-600 mb-2">{children}</div>;
}

// ── Completeness ring ─────────────────────────────────────────────────────────

export function CompletenessRing({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "text-emerald-400" : pct >= 50 ? "text-amber-400" : "text-red-400";
  return (
    <span className={`text-xs font-mono ${color}`} title={`${pct}% complete`}>{pct}%</span>
  );
}
