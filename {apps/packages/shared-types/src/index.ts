// ─── Controlled Vocabularies ──────────────────────────────────────────────────

export type RoastLevel =
  | "light"
  | "medium_light"
  | "medium"
  | "medium_dark"
  | "dark"
  | "unknown";

export type GrindType =
  | "whole_bean"
  | "espresso"
  | "filter"
  | "cafetiere"
  | "moka"
  | "aeropress"
  | "pour_over"
  | "omni"
  | "unknown";

export type Process =
  | "washed"
  | "natural"
  | "honey"
  | "anaerobic"
  | "wet_hulled"
  | "carbonic_maceration"
  | "experimental"
  | "unknown";

export type SourceType = "shopify" | "html" | "schema_org" | "dataset";
export type ParserStrategy = "shopify" | "schema_org" | "html" | "llm" | "unknown";
export type ExtractionMethod = "shopify_json" | "schema_org" | "html_rules" | "llm";
export type ReviewStatus = "pending" | "accepted" | "rejected" | "skipped";
export type IngestionRunStatus = "running" | "completed" | "failed" | "partial";
export type ListingStatus = "active" | "inactive" | "archived";
export type AvailabilityStatus = "in_stock" | "out_of_stock" | "preorder" | "unknown";

// ─── Store / Source ───────────────────────────────────────────────────────────

export interface Store {
  id: string;
  name: string;
  domain: string;
  homepage_url: string;
  source_type: SourceType;
  country_code: string;
  uk_region: string | null;
  roaster_flag: boolean;
  cafe_flag: boolean;
  ecommerce_flag: boolean;
  active_flag: boolean;
  crawl_frequency_hours: number;
  last_successful_crawl_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourcePage {
  id: string;
  store_id: string;
  url: string;
  page_type: "listing" | "product" | "feed" | "sitemap" | "homepage";
  discovered_at: string;
  last_fetched_at: string | null;
  status_code: number | null;
  content_hash: string | null;
  raw_storage_path: string | null;
  parser_strategy: ParserStrategy;
  changed_flag: boolean;
}

// ─── Extraction ───────────────────────────────────────────────────────────────

export interface RawExtraction {
  id: string;
  source_page_id: string;
  extraction_method: ExtractionMethod;
  model_name: string | null;
  prompt_version: string | null;
  extracted_payload: ExtractionPayload;
  confidence_score: number;
  validation_status: "valid" | "invalid" | "partial";
  created_at: string;
}

export interface ExtractionPayload {
  coffee_name: string;
  roaster_name: string;
  origin_country: string;
  origin_region: string;
  farm_or_estate: string;
  producer: string;
  varietal: string[];
  process: string;
  roast_level: string;
  brew_suitability: string[];
  grind_options: string[];
  flavour_notes: string[];
  weights: number[];
  price_variants: PriceVariant[];
  decaf_flag: boolean;
  confidence: number;
  reasoning_summary: string;
}

export interface PriceVariant {
  weight_g: number;
  grind_type: string;
  price_gbp: number;
}

// ─── Canonical Bean ───────────────────────────────────────────────────────────

export interface CanonicalBean {
  id: string;
  canonical_name: string;
  origin_country: string | null;
  origin_region: string | null;
  farm_or_estate: string | null;
  washing_station: string | null;
  producer: string | null;
  varietal: string[];
  process: Process | null;
  altitude_masl_min: number | null;
  altitude_masl_max: number | null;
  harvest_year: number | null;
  roast_level: RoastLevel | null;
  flavour_notes: string[];
  decaf_flag: boolean;
  espresso_suitable_flag: boolean;
  filter_suitable_flag: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Listings & Variants ──────────────────────────────────────────────────────

export interface BeanListing {
  id: string;
  store_id: string;
  canonical_bean_id: string | null;
  source_page_id: string;
  raw_title: string;
  raw_subtitle: string | null;
  raw_description: string | null;
  roast_label_raw: string | null;
  process_label_raw: string | null;
  origin_label_raw: string | null;
  varietal_label_raw: string | null;
  listing_status: ListingStatus;
  first_seen_at: string;
  last_seen_at: string;
  last_changed_at: string | null;
  content_hash: string;
  active_flag: boolean;
}

export interface ListingVariant {
  id: string;
  bean_listing_id: string;
  variant_title_raw: string;
  weight_g: number | null;
  grind_type: GrindType;
  pack_count: number | null;
  price_gbp: number;
  price_per_100g_gbp: number | null;
  currency_code: string;
  availability_status: AvailabilityStatus;
  sku: string | null;
  seller_variant_id: string | null;
  recorded_at: string;
}

export interface PriceHistory {
  id: string;
  listing_variant_id: string;
  price_gbp: number;
  availability_status: AvailabilityStatus;
  recorded_at: string;
}

// ─── Entity Resolution ────────────────────────────────────────────────────────

export interface CanonicalMatch {
  id: string;
  bean_listing_id: string;
  proposed_canonical_bean_id: string;
  match_method: "exact" | "fuzzy" | "embedding" | "combined" | "manual";
  confidence_score: number;
  accepted_by_system_flag: boolean;
  reviewed_by_user_id: string | null;
  review_status: ReviewStatus;
  created_at: string;
}

export interface NormalisationMapping {
  id: string;
  mapping_type: "grind" | "roast_level" | "process" | "country" | "region" | "varietal";
  raw_value: string;
  normalised_value: string;
  confidence_score: number;
  created_at: string;
  updated_at: string;
}

// ─── Ingestion ────────────────────────────────────────────────────────────────

export interface IngestionRun {
  id: string;
  run_type: "full" | "incremental" | "single_store" | "single_page";
  store_id: string | null;
  started_at: string;
  completed_at: string | null;
  status: IngestionRunStatus;
  records_seen: number;
  records_created: number;
  records_updated: number;
  warnings: string[];
  errors: string[];
}

// ─── API Response Wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface ApiError {
  error: string;
  message: string;
  detail?: unknown;
}

// ─── Public Website Types ─────────────────────────────────────────────────────

export interface CoffeeSearchParams {
  q?: string;
  origin_country?: string;
  process?: Process;
  roast_level?: RoastLevel;
  min_price?: number;
  max_price?: number;
  flavour_notes?: string[];
  decaf?: boolean;
  page?: number;
  page_size?: number;
}

export interface CoffeeWithListings extends CanonicalBean {
  listings: (BeanListing & { store: Store; variants: ListingVariant[] })[];
  min_price_gbp: number | null;
  max_price_gbp: number | null;
  store_count: number;
}
