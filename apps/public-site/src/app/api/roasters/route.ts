import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const searchParams = request.nextUrl.searchParams;
    const page = searchParams.get("page") || "1";
    const page_size = searchParams.get("page_size") || "20";

    const response = await fetch(`${backendUrl}/api/v1/roasters?page=${page}&page_size=${page_size}`);

    if (!response.ok) {
      return NextResponse.json({ error: "Failed to fetch roasters" }, { status: 500 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET /api/roasters error:", error);
    return NextResponse.json({ error: "Failed to fetch roasters" }, { status: 500 });
  }
}
