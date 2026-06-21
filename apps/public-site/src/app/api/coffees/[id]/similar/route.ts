'use server';

import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const limit = Number(request.nextUrl.searchParams.get("limit")) || 4;
    const data = await dbQueries.getSimilarCoffees(params.id, limit);
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id}/similar error:`, error);
    return NextResponse.json([]);
  }
}
