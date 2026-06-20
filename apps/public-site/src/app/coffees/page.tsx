"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import CoffeeCard from "@/components/CoffeeCard";
import { getCoffees, getMarketAverages } from "@/lib/api";
import type { Coffee, MarketAverages } from "@/lib/api";

const PROCESSES = ["washed", "natural", "honey", "anaerobic", "wet_hulled", "carbonic_maceration"];
const ROASTS    = ["light", "medium_light", "medium", "medium_dark", "dark"];
const ORIGINS   = ["Ethiopia", "Kenya", "Colombia", "Brazil", "Guatemala", "Rwanda", "Panama", "Costa Rica", "Honduras", "El Salvador", "Peru", "Burundi"];
const FLAVOURS  = ["jasmine", "bergamot", "lemon", "blackcurrant", "chocolate", "caramel", "tropical fruit", "cherry", "floral", "citrus", "brown sugar", "honey"];
const PRICE_BANDS = [
  { label: "Under £10", min: 0, max: 10 },
  { label: "£10–£15",   min: 10, max: 15 },
  { label: "£15–£20",   min: 15, max: 20 },
  { label: "£20+",      min: 20, max: 999 },
];

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="text-xs px-3 py-1.5 rounded-full border transition-all whitespace-nowrap"
      style={{
        backgroundColor: active ? "var(--accent)" : "transparent",
        borderColor: active ? "var(--accent)" : "var(--border)",
        color: active ? "#fff" : "var(--text-muted)",
      }}>
      {label.replace(/_/g, " ")}
    </button>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] uppercase tracking-widest mb-2.5 font-medium" style={{ color: "var(--text-faint)" }}>{title}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl p-5 animate-pulse" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
      <div className="h-3 w-16 rounded mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-5 w-3/4 rounded mb-2" style={{ backgroundColor: "var(--border)" }} />
      <div className="h-3 w-1/2 rounded mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="flex gap-1.5 mb-4">{[40,55,45].map(w => <div key={w} className="h-5 rounded-full" style={{ width: w, backgroundColor: "var(--border)" }} />)}</div>
      <div className="h-px mb-4" style={{ backgroundColor: "var(--border)" }} />
      <div className="flex justify-between">
        <div className="h-4 w-20 rounded" style={{ backgroundColor: "var(--border)" }} />
        <div className="h-4 w-12 rounded" style={{ backgroundColor: "var(--border)" }} />
      </div>
    </div>
  );
}

export default function BrowsePage() {
  const searchParams = useSearchParams();
  const [q, setQ]                       = useState("");
  const [debouncedQ, setDebouncedQ]     = useState("");
  const [selectedProcess, setSelectedProcess] = useState<string[]>([]);
  const [selectedRoast, setSelectedRoast]     = useState<string[]>([]);
  const [selectedOrigin, setSelectedOrigin]   = useState<string[]>([]);
  const [selectedFlavour, setSelectedFlavour] = useState<string[]>([]);
  const [selectedPrice, setSelectedPrice]     = useState<number | null>(null);
  const [layout, setLayout]             = useState<"grid" | "list">("grid");
  const [sidebarOpen, setSidebarOpen]   = useState(false);
  const [coffees, setCoffees]           = useState<Coffee[]>([]);
  const [total, setTotal]               = useState(0);
  const [page, setPage]                 = useState(1);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [marketMedian, setMarketMedian] = useState<number | null>(null);
  const [roasterDomain, setRoasterDomain] = useState<string | null>(null);

  // Initialize filters from URL params
  useEffect(() => {
    const domain = searchParams.get("roaster_domain");
    console.log("URL roaster_domain:", domain);
    if (domain) {
      setRoasterDomain(domain);
      console.log("Set roasterDomain to:", domain);
    }
  }, [searchParams]);

  // Debounce
  useEffect(() => {
    getMarketAverages().then(d => setMarketMedian(d.median_per_100g_gbp)).catch(() => {});
  }, []);

  useEffect(() => { const t = setTimeout(() => setDebouncedQ(q), 350); return () => clearTimeout(t); }, [q]);
  // Reset page on filter change
  useEffect(() => { setPage(1); }, [debouncedQ, selectedProcess, selectedRoast, selectedOrigin, selectedFlavour, selectedPrice, roasterDomain]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params: Record<string, string | number | undefined> = { page, page_size: 24 };
      if (debouncedQ)           params.q = debouncedQ;
      if (selectedProcess.length) params.process = selectedProcess.join(",");
      if (selectedRoast.length)   params.roast_level = selectedRoast.join(",");
      if (selectedOrigin.length)  params.origin_country = selectedOrigin.join(",");
      if (selectedFlavour.length) params.flavour = selectedFlavour.join(",");
      if (roasterDomain)          params.store_domain = roasterDomain;
      if (selectedPrice !== null) {
        const band = PRICE_BANDS[selectedPrice];
        params.min_price = band.min;
        if (band.max !== 999) params.max_price = band.max;
      }
      console.log("Loading coffees with params:", params);
      const data = await getCoffees(params);
      console.log("Got data with total:", data.total);
      setCoffees(data.data); setTotal(data.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [page, debouncedQ, selectedProcess, selectedRoast, selectedOrigin, selectedFlavour, selectedPrice, roasterDomain]);

  useEffect(() => { load(); }, [load]);

  const toggle = (arr: string[], set: (a: string[]) => void, val: string) =>
    set(arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);

  const activeCount = selectedProcess.length + selectedRoast.length + selectedOrigin.length + selectedFlavour.length + (selectedPrice !== null ? 1 : 0) + (roasterDomain ? 1 : 0);
  const clearAll = () => { setSelectedProcess([]); setSelectedRoast([]); setSelectedOrigin([]); setSelectedFlavour([]); setSelectedPrice(null); setQ(""); setRoasterDomain(null); };
  const totalPages = Math.ceil(total / 24);

  const FilterPanel = (
    <div>
      <FilterSection title="Process">
        {PROCESSES.map(p => <FilterChip key={p} label={p} active={selectedProcess.includes(p)} onClick={() => toggle(selectedProcess, setSelectedProcess, p)} />)}
      </FilterSection>
      <FilterSection title="Roast">
        {ROASTS.map(r => <FilterChip key={r} label={r.replace(/_/g, "-")} active={selectedRoast.includes(r)} onClick={() => toggle(selectedRoast, setSelectedRoast, r)} />)}
      </FilterSection>
      <FilterSection title="Origin">
        {ORIGINS.map(o => <FilterChip key={o} label={o} active={selectedOrigin.includes(o)} onClick={() => toggle(selectedOrigin, setSelectedOrigin, o)} />)}
      </FilterSection>
      <FilterSection title="Tasting notes">
        {FLAVOURS.map(f => <FilterChip key={f} label={f} active={selectedFlavour.includes(f)} onClick={() => toggle(selectedFlavour, setSelectedFlavour, f)} />)}
      </FilterSection>
      <FilterSection title="Price (250g)">
        {PRICE_BANDS.map((b, i) => <FilterChip key={b.label} label={b.label} active={selectedPrice === i} onClick={() => setSelectedPrice(selectedPrice === i ? null : i)} />)}
      </FilterSection>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-4">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--text-faint)" }}>Discovery</div>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <h1 className="text-4xl font-light" style={{ fontFamily: "var(--font-display)" }}>Browse coffees</h1>
          <div className="flex items-center gap-3">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: "var(--text-faint)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search coffees…"
                className="pl-8 pr-4 py-2 text-sm rounded-full w-52 focus:outline-none"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }} />
            </div>
            <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
              {(["grid", "list"] as const).map(l => (
                <button key={l} onClick={() => setLayout(l)} className="px-3 py-2 text-xs transition-colors"
                  style={{ backgroundColor: layout === l ? "var(--accent)" : "transparent", color: layout === l ? "#fff" : "var(--text-muted)" }}>
                  {l === "grid" ? "⊞" : "☰"}
                </button>
              ))}
            </div>
            <button onClick={() => setSidebarOpen(true)} className="md:hidden flex items-center gap-2 px-3 py-2 rounded-full text-xs"
              style={{ backgroundColor: activeCount > 0 ? "var(--accent)" : "var(--surface)", color: activeCount > 0 ? "#fff" : "var(--text-muted)", border: "1px solid var(--border)" }}>
              Filters {activeCount > 0 && `(${activeCount})`}
            </button>
          </div>
        </div>
      </div>

      <div className="flex gap-8">
        <aside className="hidden md:block w-56 flex-shrink-0 sticky top-20 self-start">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--text-faint)" }}>Filters</span>
            {activeCount > 0 && <button onClick={clearAll} className="text-xs hover:opacity-70" style={{ color: "var(--accent)" }}>Clear {activeCount}</button>}
          </div>
          {FilterPanel}
        </aside>

        {sidebarOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
            <div className="absolute right-0 top-0 bottom-0 w-72 overflow-y-auto p-6" style={{ backgroundColor: "var(--bg)" }}>
              <div className="flex items-center justify-between mb-6">
                <span className="font-medium" style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem" }}>Filters</span>
                <button onClick={() => setSidebarOpen(false)} style={{ color: "var(--text-muted)" }}>✕</button>
              </div>
              {FilterPanel}
              <button onClick={() => setSidebarOpen(false)} className="w-full mt-4 py-3 rounded-full text-sm font-medium" style={{ backgroundColor: "var(--accent)", color: "#fff" }}>
                Show results
              </button>
            </div>
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-5">
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>
              {loading ? "Loading…" : `${total.toLocaleString()} coffees`}
            </span>
          </div>

          {error && (
            <div className="py-6 text-center rounded-2xl mb-6" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Couldn't reach the API</p>
              <button onClick={load} className="text-xs px-4 py-2 rounded-full" style={{ backgroundColor: "var(--accent)", color: "#fff" }}>Retry</button>
            </div>
          )}

          {loading ? (
            <div className={layout === "grid" ? "grid sm:grid-cols-2 lg:grid-cols-3 gap-4" : "space-y-3"}>
              {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : coffees.length === 0 && !error ? (
            <div className="py-20 text-center">
              <div className="text-3xl mb-3" style={{ fontFamily: "var(--font-display)" }}>No matches</div>
              <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Try removing some filters</p>
              <button onClick={clearAll} className="text-sm" style={{ color: "var(--accent)" }}>Clear all filters</button>
            </div>
          ) : layout === "grid" ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {coffees.map(c => <CoffeeCard key={c.id} coffee={c} marketMedianPer100g={marketMedian} />)}
            </div>
          ) : (
            <div>{coffees.map(c => <CoffeeCard key={c.id} coffee={c} layout="list" marketMedianPer100g={marketMedian} />)}</div>
          )}

          {totalPages > 1 && !loading && (
            <div className="mt-10 flex items-center justify-center gap-2">
              <button onClick={() => setPage(p => p - 1)} disabled={page <= 1}
                className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>← Prev</button>
              <span className="px-3 text-sm" style={{ color: "var(--text-muted)" }}>{page} / {totalPages}</span>
              <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
                className="px-4 py-2 text-sm rounded-full disabled:opacity-30"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>Next →</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
