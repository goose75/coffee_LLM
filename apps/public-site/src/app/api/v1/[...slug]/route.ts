import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, { params }: { params: Promise<{ slug: string[] }> }) {
  try {
    const { slug } = await params;
    const path = `/${slug.join("/")}`;
    const searchParams = request.nextUrl.searchParams;
    const queryString = searchParams.toString();

    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const url = `${backendUrl}/api/v1${path}${queryString ? `?${queryString}` : ""}`;

    const response = await fetch(url);
    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/v1 proxy error:", error);
    return NextResponse.json({ error: "Failed to fetch from API" }, { status: 500 });
  }
}
