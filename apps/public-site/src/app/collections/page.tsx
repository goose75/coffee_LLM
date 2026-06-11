"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { getCoffees, type Coffee } from "@/lib/api";

const COLLECTIONS = [
  {
    id: "bright-fruity",
    title: "Bright & Fruity",
    description: "Light roasts with vibrant citrus and berry notes",
    emoji: "🍋",
    icon: "✨",
    filters: { roast_level: "light", flavour: "citrus" },
    color: "#f5a623",
  },
  {
    id: "smooth-chocolatey",
    title: "Smooth & Chocolatey",
    description: "Medium roasts with rich chocolate and nutty undertones",
    emoji: "🍫",
    icon: "☕",
    filters: { roast_level: "medium", flavour: "chocolate" },
    color: "#8b6f47",
  },
  {
    id: "wild-fermented",
    title: "Wild & Fermented",
    description: "Natural process coffees with complex, wine-like notes",
    emoji: "🍷",
    icon: "🌿",
    filters: { process: "natural" },
    color: "#8b6bab",
  },
  {
    id: "espresso-ready",
    title: "Espresso Ready",
    description: "Coffees optimized for espresso shots",
    emoji: "🎯",
    icon: "💪",
    filters: { espresso_suitable: true },
    color: "#5a7fa8",
  },
  {
    id: "pour-over-perfect",
    title: "Pour Over Perfect",
    description: "Coffees that shine in pour over and drip brewing",
    emoji: "🫗",
    icon: "💧",
    filters: { filter_suitable: true },
    color: "#6b9e8c",
  },
  {
    id: "seasonal-limited",
    title: "Seasonal & Limited",
    description: "Fresh arrivals and exclusive releases",
    emoji: "🌾",
    icon: "🎁",
    filters: {},
    color: "#d4a03a",
  },
];

function CollectionCard({
  collection,
  coffeeCount,
}: {
  collection: (typeof COLLECTIONS)[0];
  coffeeCount: number;
}) {
  return (
    <Link
      href={`/coffees?collection=${collection.id}`}
      className="group relative overflow-hidden rounded-2xl transition-all hover:shadow-lg"
      style={{
        backgroundColor: collection.color,
        aspectRatio: "1 / 1.2",
        border: "1px solid rgba(255,255,255,0.1)",
      }}
    >
      {/* Gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(135deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.3) 100%)",
        }}
      />

      {/* Content */}
      <div className="relative h-full p-6 flex flex-col justify-between">
        {/* Header */}
        <div>
          <div className="text-4xl mb-2">{collection.emoji}</div>
          <h3
            className="text-2xl font-light leading-tight mb-2 text-white"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {collection.title}
          </h3>
          <p className="text-sm text-white opacity-90">
            {collection.description}
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-end justify-between">
          <div className="text-white opacity-75">
            <div className="text-xs uppercase tracking-wider font-semibold">
              Coffees
            </div>
            <div className="text-2xl font-light">{coffeeCount}</div>
          </div>
          <div className="text-3xl opacity-50 group-hover:opacity-100 transition-opacity">
            {collection.icon}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function CollectionsPage() {
  const [collectionCounts, setCollectionCounts] = useState<
    Record<string, number>
  >({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCounts = async () => {
      try {
        // Fetch all collection counts in parallel (not sequentially)
        const countPromises = COLLECTIONS.map(async (collection) => {
          try {
            let params: Record<string, any> = { page: 1, page_size: 1 };

            if (collection.filters.roast_level) {
              params.roast = collection.filters.roast_level;
            }
            if (collection.filters.process) {
              params.process = collection.filters.process;
            }
            if (collection.filters.espresso_suitable) {
              params.espresso_suitable = "true";
            }
            if (collection.filters.filter_suitable) {
              params.filter_suitable = "true";
            }

            const result = await getCoffees(params);
            return { id: collection.id, count: result.total };
          } catch {
            return { id: collection.id, count: 0 };
          }
        });

        const results = await Promise.all(countPromises);
        const counts = Object.fromEntries(results.map(r => [r.id, r.count]));
        setCollectionCounts(counts);
      } finally {
        setLoading(false);
      }
    };

    loadCounts();
  }, []);

  return (
    <div className="px-4 py-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1
            className="text-5xl font-light mb-4 leading-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Curated Collections
          </h1>
          <p
            className="text-lg"
            style={{ color: "var(--text)", maxWidth: "600px" }}
          >
            Discover coffees handpicked for specific moments and brewing
            methods. Whether you're seeking bright mornings or smooth evenings,
            find your next favourite.
          </p>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {COLLECTIONS.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              coffeeCount={collectionCounts[collection.id] || 0}
            />
          ))}
        </div>

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
            How we choose
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3
                className="font-semibold mb-2"
                style={{ color: "var(--text)" }}
              >
                Quality First
              </h3>
              <p style={{ color: "var(--text-muted)" }}>
                Every coffee in our collections meets strict quality standards.
                We focus on specialty-grade beans with clear provenance and
                unique character.
              </p>
            </div>
            <div>
              <h3
                className="font-semibold mb-2"
                style={{ color: "var(--text)" }}
              >
                Experience Matters
              </h3>
              <p style={{ color: "var(--text-muted)" }}>
                Collections are designed for specific brewing methods and
                occasions. Each selection has been tested and recommended for
                how it's meant to be enjoyed.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
