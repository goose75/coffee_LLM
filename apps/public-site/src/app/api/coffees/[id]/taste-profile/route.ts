import { NextRequest, NextResponse } from "next/server";
import type { TasteProfile } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  // Taste profile not yet implemented in local database
  const data: TasteProfile = {
    bean_id: params.id,
    canonical_name: "",
    raw_notes: [],
    families: [],
    has_structured_tags: false,
    tag_count: 0,
  };
  return NextResponse.json(data);
}
