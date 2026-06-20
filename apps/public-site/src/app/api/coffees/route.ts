import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const params: Record<string, string | number | undefined> = {
      page: searchParams.get("page") ?? "1",
      page_size: searchParams.get("page_size") ?? "20",
      search: searchParams.get("search") ?? undefined,
      process: searchParams.get("process") ?? undefined,
      origin: searchParams.get("origin") ?? undefined,
      roast: searchParams.get("roast") ?? undefined,
      flavour: searchParams.get("flavour") ?? undefined,
      store_domain: searchParams.get("store_domain") ?? undefined,
    };

    const data = await dbQueries.getCoffees(params);
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/coffees error:", error);
    return NextResponse.json({ error: "Failed to fetch coffees" }, { status: 500 });
  }
}
