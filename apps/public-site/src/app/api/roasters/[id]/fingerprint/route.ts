import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/api/v1/roasters/${params.id}/fingerprint`);

    if (!response.ok) {
      console.error("Backend API error:", response.status);
      return NextResponse.json({ error: "Failed to fetch roaster fingerprint" }, { status: 500 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/roasters/${params.id}/fingerprint error:`, error);
    return NextResponse.json({ error: "Failed to fetch roaster fingerprint" }, { status: 500 });
  }
}
