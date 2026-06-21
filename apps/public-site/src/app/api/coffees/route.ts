import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const queryString = request.nextUrl.searchParams.toString();
    const response = await fetch(`${backendUrl}/api/v1/coffees?${queryString}`);

    if (!response.ok) {
      return NextResponse.json({ error: "Failed to fetch coffees" }, { status: 500 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/coffees error:", error);
    return NextResponse.json({ error: "Failed to fetch coffees" }, { status: 500 });
  }
}
