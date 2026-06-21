import { NextRequest, NextResponse } from "next/server";
import type { BeanPriceHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  // Price history not yet implemented in local database
  const data: BeanPriceHistory = {
    bean_id: params.id,
    canonical_name: "",
    variants: [],
    min_current_price_gbp: null,
    min_current_per_100g: null,
  };
  return NextResponse.json(data);
}
