import { query } from "./db";
import type {
  Coffee,
  StoreListing,
  PriceVariant,
  Roaster,
  Paginated,
  PricePoint,
  VariantPriceHistory,
  BeanPriceHistory,
  SellerListing,
  SellerComparison,
  VariantOffer,
  PriceSummaryStats,
  TasteProfile,
  FlavorFamily,
  TaggedNote,
  SimilarCoffee,
  MarketAverages,
} from "./api";

// ── Coffee Queries ────────────────────────────────────────────────────────

export async function getCoffees(
  params: Record<string, string | number | undefined> = {}
): Promise<Paginated<Coffee>> {
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;
  const offset = (page - 1) * pageSize;
  const search = params.search ? `%${params.search}%` : null;

  let sql = `
    SELECT
      cb.id,
      cb.canonical_name,
      cb.origin_country,
      cb.origin_region,
      cb.farm_or_estate,
      cb.washing_station,
      cb.producer,
      cb.varietal,
      cb.process,
      cb.process_detail,
      cb.altitude_masl_min,
      cb.altitude_masl_max,
      cb.harvest_year,
      cb.roast_level,
      cb.flavour_notes,
      cb.decaf_flag,
      cb.espresso_suitable_flag,
      cb.filter_suitable_flag,
      cb.data_completeness_score,
      COUNT(DISTINCT bl.id) as listing_count,
      MIN(lv.price_gbp) as min_price_gbp,
      MAX(lv.price_gbp) as max_price_gbp,
      MIN(lv.price_per_100g_gbp) as min_price_per_100g_gbp,
      COUNT(DISTINCT s.id) as store_count,
      MAX(bl.last_seen_at) as newest_listing_at
    FROM canonical_beans cb
    LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
    LEFT JOIN listing_variants lv ON bl.id = lv.bean_listing_id
    LEFT JOIN stores s ON bl.store_id = s.id
    WHERE bl.id IS NOT NULL
  `;

  const params_array: unknown[] = [];

  if (search) {
    sql += ` AND (cb.canonical_name ILIKE $${params_array.length + 1}
                   OR cb.origin_country ILIKE $${params_array.length + 1})`;
    params_array.push(search);
  }

  sql += ` GROUP BY cb.id ORDER BY cb.canonical_name ASC LIMIT $${params_array.length + 1} OFFSET $${params_array.length + 2}`;
  params_array.push(pageSize, offset);

  // Get total count
  let countSql = `SELECT COUNT(DISTINCT cb.id) as count FROM canonical_beans cb
                   LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
                   WHERE bl.id IS NOT NULL`;
  if (search) {
    countSql += ` AND (cb.canonical_name ILIKE $1 OR cb.origin_country ILIKE $1)`;
  }

  const countResult = await query(countSql, search ? [search] : []);
  const total = Number(countResult.rows[0]?.count) || 0;

  const result = await query(sql, params_array);

  const data: Coffee[] = result.rows.map((row) => ({
    id: row.id,
    canonical_name: row.canonical_name,
    origin_country: row.origin_country,
    origin_region: row.origin_region,
    farm_or_estate: row.farm_or_estate,
    washing_station: row.washing_station,
    producer: row.producer,
    varietal: row.varietal || [],
    process: row.process,
    process_detail: row.process_detail,
    altitude_masl_min: row.altitude_masl_min,
    altitude_masl_max: row.altitude_masl_max,
    harvest_year: row.harvest_year,
    roast_level: row.roast_level,
    flavour_notes: row.flavour_notes || [],
    decaf_flag: row.decaf_flag,
    espresso_suitable_flag: row.espresso_suitable_flag,
    filter_suitable_flag: row.filter_suitable_flag,
    data_completeness_score: row.data_completeness_score,
    listing_count: Number(row.listing_count),
    min_price_gbp: row.min_price_gbp ? Number(row.min_price_gbp) : null,
    max_price_gbp: row.max_price_gbp ? Number(row.max_price_gbp) : null,
    min_price_per_100g_gbp: row.min_price_per_100g_gbp
      ? Number(row.min_price_per_100g_gbp)
      : null,
    store_count: Number(row.store_count),
    newest_listing_at: row.newest_listing_at,
  }));

  return {
    data,
    total,
    page,
    page_size: pageSize,
    has_next: offset + pageSize < total,
  };
}

export async function getCoffee(id: string): Promise<Coffee> {
  const result = await query(
    `
    SELECT
      cb.id,
      cb.canonical_name,
      cb.origin_country,
      cb.origin_region,
      cb.farm_or_estate,
      cb.washing_station,
      cb.producer,
      cb.varietal,
      cb.process,
      cb.process_detail,
      cb.altitude_masl_min,
      cb.altitude_masl_max,
      cb.harvest_year,
      cb.roast_level,
      cb.flavour_notes,
      cb.decaf_flag,
      cb.espresso_suitable_flag,
      cb.filter_suitable_flag,
      cb.data_completeness_score,
      COUNT(DISTINCT bl.id) as listing_count,
      MIN(lv.price_gbp) as min_price_gbp,
      MAX(lv.price_gbp) as max_price_gbp,
      MIN(lv.price_per_100g_gbp) as min_price_per_100g_gbp,
      COUNT(DISTINCT s.id) as store_count
    FROM canonical_beans cb
    LEFT JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
    LEFT JOIN listing_variants lv ON bl.id = lv.bean_listing_id
    LEFT JOIN stores s ON bl.store_id = s.id
    WHERE cb.id = $1
    GROUP BY cb.id
  `,
    [id]
  );

  if (result.rows.length === 0) {
    throw new Error(`Coffee ${id} not found`);
  }

  const row = result.rows[0];
  return {
    id: row.id,
    canonical_name: row.canonical_name,
    origin_country: row.origin_country,
    origin_region: row.origin_region,
    farm_or_estate: row.farm_or_estate,
    washing_station: row.washing_station,
    producer: row.producer,
    varietal: row.varietal || [],
    process: row.process,
    process_detail: row.process_detail,
    altitude_masl_min: row.altitude_masl_min,
    altitude_masl_max: row.altitude_masl_max,
    harvest_year: row.harvest_year,
    roast_level: row.roast_level,
    flavour_notes: row.flavour_notes || [],
    decaf_flag: row.decaf_flag,
    espresso_suitable_flag: row.espresso_suitable_flag,
    filter_suitable_flag: row.filter_suitable_flag,
    data_completeness_score: row.data_completeness_score,
    listing_count: Number(row.listing_count),
    min_price_gbp: row.min_price_gbp ? Number(row.min_price_gbp) : null,
    max_price_gbp: row.max_price_gbp ? Number(row.max_price_gbp) : null,
    min_price_per_100g_gbp: row.min_price_per_100g_gbp
      ? Number(row.min_price_per_100g_gbp)
      : null,
    store_count: Number(row.store_count),
  };
}

export async function compareCoffee(
  id: string
): Promise<Coffee & { listings: StoreListing[] }> {
  const coffee = await getCoffee(id);

  const listingsResult = await query(
    `
    SELECT
      bl.id,
      bl.store_id,
      s.name as store_name,
      s.domain as store_domain,
      bl.raw_title,
      bl.product_url,
      bl.listing_status,
      bl.active_flag,
      json_agg(
        json_build_object(
          'id', lv.id,
          'weight_g', lv.weight_g,
          'grind_type', lv.grind_type,
          'price_gbp', lv.price_gbp,
          'price_per_100g_gbp', lv.price_per_100g_gbp,
          'availability_status', lv.availability_status,
          'sku', lv.sku
        ) ORDER BY lv.weight_g, lv.grind_type
      ) as variants,
      MIN(lv.price_gbp) as min_price_gbp,
      MAX(lv.price_gbp) as max_price_gbp
    FROM bean_listings bl
    JOIN stores s ON bl.store_id = s.id
    LEFT JOIN listing_variants lv ON bl.id = lv.bean_listing_id
    WHERE bl.canonical_bean_id = $1
    GROUP BY bl.id, s.id
    ORDER BY s.name
  `,
    [id]
  );

  const listings: StoreListing[] = listingsResult.rows.map((row) => ({
    id: row.id,
    store_id: row.store_id,
    store_name: row.store_name,
    store_domain: row.store_domain,
    raw_title: row.raw_title,
    product_url: row.product_url,
    listing_status: row.listing_status,
    active_flag: row.active_flag,
    variants: (row.variants || []).map((v: unknown) => {
      const variant = v as Record<string, unknown>;
      return {
        id: variant.id as string,
        weight_g: variant.weight_g as number | null,
        grind_type: variant.grind_type as string,
        price_gbp: Number(variant.price_gbp),
        price_per_100g_gbp: variant.price_per_100g_gbp
          ? Number(variant.price_per_100g_gbp)
          : null,
        availability_status: variant.availability_status as string,
        sku: variant.sku as string | null,
      };
    }),
    min_price_gbp: row.min_price_gbp ? Number(row.min_price_gbp) : null,
    max_price_gbp: row.max_price_gbp ? Number(row.max_price_gbp) : null,
  }));

  return { ...coffee, listings };
}

// ── Roaster Queries ──────────────────────────────────────────────────────

export async function getRoasters(
  params: Record<string, string | number | undefined> = {}
): Promise<Paginated<Roaster>> {
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;
  const offset = (page - 1) * pageSize;

  const result = await query(
    `
    SELECT
      s.id,
      s.name,
      s.domain,
      s.homepage_url,
      s.uk_region,
      s.roaster_flag,
      s.cafe_flag,
      s.active_flag,
      COUNT(DISTINCT bl.id) as listing_count
    FROM stores s
    LEFT JOIN bean_listings bl ON s.id = bl.store_id
    WHERE s.roaster_flag = true AND s.active_flag = true
    GROUP BY s.id
    ORDER BY s.name ASC
    LIMIT $1 OFFSET $2
  `,
    [pageSize, offset]
  );

  const countResult = await query(
    `SELECT COUNT(*) as count FROM stores WHERE roaster_flag = true AND active_flag = true`
  );
  const total = Number(countResult.rows[0]?.count) || 0;

  const data: Roaster[] = result.rows.map((row) => ({
    id: row.id,
    name: row.name,
    domain: row.domain,
    homepage_url: row.homepage_url,
    uk_region: row.uk_region,
    roaster_flag: row.roaster_flag,
    cafe_flag: row.cafe_flag,
    active_flag: row.active_flag,
    listing_count: Number(row.listing_count),
  }));

  return {
    data,
    total,
    page,
    page_size: pageSize,
    has_next: offset + pageSize < total,
  };
}

// ── New Releases Queries ──────────────────────────────────────────────────

export async function getNewReleases(
  params: Record<string, string | number | undefined> = {}
): Promise<Paginated<Coffee>> {
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;
  const offset = (page - 1) * pageSize;
  const daysAgo = Number(params.days) || 30;

  let sql = `
    SELECT DISTINCT
      cb.id,
      cb.canonical_name,
      cb.origin_country,
      cb.origin_region,
      cb.farm_or_estate,
      cb.washing_station,
      cb.producer,
      cb.varietal,
      cb.process,
      cb.process_detail,
      cb.altitude_masl_min,
      cb.altitude_masl_max,
      cb.harvest_year,
      cb.roast_level,
      cb.flavour_notes,
      cb.decaf_flag,
      cb.espresso_suitable_flag,
      cb.filter_suitable_flag,
      cb.data_completeness_score,
      COUNT(DISTINCT bl.id) as listing_count,
      MIN(lv.price_gbp) as min_price_gbp,
      MAX(lv.price_gbp) as max_price_gbp,
      MIN(lv.price_per_100g_gbp) as min_price_per_100g_gbp,
      COUNT(DISTINCT s.id) as store_count,
      MAX(bl.last_seen_at) as newest_listing_at
    FROM canonical_beans cb
    JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
    LEFT JOIN listing_variants lv ON bl.id = lv.bean_listing_id
    LEFT JOIN stores s ON bl.store_id = s.id
    WHERE bl.first_seen_at >= NOW() - INTERVAL '1 day' * $1
    GROUP BY cb.id
    ORDER BY newest_listing_at DESC
    LIMIT $2 OFFSET $3
  `;

  const result = await query(sql, [daysAgo, pageSize, offset]);

  const countSql = `
    SELECT COUNT(DISTINCT cb.id) as count
    FROM canonical_beans cb
    JOIN bean_listings bl ON cb.id = bl.canonical_bean_id
    WHERE bl.first_seen_at >= NOW() - INTERVAL '1 day' * $1
  `;
  const countResult = await query(countSql, [daysAgo]);
  const total = Number(countResult.rows[0]?.count) || 0;

  const data: Coffee[] = result.rows.map((row) => ({
    id: row.id,
    canonical_name: row.canonical_name,
    origin_country: row.origin_country,
    origin_region: row.origin_region,
    farm_or_estate: row.farm_or_estate,
    washing_station: row.washing_station,
    producer: row.producer,
    varietal: row.varietal || [],
    process: row.process,
    process_detail: row.process_detail,
    altitude_masl_min: row.altitude_masl_min,
    altitude_masl_max: row.altitude_masl_max,
    harvest_year: row.harvest_year,
    roast_level: row.roast_level,
    flavour_notes: row.flavour_notes || [],
    decaf_flag: row.decaf_flag,
    espresso_suitable_flag: row.espresso_suitable_flag,
    filter_suitable_flag: row.filter_suitable_flag,
    data_completeness_score: row.data_completeness_score,
    listing_count: Number(row.listing_count),
    min_price_gbp: row.min_price_gbp ? Number(row.min_price_gbp) : null,
    max_price_gbp: row.max_price_gbp ? Number(row.max_price_gbp) : null,
    min_price_per_100g_gbp: row.min_price_per_100g_gbp
      ? Number(row.min_price_per_100g_gbp)
      : null,
    store_count: Number(row.store_count),
    newest_listing_at: row.newest_listing_at,
  }));

  return {
    data,
    total,
    page,
    page_size: pageSize,
    has_next: offset + pageSize < total,
  };
}

// ── Placeholder functions for advanced features ──────────────────────────

export async function getMarketAverages(): Promise<MarketAverages> {
  const result = await query(`
    SELECT
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lv.price_per_100g_gbp) as median_per_100g_gbp,
      AVG(lv.price_per_100g_gbp) as mean_per_100g_gbp,
      MIN(lv.price_per_100g_gbp) as min_per_100g_gbp,
      MAX(lv.price_per_100g_gbp) as max_per_100g_gbp,
      COUNT(*) as sample_size
    FROM listing_variants lv
    WHERE lv.price_per_100g_gbp IS NOT NULL
  `);

  const row = result.rows[0];
  return {
    median_per_100g_gbp: row.median_per_100g_gbp
      ? Number(row.median_per_100g_gbp)
      : null,
    mean_per_100g_gbp: row.mean_per_100g_gbp
      ? Number(row.mean_per_100g_gbp)
      : null,
    min_per_100g_gbp: row.min_per_100g_gbp
      ? Number(row.min_per_100g_gbp)
      : null,
    max_per_100g_gbp: row.max_per_100g_gbp
      ? Number(row.max_per_100g_gbp)
      : null,
    sample_size: Number(row.sample_size),
  };
}

// Price, taste, and comparison functions return empty/placeholder data for now
export async function getPriceHistory(): Promise<BeanPriceHistory> {
  return {
    bean_id: "",
    canonical_name: "",
    variants: [],
    min_current_price_gbp: null,
    min_current_per_100g: null,
  };
}

export async function getPriceCompare(): Promise<SellerComparison> {
  return {
    bean_id: "",
    canonical_name: "",
    stores: [],
    best_price_gbp: null,
    best_price_per_100g: null,
  };
}

export async function getPriceStats(): Promise<PriceSummaryStats[]> {
  return [];
}

export async function getTasteProfile(): Promise<TasteProfile> {
  return {
    bean_id: "",
    canonical_name: "",
    raw_notes: [],
    families: [],
    has_structured_tags: false,
    tag_count: 0,
  };
}

export async function getSimilarCoffees(): Promise<SimilarCoffee[]> {
  return [];
}
