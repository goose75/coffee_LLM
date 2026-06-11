"use client";

import Link from "next/link";
import { useState, useEffect, useMemo } from "react";
import { getCoffees, type Coffee } from "@/lib/api";
import CoffeeCard from "@/components/CoffeeCard";

const ORIGIN_PROFILES: Record<
  string,
  {
    description: string;
    flavor_profile: string[];
    altitude_range: string;
    emoji: string;
    notable_regions: string[];
  }
> = {
  Ethiopia: {
    description:
      "The birthplace of coffee. Known for tea-like, floral, and fruity notes with bright acidity.",
    flavor_profile: ["floral", "fruity", "tea-like", "bright"],
    altitude_range: "1,400–2,200m",
    emoji: "🌍",
    notable_regions: ["Yirgacheffe", "Sidamo", "Harrar", "Guji", "Jimma"],
  },
  Kenya: {
    description:
      "Bold, wine-like flavors with black currant and stone fruit notes. High altitude, high quality.",
    flavor_profile: ["wine-like", "berry", "stone fruit", "bold"],
    altitude_range: "1,600–2,100m",
    emoji: "🦁",
    notable_regions: ["Nyeri", "Kirinyaga", "Embu", "Machakos", "Rift Valley"],
  },
  Colombia: {
    description:
      "Balanced, sweet coffees with chocolate, nuts, and caramel. The world's most consistent producer.",
    flavor_profile: ["chocolate", "nutty", "caramel", "balanced"],
    altitude_range: "1,200–2,200m",
    emoji: "🏔️",
    notable_regions: [
      "Huila",
      "Nariño",
      "Cauca",
      "Tolima",
      "Antioquia",
    ],
  },
  Brazil: {
    description:
      "Smooth, full-bodied with chocolate, nutty, and sweet flavors. The largest coffee producer.",
    flavor_profile: ["smooth", "nutty", "sweet", "chocolate"],
    altitude_range: "800–1,200m",
    emoji: "🌳",
    notable_regions: [
      "Minas Gerais",
      "São Paulo",
      "Espírito Santo",
      "Bahia",
    ],
  },
  Guatemala: {
    description:
      "Complex, spicy coffees with chocolate and earthy notes. Volcanic soils add depth.",
    flavor_profile: ["spicy", "earthy", "chocolate", "complex"],
    altitude_range: "1,500–2,000m",
    emoji: "🌋",
    notable_regions: ["Huehuetenango", "Atitlán", "Antigua", "Coban"],
  },
  Rwanda: {
    description:
      "Bright, fruity coffees with floral notes. Rapidly growing specialty producer.",
    flavor_profile: ["fruity", "floral", "bright", "clean"],
    altitude_range: "1,400–2,000m",
    emoji: "🍓",
    notable_regions: ["Maraba", "Caplaki", "Gakenke", "Karongi"],
  },
  Peru: {
    description:
      "Well-balanced, earthy coffees with cocoa and spice notes. Often organic and fair trade.",
    flavor_profile: ["earthy", "cocoa", "spice", "clean"],
    altitude_range: "1,200–2,000m",
    emoji: "🦙",
    notable_regions: ["Cusco", "Junín", "Cajamarca", "Huancayo"],
  },
  Honduras: {
    description:
      "Medium-bodied with chocolate and nut flavors. Affordable, quality single-origins.",
    flavor_profile: ["chocolate", "nutty", "mild", "smooth"],
    altitude_range: "1,200–1,600m",
    emoji: "🏜️",
    notable_regions: ["Copán", "Comayagua", "Santa Bárbara"],
  },
};

interface CoffeeByOrigin {
  origin: string;
  coffees: Coffee[];
  profile: (typeof ORIGIN_PROFILES)[keyof typeof ORIGIN_PROFILES];
}

function OriginCard({
  origin,
  coffees,
  profile,
}: {
  origin: string;
  coffees: Coffee[];
  profile: (typeof ORIGIN_PROFILES)[keyof typeof ORIGIN_PROFILES];
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
            <div className="text-3xl mb-2">{profile.emoji}</div>
            <h3
              className="text-2xl font-light mb-2"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {origin}
            </h3>
            <p
              className="text-sm leading-relaxed"
              style={{ color: "var(--text-muted)" }}
            >
              {profile.description}
            </p>

            {/* Meta */}
            <div className="flex items-center gap-4 mt-3 text-xs">
              <span style={{ color: "var(--text-faint)" }}>
                Altitude: {profile.altitude_range}
              </span>
              <span style={{ color: "var(--text-faint)" }}>
                {coffees.length} coffee{coffees.length !== 1 ? "s" : ""}
              </span>
            </div>
          </div>

          {/* Expand indicator */}
          <div
            className="flex-shrink-0 pt-1 transition-transform"
            style={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              color: "var(--text-muted)",
            }}
          >
            ▼
          </div>
        </div>

        {/* Flavor profile tags */}
        <div className="flex flex-wrap gap-2 mt-4">
          {profile.flavor_profile.map((flavor) => (
            <span
              key={flavor}
              className="text-xs px-2.5 py-1 rounded-full capitalize"
              style={{
                backgroundColor: "var(--bg-warm)",
                color: "var(--text)",
              }}
            >
              {flavor}
            </span>
          ))}
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
          {/* Notable regions */}
          <div className="p-6 border-b" style={{ borderColor: "var(--border-light)" }}>
            <h4
              className="text-sm uppercase tracking-wider font-semibold mb-3"
              style={{ color: "var(--text-faint)" }}
            >
              Notable Regions
            </h4>
            <div className="flex flex-wrap gap-2">
              {profile.notable_regions.map((region) => (
                <span
                  key={region}
                  className="text-xs px-3 py-1.5 rounded-full border"
                  style={{
                    borderColor: "var(--border)",
                    color: "var(--text)",
                  }}
                >
                  {region}
                </span>
              ))}
            </div>
          </div>

          {/* Coffee grid */}
          <div className="p-6">
            <h4
              className="text-sm uppercase tracking-wider font-semibold mb-4"
              style={{ color: "var(--text-faint)" }}
            >
              Coffees from {origin}
            </h4>
            {coffees.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {coffees.slice(0, 6).map((coffee) => (
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
                      {coffee.origin_region || origin}
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
            ) : (
              <p style={{ color: "var(--text-muted)" }}>
                No coffees from this origin yet
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function OriginsExplorerPage() {
  const [origins, setOrigins] = useState<CoffeeByOrigin[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrigin, setSelectedOrigin] = useState<string | null>(null);

  useEffect(() => {
    const loadOrigins = async () => {
      try {
        // Fetch all origins in parallel (not sequentially)
        const originPromises = Object.keys(ORIGIN_PROFILES).map(async (originCountry) => {
          try {
            const result = await getCoffees({
              origin_country: originCountry,
              page_size: 100,
            });
            return { origin: originCountry, coffees: result.data };
          } catch {
            return { origin: originCountry, coffees: [] };
          }
        });

        const originResults = await Promise.all(originPromises);
        const originCoffees = Object.fromEntries(
          originResults.map(r => [r.origin, r.coffees])
        );

        const sorted = Object.entries(originCoffees)
          .filter(
            ([_, coffees]) =>
              ORIGIN_PROFILES[_] && coffees.length > 0
          )
          .map(([origin, coffees]) => ({
            origin,
            coffees,
            profile: ORIGIN_PROFILES[origin],
          }))
          .sort((a, b) => b.coffees.length - a.coffees.length);

        setOrigins(sorted);
      } finally {
        setLoading(false);
      }
    };

    loadOrigins();
  }, []);

  const filteredOrigins = selectedOrigin
    ? origins.filter((o) => o.origin === selectedOrigin)
    : origins;

  return (
    <div className="px-4 py-12">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1
            className="text-5xl font-light mb-4 leading-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Origin Explorer
          </h1>
          <p style={{ color: "var(--text-muted)", maxWidth: "600px" }}>
            Discover the unique characteristics of coffees from around the
            world. Each origin has its own flavor profile, altitude, and
            history.
          </p>
        </div>

        {/* Filter buttons */}
        {origins.length > 0 && (
          <div className="mb-8 flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedOrigin(null)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                !selectedOrigin
                  ? ""
                  : ""
              }`}
              style={{
                backgroundColor: !selectedOrigin
                  ? "var(--accent)"
                  : "var(--surface)",
                color: !selectedOrigin
                  ? "#fff"
                  : "var(--text)",
                border: !selectedOrigin
                  ? "none"
                  : "1px solid var(--border-light)",
              }}
            >
              All Origins
            </button>
            {origins.map((o) => (
              <button
                key={o.origin}
                onClick={() =>
                  setSelectedOrigin(
                    selectedOrigin === o.origin ? null : o.origin
                  )
                }
                className="px-4 py-2 rounded-full text-sm font-medium transition-all"
                style={{
                  backgroundColor:
                    selectedOrigin === o.origin
                      ? "var(--accent)"
                      : "var(--surface)",
                  color:
                    selectedOrigin === o.origin
                      ? "#fff"
                      : "var(--text)",
                  border:
                    selectedOrigin === o.origin
                      ? "none"
                      : "1px solid var(--border-light)",
                }}
              >
                {o.origin}
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        {loading ? (
          <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
            Loading origins...
          </div>
        ) : filteredOrigins.length > 0 ? (
          <div className="space-y-6">
            {filteredOrigins.map((origin) => (
              <OriginCard
                key={origin.origin}
                origin={origin.origin}
                coffees={origin.coffees}
                profile={origin.profile}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
            No origins found
          </div>
        )}
      </div>
    </div>
  );
}
