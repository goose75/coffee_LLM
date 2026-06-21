import { NextRequest, NextResponse } from "next/server";
import type { PriceSummaryStats } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  // Price stats not yet implemented in local database
  const data: PriceSummaryStats[] = [];
  return NextResponse.json(data);
}
