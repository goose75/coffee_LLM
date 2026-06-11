"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { getCoffees, type Coffee } from "@/lib/api";

const BREW_METHODS = [
  {
    id: "espresso",
    name: "Espresso",
    icon: "🎯",
    description:
      "High pressure extraction for rich, concentrated shots. Best for full-bodied, dark roasts.",
    water_temp: "90–96°C",
    grind: "Fine",
    ratio: "1:2 (e.g., 18g coffee → 36g espresso)",
    time: "25–30s",
    ideal_roasts: ["medium_dark", "dark"],
    tips: [
      "Use fresh beans (within 2-4 weeks of roasting)",
      "Tamp with consistent pressure (~30kg)",
      "Look for rich, golden crema",
      "Aim for balanced sweet and bitter notes",
    ],
    flavor_profile: "Bold, full-bodied, concentrated",
  },
  {
    id: "pour-over",
    name: "Pour Over",
    icon: "🫗",
    description:
      "Manual brewing that highlights clarity and origin characteristics. Perfect for single-origins.",
    water_temp: "92–96°C",
    grind: "Medium-fine",
    ratio: "1:16 (e.g., 20g coffee → 320g water)",
    time: "3–4 minutes",
    ideal_roasts: ["light", "medium_light", "medium"],
    tips: [
      "Use filtered water for best taste",
      "Bloom for 30-45s before pouring",
      "Pour slowly in circular motions",
      "Medium-fine grind prevents under-extraction",
    ],
    flavor_profile: "Clean, bright, nuanced",
  },
  {
    id: "french-press",
    name: "French Press",
    icon: "🫖",
    description:
      "Immersion brewing that creates full-bodied, rich coffee. Great for bold flavors.",
    water_temp: "92–96°C",
    grind: "Coarse",
    ratio: "1:15 (e.g., 30g coffee → 450g water)",
    time: "4 minutes",
    ideal_roasts: ["medium", "medium_dark", "dark"],
    tips: [
      "Use coarse grind to prevent over-extraction",
      "Pre-warm the pot with hot water",
      "Press slowly and steadily",
      "Pour immediately to avoid bitter notes",
    ],
    flavor_profile: "Full-bodied, rich, oils present",
  },
  {
    id: "aeropress",
    name: "AeroPress",
    icon: "💨",
    description:
      "Versatile, fast brewing combining immersion and pressure. Great travel companion.",
    water_temp: "85–92°C",
    grind: "Medium-fine",
    ratio: "1:16 (e.g., 17g coffee → 280g water)",
    time: "1–2 minutes",
    ideal_roasts: ["light", "medium", "medium_dark"],
    tips: [
      "Experiment with immersion or espresso-style brewing",
      "Lower temperature highlights origin notes",
      "Invert method for longer steeping",
      "Paper filters create clean cup",
    ],
    flavor_profile: "Clean, versatile, balanced",
  },
  {
    id: "moka-pot",
    name: "Moka Pot",
    icon: "⚡",
    description:
      "Stovetop brewing that creates concentrated coffee similar to espresso. Rich and strong.",
    water_temp: "Medium heat",
    grind: "Fine",
    ratio: "1:1 (e.g., fill bottom chamber with water)",
    time: "5–10 minutes",
    ideal_roasts: ["medium_dark", "dark"],
    tips: [
      "Use medium heat to prevent burning",
      "Fill water chamber just below safety valve",
      "Listen for hissing sound - remove immediately",
      "Works best with dark roasts",
    ],
    flavor_profile: "Strong, concentrated, bold",
  },
  {
    id: "cold-brew",
    name: "Cold Brew",
    icon: "🧊",
    description:
      "Long steeping in cold water creates smooth, less acidic coffee. Perfect for summer.",
    water_temp: "Room temperature",
    grind: "Coarse",
    ratio: "1:4 (e.g., 50g coffee → 200g water)",
    time: "12–24 hours",
    ideal_roasts: ["medium", "medium_dark"],
    tips: [
      "Use coarse grind for full immersion",
      "Stir occasionally for even extraction",
      "Strain through fine filter",
      "Concentrate keeps for 2 weeks",
    ],
    flavor_profile: "Smooth, sweet, low acid",
  },
];

function BrewMethodCard({
  method,
  recommendedCoffees,
}: {
  method: (typeof BREW_METHODS)[0];
  recommendedCoffees: Coffee[];
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-xl overflow-hidden border transition-all"
      style={{ borderColor: "var(--border-light)" }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-6 hover:bg-opacity-50 transition-colors text-left"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">{method.icon}</span>
              <h3
                className="text-2xl font-light"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {method.name}
              </h3>
            </div>
            <p
              className="text-sm leading-relaxed"
              style={{ color: "var(--text-muted)" }}
            >
              {method.description}
            </p>
          </div>

          {/* Expand indicator */}
          <div
            className="flex-shrink-0 transition-transform"
            style={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              color: "var(--text-muted)",
              fontSize: "14px",
            }}
          >
            ▼
          </div>
        </div>

        {/* Quick specs */}
        <div className="flex flex-wrap gap-3 mt-4">
          <div>
            <div
              className="text-xs uppercase tracking-wider font-semibold"
              style={{ color: "var(--text-faint)" }}
            >
              Water Temp
            </div>
            <div style={{ color: "var(--text)" }}>{method.water_temp}</div>
          </div>
          <div>
            <div
              className="text-xs uppercase tracking-wider font-semibold"
              style={{ color: "var(--text-faint)" }}
            >
              Time
            </div>
            <div style={{ color: "var(--text)" }}>{method.time}</div>
          </div>
          <div>
            <div
              className="text-xs uppercase tracking-wider font-semibold"
              style={{ color: "var(--text-faint)" }}
            >
              Grind
            </div>
            <div style={{ color: "var(--text)" }}>{method.grind}</div>
          </div>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div
          style={{
            borderTop: "1px solid var(--border-light)",
            backgroundColor: "var(--bg)",
          }}
        >
          {/* Details grid */}
          <div
            className="grid md:grid-cols-2 gap-6 p-6 border-b"
            style={{ borderColor: "var(--border-light)" }}
          >
            <div>
              <h4
                className="text-sm uppercase tracking-wider font-semibold mb-3"
                style={{ color: "var(--text-faint)" }}
              >
                Brewing Details
              </h4>
              <div className="space-y-3">
                <div>
                  <div style={{ color: "var(--text-faint)" }}>Ratio</div>
                  <div style={{ color: "var(--text)" }}>{method.ratio}</div>
                </div>
                <div>
                  <div style={{ color: "var(--text-faint)" }}>
                    Flavor Profile
                  </div>
                  <div style={{ color: "var(--text)" }}>
                    {method.flavor_profile}
                  </div>
                </div>
              </div>
            </div>

            <div>
              <h4
                className="text-sm uppercase tracking-wider font-semibold mb-3"
                style={{ color: "var(--text-faint)" }}
              >
                Ideal Roasts
              </h4>
              <div className="flex flex-wrap gap-2">
                {method.ideal_roasts.map((roast) => (
                  <span
                    key={roast}
                    className="text-xs px-3 py-1.5 rounded-full"
                    style={{
                      backgroundColor: "var(--bg-warm)",
                      color: "var(--text)",
                    }}
                  >
                    {roast.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Tips */}
          <div className="p-6 border-b" style={{ borderColor: "var(--border-light)" }}>
            <h4
              className="text-sm uppercase tracking-wider font-semibold mb-3"
              style={{ color: "var(--text-faint)" }}
            >
              Pro Tips
            </h4>
            <ul className="space-y-2">
              {method.tips.map((tip, i) => (
                <li key={i} className="flex gap-3">
                  <span
                    style={{ color: "var(--accent)", flexShrink: 0 }}
                  >
                    ✓
                  </span>
                  <span style={{ color: "var(--text)" }}>{tip}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Recommended coffees */}
          {recommendedCoffees.length > 0 && (
            <div className="p-6">
              <h4
                className="text-sm uppercase tracking-wider font-semibold mb-4"
                style={{ color: "var(--text-faint)" }}
              >
                Coffees for {method.name}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {recommendedCoffees.slice(0, 4).map((coffee) => (
                  <Link
                    key={coffee.id}
                    href={`/coffees/${coffee.id}`}
                    className="p-4 rounded-lg border transition-colors hover:bg-opacity-50"
                    style={{
                      borderColor: "var(--border-light)",
                      backgroundColor: "var(--surface)",
                    }}
                  >
                    <div
                      className="text-xs uppercase tracking-wider mb-1"
                      style={{ color: "var(--text-faint)" }}
                    >
                      {coffee.origin_country}
                    </div>
                    <h5
                      className="text-base font-medium mb-2"
                      style={{ fontFamily: "var(--font-display)" }}
                    >
                      {coffee.canonical_name}
                    </h5>
                    <div className="flex items-center gap-2 text-xs">
                      {coffee.min_price_gbp && (
                        <span style={{ color: "var(--accent)" }}>
                          £{coffee.min_price_gbp.toFixed(2)}
                        </span>
                      )}
                      {coffee.roast_level && (
                        <span style={{ color: "var(--text-muted)" }}>
                          {coffee.roast_level.replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BrewGuidesPage() {
  const [coffeesByRoast, setCoffeesByRoast] = useState<
    Record<string, Coffee[]>
  >({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCoffees = async () => {
      try {
        const roasts = [
          "light",
          "medium_light",
          "medium",
          "medium_dark",
          "dark",
        ];

        // Fetch all roasts in parallel (not sequentially)
        const roastPromises = roasts.map(async (roast) => {
          try {
            const result = await getCoffees({ roast, page_size: 50 });
            return { roast, coffees: result.data };
          } catch {
            return { roast, coffees: [] };
          }
        });

        const results = await Promise.all(roastPromises);
        const coffeeMap = Object.fromEntries(results.map(r => [r.roast, r.coffees]));
        setCoffeesByRoast(coffeeMap);
      } finally {
        setLoading(false);
      }
    };

    loadCoffees();
  }, []);

  const getRecommendedCoffees = (roasts: string[]): Coffee[] => {
    const recommended: Coffee[] = [];
    for (const roast of roasts) {
      recommended.push(...(coffeesByRoast[roast] || []).slice(0, 2));
    }
    return recommended.slice(0, 6);
  };

  return (
    <div className="px-4 py-12">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1
            className="text-5xl font-light mb-4 leading-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Brewing Guides
          </h1>
          <p style={{ color: "var(--text-muted)", maxWidth: "600px" }}>
            Master different brewing methods with detailed guides for each
            technique. Learn optimal temperatures, ratios, and pro tips to get
            the best from your coffee.
          </p>
        </div>

        {/* Content */}
        {loading ? (
          <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
            Loading brewing guides...
          </div>
        ) : (
          <div className="space-y-6">
            {BREW_METHODS.map((method) => (
              <BrewMethodCard
                key={method.id}
                method={method}
                recommendedCoffees={getRecommendedCoffees(
                  method.ideal_roasts
                )}
              />
            ))}
          </div>
        )}

        {/* Footer */}
        <div
          className="mt-16 pt-12"
          style={{
            borderTop: "1px solid var(--border-light)",
          }}
        >
          <h2
            className="text-2xl font-light mb-4"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Finding Your Perfect Brew
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div>
              <h3
                className="font-semibold mb-2"
                style={{ color: "var(--text)" }}
              >
                Start Simple
              </h3>
              <p style={{ color: "var(--text-muted)" }}>
                Begin with pour over or French press. They require minimal
                equipment and are forgiving to learn.
              </p>
            </div>
            <div>
              <h3
                className="font-semibold mb-2"
                style={{ color: "var(--text)" }}
              >
                Quality Water Matters
              </h3>
              <p style={{ color: "var(--text-muted)" }}>
                Good water is 98% of coffee. Use filtered water and aim for
                slightly cooler temperatures initially.
              </p>
            </div>
            <div>
              <h3
                className="font-semibold mb-2"
                style={{ color: "var(--text)" }}
              >
                Grind Fresh
              </h3>
              <p style={{ color: "var(--text-muted)" }}>
                Grind just before brewing. Even 15 minutes of oxidation affects
                taste significantly.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
