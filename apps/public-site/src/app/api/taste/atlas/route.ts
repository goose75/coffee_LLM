export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";

export async function GET() {
  try {
    const apiUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/v1/taste/atlas`);

    if (!response.ok) {
      console.error("Backend API error:", response.status);
      return NextResponse.json(
        { error: "Failed to fetch taste atlas", families: [], total_coffees: 0 },
        { status: 500 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching taste atlas:", error);
    return NextResponse.json(
      { error: "Failed to fetch taste atlas", families: [], total_coffees: 0 },
      { status: 500 }
    );
  }
}
