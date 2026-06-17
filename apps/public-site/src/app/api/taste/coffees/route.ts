export const dynamic = "force-dynamic";

import { query } from "@/lib/db";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const slugsParam = searchParams.get("slugs");
    const page = parseInt(searchParams.get("page") || "1", 10);
    const pageSize = parseInt(searchParams.get("page_size") || "12", 10);

    if (!slugsParam) {
      return Response.json({ data: [], total: 0, page, page_size: pageSize });
    }

    // Parse flavour slugs and convert back to display labels
    const slugs = slugsParam.split(",").filter(Boolean);
    const flavourLabels = slugs.map(slug =>
      slug
        .split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ")
    );

    const offset = (page - 1) * pageSize;

    // Count total coffees matching any of the selected flavours
    const countQueryText = `
      SELECT COUNT(DISTINCT cb.id) as count
      FROM canonical_beans cb
      LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
      WHERE bl.id IS NOT NULL
        AND cb.flavour_notes IS NOT NULL
        AND (
          ${flavourLabels.map((_, i) => `$${i + 1} = ANY(cb.flavour_notes)`).join(" OR ")}
        )
    `;

    const countResult = await query(countQueryText, flavourLabels);
    const total = parseInt(countResult.rows[0].count, 10) || 0;

    // Fetch coffees matching the selected flavours
    const queryText = `
      SELECT DISTINCT
        cb.id,
        cb.canonical_name,
        cb.origin_country,
        cb.origin_region,
        cb.farm_or_estate,
        cb.washing_station,
        cb.producer,
        cb.varietal,
        cb.process,
        cb.process_detail,
        cb.altitude_masl_min,
        cb.altitude_masl_max,
        cb.harvest_year,
        cb.roast_level,
        cb.flavour_notes,
        cb.decaf_flag,
        cb.espresso_suitable_flag,
        cb.filter_suitable_flag,
        cb.data_completeness_score,
        COUNT(DISTINCT bl.id) as listing_count,
        MIN(lv.price_gbp) as min_price_gbp,
        MAX(lv.price_gbp) as max_price_gbp
      FROM canonical_beans cb
      LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
      LEFT JOIN listing_variants lv ON bl.id = lv.bean_listing_id
      WHERE bl.id IS NOT NULL
        AND cb.flavour_notes IS NOT NULL
        AND (
          ${flavourLabels.map((_, i) => `$${i + 1} = ANY(cb.flavour_notes)`).join(" OR ")}
        )
      GROUP BY cb.id
      ORDER BY cb.canonical_name ASC
      LIMIT $${flavourLabels.length + 1} OFFSET $${flavourLabels.length + 2}
    `;

    const dataResult = await query(queryText, [...flavourLabels, pageSize, offset]);

    const data = dataResult.rows.map(row => ({
      id: row.id,
      canonical_name: row.canonical_name,
      origin_country: row.origin_country,
      origin_region: row.origin_region,
      farm_or_estate: row.farm_or_estate,
      washing_station: row.washing_station,
      producer: row.producer,
      varietal: row.varietal || [],
      process: row.process,
      process_detail: row.process_detail,
      altitude_masl_min: row.altitude_masl_min,
      altitude_masl_max: row.altitude_masl_max,
      harvest_year: row.harvest_year,
      roast_level: row.roast_level,
      flavour_notes: row.flavour_notes || [],
      decaf_flag: row.decaf_flag,
      espresso_suitable_flag: row.espresso_suitable_flag,
      filter_suitable_flag: row.filter_suitable_flag,
      data_completeness_score: row.data_completeness_score,
      listing_count: parseInt(row.listing_count, 10),
      min_price_gbp: row.min_price_gbp ? parseFloat(row.min_price_gbp) : null,
      max_price_gbp: row.max_price_gbp ? parseFloat(row.max_price_gbp) : null,
      matched_tags: flavourLabels
        .filter(label => row.flavour_notes?.includes(label))
        .map(label => ({
          slug: label.toLowerCase().replace(/\s+/g, "-"),
          label
        }))
    }));

    return Response.json({ data, total, page, page_size: pageSize });
  } catch (error) {
    console.error("Error fetching taste atlas coffees:", error);
    return Response.json(
      { error: "Failed to fetch coffees", data: [], total: 0 },
      { status: 500 }
    );
  }
}
