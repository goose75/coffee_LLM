/**
 * Typed API client — covers all admin endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN = `${API_BASE}/api/v1/admin`;

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${ADMIN}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? b.message ?? detail; } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export interface Paginated<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// Sources
export interface SourcePage { id: string; url: string; page_type: string; parser_strategy: string; discovered_at: string; last_fetched_at: string | null; status_code: number | null; changed_flag: boolean; }
export interface LastRunSummary { id: string; status: "running" | "completed" | "partial" | "failed"; started_at: string; completed_at: string | null; records_seen: number; records_created: number; records_updated: number; error_count: number; warning_count: number; top_errors: string[]; top_error_buckets: Record<string, number>; }
export interface Store { id: string; name: string; domain: string; homepage_url: string; source_type: string; parser_strategy: string; country_code: string; uk_region: string | null; roaster_flag: boolean; cafe_flag: boolean; ecommerce_flag: boolean; active_flag: boolean; crawl_frequency_hours: number; last_successful_crawl_at: string | null; created_at: string; updated_at: string; health_status: "healthy" | "degraded" | "failing" | "stale" | "unknown" | "inactive" | "no_pipeline"; last_run: LastRunSummary | null; }
export interface StoreDetail extends Store { source_pages: SourcePage[]; }
export interface PaginatedStores extends Paginated<Store> { filters_applied: Record<string, unknown>; }
export interface ImportReport { total: number; inserted: number; updated: number; failed: number; unreachable: number; strategies: Record<string, number>; errors: Array<{ domain?: string; error: string }>; }
export interface RescanResult { domain: string; parser_strategy: string; reachable: boolean; pages_upserted: number; signals: string[]; }
export interface SourceFilters { active_only?: boolean; parser_strategy?: string; source_type?: string; roaster_only?: boolean; uk_region?: string; health_status?: string; q?: string; page?: number; page_size?: number; }

export const getSources = (f: SourceFilters = {}) => { const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); }); return apiFetch<PaginatedStores>(`/sources${p.toString() ? `?${p}` : ""}`); };
export const getSource = (id: string) => apiFetch<StoreDetail>(`/sources/${id}`);
export const rescanSource = (id: string) => apiFetch<RescanResult>(`/sources/${id}/rescan`, { method: "POST" });
export const importSeed = () => apiFetch<ImportReport>("/sources/import/seed", { method: "POST" });
export const triggerIngest = (id: string) => apiFetch<Record<string, unknown>>(`/sources/${id}/ingest`, { method: "POST" });
export const triggerReingestionAll = () => apiFetch<{ status: string; message: string; started_count?: number }>("/sources/reingest-all", { method: "POST" });

// Ingestion runs
export interface IngestionRun { id: string; run_type: string; store_id: string | null; started_at: string; completed_at: string | null; status: string; records_seen: number; records_created: number; records_updated: number; records_unchanged: number; pages_fetched: number; pages_failed: number; warning_count: number; error_count: number; duration_seconds: number | null; warnings: Array<{ message: string; url?: string; detail?: string }>; errors: Array<{ message: string; url?: string; detail?: string }>; }
export interface IngestionFilters { store_id?: string; status?: string; run_type?: string; page?: number; page_size?: number; }
export const getIngestionRuns = (f: IngestionFilters = {}) => { const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); }); return apiFetch<Paginated<IngestionRun>>(`/ingestion-runs${p.toString() ? `?${p}` : ""}`); };
export const getIngestionRun = (id: string) => apiFetch<IngestionRun>(`/ingestion-runs/${id}`);

// Extractions
export interface RawExtraction { id: string; source_page_id: string; extraction_method: string; model_name: string | null; prompt_version: string | null; extracted_payload: Record<string, unknown>; confidence_score: number; validation_status: string; validation_errors: { errors: string[] } | null; created_at: string; }
export const getExtractionFailures = (page = 1, page_size = 30) => apiFetch<Paginated<RawExtraction>>(`/extractions/failures?page=${page}&page_size=${page_size}`);
export const getExtraction = (id: string) => apiFetch<RawExtraction>(`/extractions/${id}`);

// Canonical beans
export interface ListingVariant { id: string; variant_title_raw: string; weight_g: number | null; grind_type: string; price_gbp: number; price_per_100g_gbp: number | null; availability_status: string; sku: string | null; recorded_at: string; }
export interface CanonicalBean { id: string; canonical_name: string; origin_country: string | null; origin_region: string | null; farm_or_estate: string | null; washing_station: string | null; producer: string | null; varietal: string[]; process: string | null; process_detail: string | null; altitude_masl_min: number | null; altitude_masl_max: number | null; harvest_year: number | null; roast_level: string | null; flavour_notes: string[]; decaf_flag: boolean; espresso_suitable_flag: boolean; filter_suitable_flag: boolean; data_completeness_score: number; created_at: string; updated_at: string; }
export interface BeanFilters { q?: string; origin_country?: string; process?: string; roast_level?: string; page?: number; page_size?: number; }
export const getCanonicalBeans = (f: BeanFilters = {}) => { const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); }); return apiFetch<Paginated<CanonicalBean>>(`/beans${p.toString() ? `?${p}` : ""}`); };
export const getCanonicalBean = (id: string) => apiFetch<CanonicalBean>(`/beans/${id}`);
export const updateCanonicalBean = (id: string, data: Partial<CanonicalBean>) => apiFetch<CanonicalBean>(`/beans/${id}`, { method: "PATCH", body: JSON.stringify(data) });

// Matches
export interface BeanListingSummary { id: string; raw_title: string; raw_description: string | null; origin_label_raw: string | null; process_label_raw: string | null; roast_label_raw: string | null; varietal_label_raw: string | null; store_id: string; first_seen_at: string; }
export interface CanonicalBeanSummary { id: string; canonical_name: string; origin_country: string | null; origin_region: string | null; farm_or_estate: string | null; process: string | null; roast_level: string | null; varietal: string[]; flavour_notes: string[]; harvest_year: number | null; data_completeness_score: number; }
export interface MatchSignals { exact_score: number; fuzzy_score: number; embedding_score: number; harvest_score: number; field_matches: Record<string, boolean | null>; combined: number; }
export interface CanonicalMatch { id: string; bean_listing_id: string; proposed_canonical_bean_id: string; match_method: string; confidence_score: number; accepted_by_system_flag: boolean; reviewed_by_user_id: string | null; review_status: string; review_notes: string | null; reviewed_at: string | null; created_at: string; match_signals: MatchSignals | null; confidence_band: string; bean_listing: BeanListingSummary | null; proposed_canonical_bean: CanonicalBeanSummary | null; }
export interface PaginatedMatches extends Paginated<CanonicalMatch> { pending_count: number; }
export interface MatchFilters { status?: string; match_method?: string; min_confidence?: number; max_confidence?: number; page?: number; page_size?: number; }
export const getMatches = (f: MatchFilters = {}) => { const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); }); return apiFetch<PaginatedMatches>(`/review/matches${p.toString() ? `?${p}` : ""}`); };
export const acceptMatch = (id: string, notes?: string) => apiFetch(`/review/matches/${id}/accept`, { method: "POST", body: JSON.stringify({ notes }) });
export const rejectMatch = (id: string, notes?: string) => apiFetch(`/review/matches/${id}/reject`, { method: "POST", body: JSON.stringify({ notes }) });

// Bulk review
export interface BulkReviewRequest { match_ids?: string[]; min_confidence?: number; max_confidence?: number; match_method?: string; notes?: string; user_id?: string; limit?: number; }
export interface BulkReviewResponse { outcome: "accepted" | "rejected"; affected: number; skipped: string[]; }
export const bulkAcceptMatches = (req: BulkReviewRequest) => apiFetch<BulkReviewResponse>("/review/matches/bulk-accept", { method: "POST", body: JSON.stringify(req) });
export const bulkRejectMatches = (req: BulkReviewRequest) => apiFetch<BulkReviewResponse>("/review/matches/bulk-reject", { method: "POST", body: JSON.stringify(req) });

// Review analytics
export interface HistogramBin { bin_label: string; bin_min: number; bin_max: number; count: number; }
export interface FieldCoverage { field: string; matched: number; mismatched: number; skipped: number; }
export interface TopBlocker { label: string; count: number; description: string; }
export interface ReviewAnalytics {
  pending_count: number;
  accepted_count: number;
  rejected_count: number;
  pending_confidence_histogram: HistogramBin[];
  exact_score_histogram: HistogramBin[];
  fuzzy_score_histogram: HistogramBin[];
  embedding_score_histogram: HistogramBin[];
  field_coverage: FieldCoverage[];
  method_breakdown: Record<string, number>;
  top_blockers: TopBlocker[];
  catalogue_completeness_histogram: HistogramBin[];
  canonical_bean_count: number;
  avg_canonical_completeness: number;
}
export const getReviewAnalytics = () => apiFetch<ReviewAnalytics>("/review/analytics");

// Data quality
export interface FieldDisagreement { field: string; canonical_value: string | null; listing_majority_value: string | null; listings_disagreeing: number; total_listings: number; }
export interface DataQualityIssue { issue_type: "field_disagreement" | "duplicate_suspect" | "stale_auto_accept" | "very_sparse"; bean_id: string; canonical_name: string; severity: "low" | "medium" | "high"; summary: string; field_disagreements: FieldDisagreement[]; duplicate_of_bean_id: string | null; duplicate_of_name: string | null; stale_match_id: string | null; }
export interface DataQualityReport { issues: DataQualityIssue[]; counts_by_type: Record<string, number>; total: number; }
export const getDataQuality = () => apiFetch<DataQualityReport>("/review/data-quality");

// Field enhancement
export interface FieldSuggestion { field: string; current_value: string | null; suggested_value: string | null; confidence: number; source_summary: string; }
export interface EnhancementProposal { bean_id: string; canonical_name: string; current_completeness: number; listings_considered: number; suggestions: FieldSuggestion[]; notes: string | null; }
export interface EnhancementApplyResponse { bean_id: string; fields_updated: string[]; new_completeness: number; }
export interface BulkEnhancementSummary { beans_examined: number; beans_updated: number; fields_updated_total: number; skipped_no_listings: number; skipped_no_suggestions: number; errors: string[]; }
export const previewEnhancement = (beanId: string) => apiFetch<EnhancementProposal>(`/beans/${beanId}/enhance/preview`);
export const applyEnhancement = (beanId: string, accepted_fields: string[]) => apiFetch<EnhancementApplyResponse>(`/beans/${beanId}/enhance/apply`, { method: "POST", body: JSON.stringify({ accepted_fields }) });
export const bulkEnhance = (params: { max_completeness?: number; limit?: number; auto_apply_threshold?: number } = {}) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null) p.set(k, String(v)); });
  return apiFetch<BulkEnhancementSummary>(`/beans/enhance/bulk${p.toString() ? `?${p}` : ""}`, { method: "POST" });
};

// Merge canonical beans
export interface MergeRequest { source_bean_id: string; target_bean_id: string; delete_source?: boolean; }
export interface MergeResult { target_bean_id: string; relinked_listings: number; relinked_matches: number; fields_copied: string[]; source_deleted: boolean; }
export const mergeBeans = (req: MergeRequest) => apiFetch<MergeResult>("/beans/merge", { method: "POST", body: JSON.stringify(req) });

// Mappings
export interface Mapping { id: string; mapping_type: string; raw_value: string; normalised_value: string; confidence_score: number; source: string; created_at: string; updated_at: string; }
export interface VocabSummary { mapping_type: string; count: number; valid_values: string[]; }
export interface MappingFilters { mapping_type?: string; q?: string; source?: string; page?: number; page_size?: number; }
export const getMappings = (f: MappingFilters = {}) => { const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => { if (v != null && v !== "") p.set(k, String(v)); }); return apiFetch<Paginated<Mapping>>(`/mappings${p.toString() ? `?${p}` : ""}`); };
export const getVocabSummary = () => apiFetch<VocabSummary[]>("/mappings/vocab");
export const createMapping = (data: Omit<Mapping, "id" | "created_at" | "updated_at">) => apiFetch<Mapping>("/mappings", { method: "POST", body: JSON.stringify(data) });
export const updateMapping = (id: string, data: Partial<Mapping>) => apiFetch<Mapping>(`/mappings/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteMapping = (id: string) => apiFetch(`/mappings/${id}`, { method: "DELETE" });
export const normaliseValue = (raw_value: string, mapping_type: string) => apiFetch<{ raw_value: string; normalised_value: string; confidence: number; source: string; is_unknown: boolean }>("/mappings/normalise", { method: "POST", body: JSON.stringify({ raw_value, mapping_type }) });
