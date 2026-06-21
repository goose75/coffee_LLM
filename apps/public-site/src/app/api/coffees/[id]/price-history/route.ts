'use server';

import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const data = await dbQueries.getPriceHistory(params.id);
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/price-history error:`, error);
    return NextResponse.json({ bean_id: params.id, canonical_name: "", variants: [], min_current_price_gbp: null, min_current_per_100g: null });
  }
}
