import { NextRequest, NextResponse } from "next/server";
import type { SimilarCoffee } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  // Similar coffees not yet implemented in local database
  const data: SimilarCoffee[] = [];
  return NextResponse.json(data);
}
