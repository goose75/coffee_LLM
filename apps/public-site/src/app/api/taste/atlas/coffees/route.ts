export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const slugsParam = searchParams.get("slugs");
    const page = searchParams.get("page") || "1";
    const pageSize = searchParams.get("page_size") || "12";

    if (!slugsParam) {
      return NextResponse.json({ data: [], total: 0, page: parseInt(page), page_size: parseInt(pageSize) });
    }

    const apiUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(
      `${apiUrl}/api/v1/taste/atlas/coffees?slugs=${encodeURIComponent(slugsParam)}&page=${page}&page_size=${pageSize}`
    );

    if (!response.ok) {
      console.error("Backend API error:", response.status);
      return NextResponse.json(
        { error: "Failed to fetch coffees", data: [], total: 0 },
        { status: 500 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching taste atlas coffees:", error);
    return NextResponse.json(
      { error: "Failed to fetch coffees", data: [], total: 0 },
      { status: 500 }
    );
  }
}
