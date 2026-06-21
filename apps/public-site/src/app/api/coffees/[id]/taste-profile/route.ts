import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/api/v1/coffees/${params.id}/taste-profile`);

    if (!response.ok) {
      return NextResponse.json({ bean_id: params.id, canonical_name: "", raw_notes: [], families: [], has_structured_tags: false, tag_count: 0 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/taste-profile error:`, error);
    return NextResponse.json({ bean_id: params.id, canonical_name: "", raw_notes: [], families: [], has_structured_tags: false, tag_count: 0 });
  }
}
