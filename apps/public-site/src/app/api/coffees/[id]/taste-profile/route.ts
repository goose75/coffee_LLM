'use server';

import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const data = await dbQueries.getTasteProfile(params.id);
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/taste-profile error:`, error);
    return NextResponse.json({ bean_id: params.id, canonical_name: "", raw_notes: [], families: [], has_structured_tags: false, tag_count: 0 });
  }
}
