import Link from "next/link";
import CoffeeCard from "@/components/CoffeeCard";
import { getCoffees, getNewReleases, getRoasters } from "@/lib/api";
import type { Coffee, Roaster } from "@/lib/api";

// Server component — data fetched at request time with 5-min ISR
async function fetchHomeData() {
  try {
    const [featured, newReleases, roasterData] = await Promise.allSettled([
      getCoffees({ page: 1, page_size: 6, sort: "data_completeness_score" }),
      getNewReleases({ days: 14, page: 1, page_size: 8 }),
      getRoasters({ page: 1, page_size: 4 }),
    ]);
    return {
      featured:     featured.status     === "fulfilled" ? featured.value.data    : [] as Coffee[],
      newReleases:  newReleases.status  === "fulfilled" ? newReleases.value.data : [] as Coffee[],
      roasters:     roasterData.status  === "fulfilled" ? roasterData.value.data : [] as Roaster[],
      roasterTotal: roasterData.status  === "fulfilled" ? roasterData.value.total : 0,
    };
  } catch {
    return { featured: [] as Coffee[], newReleases: [] as Coffee[], roasters: [] as Roaster[], roasterTotal: 0 };
  }
}

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c", natural: "#c4763a", honey: "#d4a03a",
  anaerobic: "#8b6bab", wet_hulled: "#5a7fa8", carbonic_maceration: "#a85a7f",
};

export default async function HomePage() {
  const { featured, newReleases, roasters, roasterTotal } = await fetchHomeData();

  return (
    <div style={{ backgroundColor: "var(--bg)" }}>

      {/* ── Hero strip ──────────────────────────────────────────────────── */}
      <section className="px-4 pt-4 pb-6">
        <div className="flex items-end justify-between mb-1">
          <div>
            <span className="text-[11px] uppercase tracking-[0.2em]" style={{ color: "var(--accent)" }}>
              UK Specialty Coffee
            </span>
            <h1
              className="text-3xl font-light leading-tight mt-0.5"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Every bean,<br />
              <em style={{ color: "var(--accent)" }}>every roaster.</em>
            </h1>
          </div>
          <div className="text-right flex-shrink-0 ml-4">
            <div className="text-2xl font-light" style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}>
              {roasterTotal || "200"}+
            </div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>roasters</div>
          </div>
        </div>

        {/* Quick action pills */}
        <div className="flex gap-2 mt-4 overflow-x-auto pb-1 -mx-4 px-4">
          {[
            { href: "/coffees", label: "Browse all" },
            { href: "/new-releases", label: "✦ New releases" },
            { href: "/coffees?process=natural", label: "Naturals" },
            { href: "/coffees?process=washed", label: "Washed" },
            { href: "/coffees?roast_level=light", label: "Light roast" },
          ].map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="flex-shrink-0 px-4 py-2 rounded-full text-[13px] font-medium press-active"
              style={{
                backgroundColor: label.includes("Browse") ? "var(--accent)" : "var(--surface)",
                color: label.includes("Browse") ? "#fff" : "var(--text-muted)",
                border: "1px solid var(--border)",
              }}
            >
              {label}
            </Link>
          ))}
        </div>
      </section>

      {/* ── New releases feed ───────────────────────────────────────────── */}
      {newReleases.length > 0 && (
        <section className="mb-8">
          <div className="flex items-center justify-between px-4 mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest mb-0.5" style={{ color: "var(--text-faint)" }}>Just landed</div>
              <h2 className="text-xl font-light" style={{ fontFamily: "var(--font-display)" }}>New releases</h2>
            </div>
            <Link href="/new-releases" className="text-xs font-medium press-active" style={{ color: "var(--accent)" }}>
              See all →
            </Link>
          </div>

          <div className="overflow-x-auto pb-2 -mx-4 px-4">
            <div className="flex gap-3" style={{ width: "max-content" }}>
              {newReleases.slice(0, 6).map((coffee) => {
                const processColor = PROCESS_COLORS[coffee.process ?? ""] ?? "var(--border)";
                return (
                  <Link
                    key={coffee.id}
                    href={`/coffees/${coffee.id}`}
                    className="press-active"
                    style={{ width: 160, flexShrink: 0 }}
                  >
                    <div
                      className="rounded-2xl overflow-hidden h-full"
                      style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}
                    >
                      <div className="h-1" style={{ backgroundColor: processColor }} />
                      <div className="p-3.5">
                        <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-faint)" }}>
                          {coffee.origin_country}
                        </div>
                        <div
                          className="text-sm font-medium leading-snug mb-2"
                          style={{ fontFamily: "var(--font-display)", fontSize: "0.95rem", color: "var(--text)" }}
                        >
                          {coffee.canonical_name}
                        </div>
                        {coffee.flavour_notes.slice(0, 2).map(n => (
                          <span
                            key={n}
                            className="inline-block mr-1 mb-1 text-[10px] px-1.5 py-0.5 rounded-full capitalize"
                            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}
                          >
                            {n}
                          </span>
                        ))}
                        {coffee.min_price_gbp != null && (
                          <div className="mt-2 text-xs font-medium" style={{ color: "var(--accent)" }}>
                            from £{coffee.min_price_gbp.toFixed(2)}
                          </div>
                        )}
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── Featured grid ──────────────────────────────────────────────── */}
      {featured.length > 0 && (
        <section className="px-4 mb-8">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest mb-0.5" style={{ color: "var(--text-faint)" }}>Editor's picks</div>
              <h2 className="text-xl font-light" style={{ fontFamily: "var(--font-display)" }}>Worth drinking now</h2>
            </div>
            <Link href="/coffees" className="text-xs font-medium press-active" style={{ color: "var(--accent)" }}>
              Browse all →
            </Link>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {featured.slice(0, 4).map(c => <CoffeeCard key={c.id} coffee={c} />)}
          </div>
        </section>
      )}

      {/* ── Roasters strip ─────────────────────────────────────────────── */}
      {roasters.length > 0 && (
        <section className="px-4 mb-8">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest mb-0.5" style={{ color: "var(--text-faint)" }}>Directory</div>
              <h2 className="text-xl font-light" style={{ fontFamily: "var(--font-display)" }}>UK Roasters</h2>
            </div>
            <Link href="/roasters" className="text-xs font-medium press-active" style={{ color: "var(--accent)" }}>
              All {roasterTotal}+ →
            </Link>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {roasters.map(r => (
              <a
                key={r.id}
                href={`//${r.domain}`}
                target="_blank"
                rel="noopener"
                className="p-3.5 rounded-2xl flex items-center gap-3 press-active"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
                  style={{ backgroundColor: "var(--bg-warm)", color: "var(--accent)" }}
                >
                  {r.name.charAt(0)}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>{r.name}</div>
                  {r.uk_region && (
                    <div className="text-[11px] truncate" style={{ color: "var(--text-faint)" }}>{r.uk_region}</div>
                  )}
                </div>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* ── About strip ────────────────────────────────────────────────── */}
      <section className="px-4 mb-8">
        <div
          className="rounded-2xl p-5"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border-light)" }}
        >
          <div className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--text-faint)" }}>About</div>
          <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-muted)" }}>
            Grounds tracks specialty coffees across UK roasters — prices, provenance, and new releases — updated daily from ~200 sources.
          </p>
          <Link
            href="/methodology"
            className="text-xs font-medium press-active"
            style={{ color: "var(--accent)" }}
          >
            How it works →
          </Link>
        </div>
      </section>

    </div>
  );
}
