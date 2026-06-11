import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export async function GET(request: NextRequest) {
  try {
    const data = await dbQueries.getMarketAverages();
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/market/averages error:", error);
    return NextResponse.json({ error: "Failed to fetch market averages" }, { status: 500 });
  }
}
