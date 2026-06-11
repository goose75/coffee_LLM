import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const params = {
      page: searchParams.get("page") ?? "1",
      page_size: searchParams.get("page_size") ?? "20",
    };

    const data = await dbQueries.getRoasters(params);
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/roasters error:", error);
    return NextResponse.json({ error: "Failed to fetch roasters" }, { status: 500 });
  }
}
