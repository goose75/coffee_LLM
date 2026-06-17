export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const country = searchParams.get("country");

    if (country) {
      // Get specific country origins/regions
      const queryText = `
        SELECT DISTINCT
          cb.origin_country,
          cb.origin_region,
          COUNT(DISTINCT cb.id) as coffee_count,
          COUNT(DISTINCT bl.id) as listing_count
        FROM canonical_beans cb
        LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
        WHERE cb.origin_country ILIKE $1
          AND bl.id IS NOT NULL
        GROUP BY cb.origin_country, cb.origin_region
        ORDER BY cb.origin_region
      `;

      const result = await query(queryText, [`%${country}%`]);
      return NextResponse.json({
        origins: result.rows.map(row => ({
          country: row.origin_country,
          region: row.origin_region,
          coffee_count: parseInt(row.coffee_count, 10),
          listing_count: parseInt(row.listing_count, 10)
        }))
      });
    } else {
      // Get all countries
      const queryText = `
        SELECT DISTINCT
          cb.origin_country,
          COUNT(DISTINCT cb.id) as coffee_count,
          COUNT(DISTINCT bl.id) as listing_count
        FROM canonical_beans cb
        LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
        WHERE cb.origin_country IS NOT NULL
          AND bl.id IS NOT NULL
        GROUP BY cb.origin_country
        ORDER BY listing_count DESC, cb.origin_country ASC
      `;

      const result = await query(queryText);
      return NextResponse.json({
        origins: result.rows.map(row => ({
          country: row.origin_country,
          coffee_count: parseInt(row.coffee_count, 10),
          listing_count: parseInt(row.listing_count, 10)
        }))
      });
    }
  } catch (error) {
    console.error("Error fetching origins:", error);
    return NextResponse.json(
      { error: "Failed to fetch origins", origins: [] },
      { status: 500 }
    );
  }
}
