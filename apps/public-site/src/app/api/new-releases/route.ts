import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const params = {
      page: searchParams.get("page") ?? "1",
      page_size: searchParams.get("page_size") ?? "20",
      days: searchParams.get("days") ?? "30",
    };

    const data = await dbQueries.getNewReleases(params);
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/new-releases error:", error);
    return NextResponse.json({ error: "Failed to fetch new releases" }, { status: 500 });
  }
}
