import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/api/v1/coffees/${params.id}`);

    if (!response.ok) {
      return NextResponse.json({ error: "Coffee not found" }, { status: 404 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id} error:`, error);
    return NextResponse.json({ error: "Failed to fetch coffee" }, { status: 500 });
  }
}
