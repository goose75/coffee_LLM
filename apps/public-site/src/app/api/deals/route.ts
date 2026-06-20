import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const days = searchParams.get("days") ?? "7";
    const minDiscount = searchParams.get("min_discount_percent") ?? "10";
    const limit = searchParams.get("limit") ?? "6";

    const apiUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(
      `${apiUrl}/api/v1/coffees/deals?days=${days}&min_discount_percent=${minDiscount}&limit=${limit}`
    );

    if (!response.ok) {
      console.error("Backend API error:", response.status);
      return NextResponse.json({ error: "Failed to fetch deals" }, { status: 500 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/deals error:", error);
    return NextResponse.json({ error: "Failed to fetch deals" }, { status: 500 });
  }
}
