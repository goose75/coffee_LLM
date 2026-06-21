'use server';

import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const data = await dbQueries.getPriceStats(params.id);
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/price-stats error:`, error);
    return NextResponse.json([]);
  }
}
