const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    next: { revalidate: 300 }, // 5-min cache
  } as RequestInit);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PriceVariant {
  id: string;
  weight_g: number | null;
  grind_type: string;
  price_gbp: number;
  price_per_100g_gbp: number | null;
  availability_status: string;
  sku: string | null;
}

export interface StoreListing {
  id: string;
  store_id: string;
  store_name: string;
  store_domain: string;
  raw_title: string;
  product_url: string | null;
  listing_status: string;
  active_flag: boolean;
  variants: PriceVariant[];
  min_price_gbp: number | null;
  max_price_gbp: number | null;
}

export interface Coffee {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  farm_or_estate: string | null;
  washing_station: string | null;
  producer: string | null;
  varietal: string[];
  process: string | null;
  process_detail: string | null;
  altitude_masl_min: number | null;
  altitude_masl_max: number | null;
  harvest_year: number | null;
  roast_level: string | null;
  flavour_notes: string[];
  decaf_flag: boolean;
  espresso_suitable_flag: boolean;
  filter_suitable_flag: boolean;
  data_completeness_score: number;
  listing_count?: number;
  min_price_gbp?: number | null;
  max_price_gbp?: number | null;
  min_price_per_100g_gbp?: number | null;
  store_count?: number;
  newest_listing_at?: string | null;
  listings?: StoreListing[];
}

export interface Roaster {
  id: string;
  name: string;
  domain: string;
  homepage_url: string;
  uk_region: string | null;
  roaster_flag: boolean;
  cafe_flag: boolean;
  active_flag: boolean;
  listing_count?: number;
}

export interface Paginated<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function getCoffees(params: Record<string, string | number | undefined> = {}): Promise<Paginated<Coffee>> {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); });
  return apiFetch<Paginated<Coffee>>(`/coffees${p.toString() ? `?${p}` : ""}`);
}

export async function getCoffee(id: string): Promise<Coffee> {
  return apiFetch<Coffee>(`/coffees/${id}`);
}

export async function compareCoffee(id: string): Promise<Coffee & { listings: StoreListing[] }> {
  return apiFetch<Coffee & { listings: StoreListing[] }>(`/coffees/${id}/compare`);
}

export async function getRoasters(params: Record<string, string | number | undefined> = {}): Promise<Paginated<Roaster>> {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); });
  return apiFetch<Paginated<Roaster>>(`/roasters${p.toString() ? `?${p}` : ""}`);
}

export async function getNewReleases(params: Record<string, string | number | undefined> = {}): Promise<Paginated<Coffee>> {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); });
  return apiFetch<Paginated<Coffee>>(`/new-releases${p.toString() ? `?${p}` : ""}`);
}

// Frontend proxy API fetch (for /api/... endpoints, not /api/v1/...)
async function frontendApiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    next: { revalidate: 60 }, // 1-min cache for deals/trending
  } as RequestInit);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function getDeals(params: Record<string, string | number | undefined> = {}): Promise<Coffee[]> {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); });
  return frontendApiFetch<Coffee[]>(`/api/deals${p.toString() ? `?${p}` : ""}`);
}

export async function getTrendingCoffees(params: Record<string, string | number | undefined> = {}): Promise<Paginated<Coffee>> {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); });
  return frontendApiFetch<Paginated<Coffee>>(`/api/new-releases${p.toString() ? `?${p}` : ""}`);
}

// ── Mock data for development (API not yet live) ──────────────────────────────


// ── Price intelligence types ──────────────────────────────────────────────────

export interface PricePoint {
  recorded_at: string;
  price_gbp: number;
  price_per_100g_gbp: number | null;
  availability_status: string;
}

export interface VariantPriceHistory {
  variant_id: string;
  variant_title: string;
  weight_g: number | null;
  grind_type: string;
  store_name: string;
  store_id: string;
  store_domain: string;
  history: PricePoint[];
  latest_price_gbp: number | null;
  latest_price_per_100g: number | null;
}

export interface BeanPriceHistory {
  bean_id: string;
  canonical_name: string;
  variants: VariantPriceHistory[];
  min_current_price_gbp: number | null;
  min_current_per_100g: number | null;
}

export interface VariantOffer {
  variant_id: string;
  weight_g: number | null;
  grind_type: string;
  price_gbp: number;
  price_per_100g_gbp: number | null;
  availability_status: string;
  product_url: string | null;
}

export interface SellerListing {
  store_id: string;
  store_name: string;
  store_domain: string;
  store_homepage_url: string;
  offers: VariantOffer[];
  min_price_gbp: number | null;
  cheapest_per_100g: number | null;
}

export interface SellerComparison {
  bean_id: string;
  canonical_name: string;
  stores: SellerListing[];
  best_price_gbp: number | null;
  best_price_per_100g: number | null;
}

export interface PriceSummaryStats {
  weight_g: number | null;
  sample_count: number;
  min_price_gbp: number | null;
  max_price_gbp: number | null;
  median_price_gbp: number | null;
  mean_price_gbp: number | null;
  min_per_100g: number | null;
  max_per_100g: number | null;
  median_per_100g: number | null;
}

// ── Taste intelligence types ──────────────────────────────────────────────────

export interface TaggedNote {
  raw_note: string;
  slug: string;
  label: string;
  confidence: number;
  source: string;
}

export interface FlavorFamily {
  family_slug: string;
  family_label: string;
  colour: string;
  tags: TaggedNote[];
  weight: number;
}

export interface TasteProfile {
  bean_id: string;
  canonical_name: string;
  raw_notes: string[];
  families: FlavorFamily[];
  has_structured_tags: boolean;
  tag_count: number;
}

export interface SimilarCoffee {
  bean_id: string;
  canonical_name: string;
  origin_country: string | null;
  process: string | null;
  roast_level: string | null;
  flavour_notes: string[];
  similarity_score: number;
  shared_families: string[];
}

export interface MarketAverages {
  median_per_100g_gbp: number | null;
  mean_per_100g_gbp: number | null;
  min_per_100g_gbp: number | null;
  max_per_100g_gbp: number | null;
  sample_size: number;
}

export async function getMarketAverages(): Promise<MarketAverages> {
  return apiFetch<MarketAverages>("/market/averages");
}

// ── Price + taste fetch functions ─────────────────────────────────────────────

export async function getPriceHistory(coffeeId: string, days = 90): Promise<BeanPriceHistory> {
  return apiFetch<BeanPriceHistory>(`/coffees/${coffeeId}/price-history?days=${days}`);
}

export async function getPriceCompare(coffeeId: string): Promise<SellerComparison> {
  return apiFetch<SellerComparison>(`/coffees/${coffeeId}/price-compare`);
}

export async function getPriceStats(coffeeId: string): Promise<PriceSummaryStats[]> {
  return apiFetch<PriceSummaryStats[]>(`/coffees/${coffeeId}/price-stats`);
}

export async function getTasteProfile(coffeeId: string): Promise<TasteProfile> {
  return apiFetch<TasteProfile>(`/coffees/${coffeeId}/taste-profile`);
}

export async function getSimilarCoffees(coffeeId: string, limit = 4): Promise<SimilarCoffee[]> {
  return apiFetch<SimilarCoffee[]>(`/coffees/${coffeeId}/similar?limit=${limit}`);
}
