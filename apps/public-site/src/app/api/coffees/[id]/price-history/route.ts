import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const days = request.nextUrl.searchParams.get("days") || "60";
    const response = await fetch(`${backendUrl}/api/v1/coffees/${params.id}/price-history?days=${days}`);

    if (!response.ok) {
      return NextResponse.json({ bean_id: params.id, canonical_name: "", variants: [], min_current_price_gbp: null, min_current_per_100g: null });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/price-history error:`, error);
    return NextResponse.json({ bean_id: params.id, canonical_name: "", variants: [], min_current_price_gbp: null, min_current_per_100g: null });
  }
}
