export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { query } from "@/lib/db";

interface AtlasNode {
  slug: string;
  label: string;
  depth: number;
  colour: string;
  coffee_count: number;
  children: AtlasNode[];
}

interface AtlasResponse {
  families: AtlasNode[];
  total_coffees: number;
}

const FLAVOUR_FAMILIES: Record<string, { label: string; colour: string; tags: string[] }> = {
  "fruity": {
    label: "Fruity",
    colour: "#FF6B6B",
    tags: ["apple", "banana", "berry", "blackcurrant", "blueberry", "cherry", "citrus", "coconut", "fig", "grape", "grapefruit", "lemon", "lime", "mango", "orange", "peach", "pear", "pineapple", "plum", "pomegranate", "raspberry", "strawberry", "tropical fruit", "watermelon"]
  },
  "floral": {
    label: "Floral",
    colour: "#DA70D6",
    tags: ["bergamot", "chamomile", "floral", "geranium", "hibiscus", "honey", "jasmine", "lavender", "lilac", "orange blossom", "orchid", "rose", "violeta"]
  },
  "sweet": {
    label: "Sweet",
    colour: "#FFD700",
    tags: ["brown sugar", "caramel", "candy", "chocolate", "cocoa", "fudge", "honey", "maple", "molasses", "sugar", "sweet", "vanilla"]
  },
  "spicy": {
    label: "Spicy",
    colour: "#FF8C00",
    tags: ["anise", "cardamom", "cinnamon", "clove", "cumin", "ginger", "licorice", "pepper", "star anise", "tobacco"]
  },
  "earthy": {
    label: "Earthy",
    colour: "#8B7355",
    tags: ["cedar", "clay", "dirt", "earthy", "forest", "grain", "hay", "leather", "moss", "mushroom", "nut", "peat", "soil", "tobacco", "wood"]
  },
  "nutty": {
    label: "Nutty",
    colour: "#D4A574",
    tags: ["almond", "chestnut", "hazelnut", "macadamia", "nut", "peanut", "pecan", "pistachio", "walnut"]
  },
  "acidic": {
    label: "Acidic",
    colour: "#90EE90",
    tags: ["acidic", "bright", "crisp", "lactic", "malic", "sour", "tangy", "tart", "vinegary", "wine-like"]
  },
  "savory": {
    label: "Savory",
    colour: "#A0522D",
    tags: ["bread", "cereal", "grain", "herbal", "malty", "meaty", "savory", "toast", "umami"]
  }
};

export async function GET() {
  try {
    const result = await query(
      `SELECT DISTINCT flavour_notes FROM canonical_beans WHERE flavour_notes IS NOT NULL AND array_length(flavour_notes, 1) > 0`
    );

    const allTags = new Set<string>();
    result.rows.forEach(row => {
      if (row.flavour_notes && Array.isArray(row.flavour_notes)) {
        row.flavour_notes.forEach((tag: string) => {
          if (tag && tag.trim()) {
            allTags.add(tag.toLowerCase().trim());
          }
        });
      }
    });

    const tagCounts: Record<string, number> = {};
    const countResult = await query(
      `SELECT DISTINCT flavour_notes FROM canonical_beans cb
       WHERE cb.flavour_notes IS NOT NULL AND array_length(cb.flavour_notes, 1) > 0
       AND EXISTS (SELECT 1 FROM bean_listings WHERE canonical_bean_id = cb.id)`
    );

    countResult.rows.forEach(row => {
      if (row.flavour_notes && Array.isArray(row.flavour_notes)) {
        row.flavour_notes.forEach((tag: string) => {
          const normalized = tag.toLowerCase().trim();
          tagCounts[normalized] = (tagCounts[normalized] || 0) + 1;
        });
      }
    });

    const families: AtlasNode[] = Object.entries(FLAVOUR_FAMILIES).map(([familySlug, family]) => {
      const children: AtlasNode[] = family.tags
        .filter(tag => allTags.has(tag.toLowerCase()))
        .map(tag => ({
          slug: tag.toLowerCase().replace(/\s+/g, "-"),
          label: tag,
          depth: 2,
          colour: family.colour,
          coffee_count: tagCounts[tag.toLowerCase()] || 0,
          children: []
        }));

      return {
        slug: familySlug,
        label: family.label,
        depth: 1,
        colour: family.colour,
        coffee_count: children.reduce((sum, child) => sum + child.coffee_count, 0),
        children
      };
    }).filter(f => f.children.length > 0);

    const totalResult = await query(
      `SELECT COUNT(DISTINCT cb.id) as count FROM canonical_beans cb
       WHERE EXISTS (SELECT 1 FROM bean_listings WHERE canonical_bean_id = cb.id)`
    );

    const response: AtlasResponse = {
      families: families.sort((a, b) => b.coffee_count - a.coffee_count),
      total_coffees: parseInt(totalResult.rows[0].count, 10) || 0
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error("Error fetching taste atlas:", error);
    return NextResponse.json(
      { error: "Failed to fetch taste atlas", families: [], total_coffees: 0 },
      { status: 500 }
    );
  }
}
