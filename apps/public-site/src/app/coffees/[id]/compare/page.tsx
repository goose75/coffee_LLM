import Link from "next/link";
import { getCoffee, getPriceStats, type Coffee, type PriceSummaryStats } from "@/lib/api";

export async function generateMetadata({ params }: { params: { id: string } }) {
  try {
    const c = await getCoffee(params.id);
    return { title: `Compare prices — ${c.canonical_name}` };
  } catch {
    return { title: "Compare prices" };
  }
}

const GRIND_LABELS: Record<string, string> = {
  whole_bean: "Whole bean", espresso: "Espresso", filter: "Filter",
  cafetiere: "Cafetière", aeropress: "Aeropress", pour_over: "Pour over",
  omni: "Omni-grind", unknown: "—",
};

function ValueBar({ value, max }: { value: number; max: number }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ backgroundColor: "var(--border)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: "var(--accent)" }} />
      </div>
    </div>
  );
}

export default async function ComparePage({ params }: { params: { id: string } }) {
  let coffee: Coffee | null = null;
  let stats: PriceSummaryStats[] = [];

  try {
    [coffee, stats] = await Promise.all([
      getCoffee(params.id),
      getPriceStats(params.id),
    ]);
  } catch {
    return (
      <div className="px-4 py-16 text-center">
        <div className="text-3xl mb-3" style={{ fontFamily: "var(--font-display)" }}>Not found</div>
        <Link href="/coffees" style={{ color: "var(--accent)" }} className="text-sm">← Browse coffees</Link>
      </div>
    );
  }

  if (!coffee) return null;

  // Flatten all listings/variants into comparable rows
  const rows: Array<{
    store: string;
    domain: string;
    url: string | null;
    weight_g: number | null;
    grind: string;
    price: number;
    per100g: number | null;
    available: boolean;
  }> = [];

  for (const listing of coffee.listings ?? []) {
    for (const v of listing.variants ?? []) {
      rows.push({
        store: listing.store_name,
        domain: listing.store_domain,
        url: listing.product_url ?? null,
        weight_g: v.weight_g ?? null,
        grind: v.grind_type ?? "unknown",
        price: Number(v.price_gbp),
        per100g: v.price_per_100g_gbp ? Number(v.price_per_100g_gbp) : null,
        available: v.availability_status === "in_stock",
      });
    }
  }

  // Sort by per-100g price ascending (best value first), unavailable last
  rows.sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    const ap = a.per100g ?? 9999;
    const bp = b.per100g ?? 9999;
    return ap - bp;
  });

  const maxPer100 = Math.max(...rows.map(r => r.per100g ?? 0), 1);
  const bestPrice = rows.find(r => r.available)?.price;
  const bestPer100 = rows.find(r => r.available && r.per100g)?.per100g;

  // Group by weight tier
  const weights = [...new Set(rows.map(r => r.weight_g).filter(Boolean))].sort((a, b) => (a ?? 0) - (b ?? 0));

  return (
    <div style={{ backgroundColor: "var(--bg)" }}>
      {/* Header */}
      <div className="px-4 pt-5 pb-4" style={{ borderBottom: "1px solid var(--border-light)" }}>
        <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--text-faint)" }}>
          Price comparison
        </div>
        <h1 className="text-2xl font-light leading-tight" style={{ fontFamily: "var(--font-display)" }}>
          {coffee.canonical_name}
        </h1>
        <div className="flex gap-4 mt-3">
          {bestPrice != null && (
            <div>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Best price</div>
              <div className="text-xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                £{bestPrice.toFixed(2)}
              </div>
            </div>
          )}
          {bestPer100 != null && (
            <div>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Best per 100g</div>
              <div className="text-xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                £{bestPer100.toFixed(2)}
              </div>
            </div>
          )}
          <div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Stores</div>
            <div className="text-xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--text)" }}>
              {new Set(rows.map(r => r.store)).size}
            </div>
          </div>
        </div>
      </div>

      {/* Weight tier filter tabs */}
      {weights.length > 1 && (
        <div className="flex gap-2 px-4 py-3 overflow-x-auto" style={{ borderBottom: "1px solid var(--border-light)" }}>
          <span className="text-[11px] self-center" style={{ color: "var(--text-faint)" }}>Weight:</span>
          {weights.map(w => (
            <span key={w} className="flex-shrink-0 px-3 py-1 rounded-full text-xs"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
              {w && w >= 1000 ? `${w / 1000}kg` : `${w}g`}
            </span>
          ))}
        </div>
      )}

      {/* Comparison rows */}
      <div className="px-4 py-4 space-y-3">
        {rows.length === 0 ? (
          <div className="py-12 text-center">
            <div className="text-3xl mb-3">🏪</div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No store listings found for this coffee.</p>
          </div>
        ) : (
          rows.map((row, i) => (
            <div key={i}
              className="rounded-2xl overflow-hidden"
              style={{
                backgroundColor: "var(--surface)",
                border: `1px solid ${i === 0 && row.available ? "var(--accent)" : "var(--border-light)"}`,
                opacity: row.available ? 1 : 0.55,
              }}>
              {i === 0 && row.available && (
                <div className="px-4 py-1.5 text-[10px] uppercase tracking-widest font-medium"
                  style={{ backgroundColor: "var(--accent)", color: "#fff" }}>
                  Best value
                </div>
              )}
              <div className="p-4">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <div className="text-sm font-medium" style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}>
                      {row.store}
                    </div>
                    <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>
                      {row.domain}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
                      £{row.price.toFixed(2)}
                    </div>
                    {row.weight_g && (
                      <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>
                        {row.weight_g >= 1000 ? `${row.weight_g / 1000}kg` : `${row.weight_g}g`}
                      </div>
                    )}
                  </div>
                </div>

                {row.per100g != null && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between text-[10px] mb-1" style={{ color: "var(--text-faint)" }}>
                      <span>£{row.per100g.toFixed(2)} / 100g</span>
                      <span>{row.available ? "In stock" : "Out of stock"}</span>
                    </div>
                    <ValueBar value={row.per100g} max={maxPer100} />
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-[11px] px-2 py-0.5 rounded-full capitalize"
                    style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}>
                    {GRIND_LABELS[row.grind] ?? row.grind}
                  </span>
                  {row.url && row.available && (
                    <a href={row.url} target="_blank" rel="noopener"
                      className="text-[11px] px-3 py-1.5 rounded-full press-active"
                      style={{ border: "1px solid var(--accent)", color: "var(--accent)" }}>
                      Buy ↗
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Stat summary */}
      {stats.length > 0 && (
        <div className="px-4 pb-8">
          <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: "var(--text-faint)" }}>
            Market summary
          </div>
          <div className="space-y-2">
            {stats.map(s => (
              <div key={s.weight_g} className="flex items-center justify-between p-3 rounded-xl"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}>
                <span className="text-sm" style={{ color: "var(--text-muted)" }}>
                  {s.weight_g ? (s.weight_g >= 1000 ? `${s.weight_g / 1000}kg` : `${s.weight_g}g`) : "All sizes"}
                </span>
                <div className="flex items-center gap-4 text-sm">
                  <span style={{ color: "var(--text-faint)" }}>
                    Low £{s.min_price_gbp?.toFixed(2) ?? "—"}
                  </span>
                  <span style={{ color: "var(--text-faint)" }}>
                    Med £{s.median_price_gbp?.toFixed(2) ?? "—"}
                  </span>
                  <span style={{ color: "var(--text-faint)" }}>
                    High £{s.max_price_gbp?.toFixed(2) ?? "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Back link */}
      <div className="px-4 pb-8">
        <Link href={`/coffees/${params.id}`} className="text-sm press-active"
          style={{ color: "var(--accent)" }}>
          ← Back to {coffee.canonical_name}
        </Link>
      </div>
    </div>
  );
}
