import { NextRequest, NextResponse } from "next/server";
import * as dbQueries from "@/lib/db-queries";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const data = await dbQueries.getCoffee(params.id);
    return NextResponse.json(data);
  } catch (error) {
    console.error(`GET /api/coffees/${params.id} error:`, error);
    return NextResponse.json({ error: "Coffee not found" }, { status: 404 });
  }
}
