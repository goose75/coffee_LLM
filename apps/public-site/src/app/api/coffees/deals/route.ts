import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const params: Record<string, string | number | undefined> = {
      page: searchParams.get("page") ?? "1",
      page_size: searchParams.get("page_size") ?? "20",
    };

    const data = await dbQueries.getCoffees(params);
    // Return just the array of coffees, not the paginated response
    return NextResponse.json(data.data);
  } catch (error) {
    console.error("GET /api/coffees/deals error:", error);
    return NextResponse.json({ error: "Failed to fetch deals" }, { status: 500 });
  }
}
