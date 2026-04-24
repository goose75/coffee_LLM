import Link from "next/link";
import type { Coffee } from "@/lib/api";

const PROCESS_COLORS: Record<string, string> = {
  washed: "#6b9e8c",
  natural: "#c4763a",
  honey: "#d4a03a",
  anaerobic: "#8b6bab",
  wet_hulled: "#5a7fa8",
  carbonic_maceration: "#a85a7f",
  experimental: "#7f7f7f",
};

function ProcessDot({ process }: { process: string | null }) {
  if (!process) return null;
  const color = PROCESS_COLORS[process] ?? "#9a9080";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <span className="capitalize text-xs" style={{ color: "var(--text-faint)" }}>
        {process.replace("_", " ")}
      </span>
    </span>
  );
}

function RoastBar({ level }: { level: string | null }) {
  const levels = ["light", "medium_light", "medium", "medium_dark", "dark"];
  const idx = level ? levels.indexOf(level) : -1;
  return (
    <div className="flex items-center gap-1">
      {levels.map((l, i) => (
        <div
          key={l}
          className="h-1 flex-1 rounded-full transition-colors"
          style={{ backgroundColor: i <= idx ? "var(--accent)" : "var(--border)" }}
        />
      ))}
    </div>
  );
}

interface CoffeeCardProps {
  coffee: Coffee;
  layout?: "grid" | "list";
}

export default function CoffeeCard({ coffee, layout = "grid" }: CoffeeCardProps) {
  const flagUrl = coffee.origin_country
    ? `https://flagcdn.com/24x18/${getCountryCode(coffee.origin_country)}.png`
    : null;

  if (layout === "list") {
    return (
      <Link href={`/coffees/${coffee.id}`} className="group block">
        <div
          className="flex items-center gap-5 py-4 border-b transition-colors group-hover:bg-surface-raised -mx-4 px-4 rounded"
          style={{ borderColor: "var(--border-light)" }}
        >
          <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-lg"
            style={{ backgroundColor: "var(--bg-warm)" }}>
            {flagUrl ? <img src={flagUrl} alt="" className="w-6 h-4 object-cover rounded" /> : "☕"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm truncate" style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}>
              {coffee.canonical_name}
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              <ProcessDot process={coffee.process} />
              {coffee.origin_region && <span className="text-xs" style={{ color: "var(--text-faint)" }}>{coffee.origin_region}</span>}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            {coffee.min_price_gbp != null && (
              <div className="text-sm font-medium" style={{ color: "var(--text)" }}>
                from £{coffee.min_price_gbp.toFixed(2)}
              </div>
            )}
            <div className="text-xs" style={{ color: "var(--text-faint)" }}>{coffee.store_count ?? 0} stores</div>
          </div>
        </div>
      </Link>
    );
  }

  return (
    <Link href={`/coffees/${coffee.id}`} className="group block">
      <article
        className="h-full rounded-2xl overflow-hidden transition-all duration-300 group-hover:-translate-y-0.5"
        style={{
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border-light)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        {/* Top colour strip by process */}
        <div className="h-1 w-full" style={{
          backgroundColor: PROCESS_COLORS[coffee.process ?? ""] ?? "var(--border)"
        }} />

        <div className="p-5">
          {/* Origin flag + location */}
          <div className="flex items-center gap-2 mb-3">
            {flagUrl && <img src={flagUrl} alt="" className="w-5 h-3.5 object-cover rounded-sm" />}
            <span className="text-xs tracking-wide uppercase" style={{ color: "var(--text-faint)" }}>
              {[coffee.origin_country, coffee.origin_region].filter(Boolean).join(" · ")}
            </span>
          </div>

          {/* Name */}
          <h3
            className="leading-snug mb-2 group-hover:opacity-80 transition-opacity"
            style={{ fontFamily: "var(--font-display)", fontSize: "1.125rem", fontWeight: 500 }}
          >
            {coffee.canonical_name}
          </h3>

          {/* Farm */}
          {coffee.farm_or_estate && (
            <p className="text-xs mb-3 truncate" style={{ color: "var(--text-faint)" }}>
              {coffee.farm_or_estate}
            </p>
          )}

          {/* Flavour notes */}
          {coffee.flavour_notes.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {coffee.flavour_notes.slice(0, 3).map((note) => (
                <span
                  key={note}
                  className="text-[11px] px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-muted)" }}
                >
                  {note}
                </span>
              ))}
            </div>
          )}

          {/* Process + roast */}
          <div className="flex items-center justify-between mb-3">
            <ProcessDot process={coffee.process} />
            {coffee.harvest_year && (
              <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
                {coffee.harvest_year}
              </span>
            )}
          </div>

          <RoastBar level={coffee.roast_level} />

          {/* Price + stores */}
          <div className="flex items-center justify-between mt-4 pt-4" style={{ borderTop: "1px solid var(--border-light)" }}>
            <div>
              {coffee.min_price_gbp != null ? (
                <span className="text-sm font-medium" style={{ color: "var(--accent)" }}>
                  from £{coffee.min_price_gbp.toFixed(2)}
                </span>
              ) : (
                <span className="text-xs" style={{ color: "var(--text-faint)" }}>Price unavailable</span>
              )}
            </div>
            <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
              {coffee.store_count ?? 0} {(coffee.store_count ?? 0) === 1 ? "store" : "stores"}
            </span>
          </div>
        </div>
      </article>
    </Link>
  );
}

function getCountryCode(country: string): string {
  const map: Record<string, string> = {
    "Ethiopia": "et", "Kenya": "ke", "Colombia": "co", "Brazil": "br",
    "Guatemala": "gt", "Costa Rica": "cr", "Honduras": "hn", "El Salvador": "sv",
    "Nicaragua": "ni", "Panama": "pa", "Peru": "pe", "Bolivia": "bo",
    "Rwanda": "rw", "Burundi": "bi", "Uganda": "ug", "Tanzania": "tz",
    "Indonesia": "id", "India": "in", "Yemen": "ye", "Vietnam": "vn",
    "Papua New Guinea": "pg", "Malawi": "mw", "Zambia": "zm",
  };
  return map[country] ?? "xx";
}
