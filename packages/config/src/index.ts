// ─── API Endpoints ────────────────────────────────────────────────────────────

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Ingestion Config ─────────────────────────────────────────────────────────

export const INGESTION_CONFIG = {
  shopify: {
    productsPerPage: 250,
    requestTimeoutMs: 15_000,
    retryAttempts: 3,
    retryDelayMs: 2_000,
  },
  html: {
    requestTimeoutMs: 20_000,
    maxPageSizeBytes: 5 * 1024 * 1024, // 5MB
  },
  llm: {
    maxInputTokens: 8_000,
    maxOutputTokens: 1_000,
    promptVersion: "v1.0.0",
  },
} as const;

// ─── Entity Resolution Thresholds ─────────────────────────────────────────────

export const CONFIDENCE_THRESHOLDS = {
  autoAccept: 0.92,
  reviewQueue: 0.75,
  // Below reviewQueue → create new canonical bean
} as const;

// ─── Crawl Defaults ───────────────────────────────────────────────────────────

export const CRAWL_DEFAULTS = {
  frequencyHours: 24,
  activeStoreFrequencyHours: 12,
  sitemapCheckFrequencyHours: 168, // weekly
} as const;

// ─── Controlled Vocabulary Labels ─────────────────────────────────────────────

export const ROAST_LEVEL_LABELS: Record<string, string> = {
  light: "Light",
  medium_light: "Medium Light",
  medium: "Medium",
  medium_dark: "Medium Dark",
  dark: "Dark",
  unknown: "Unknown",
};

export const GRIND_TYPE_LABELS: Record<string, string> = {
  whole_bean: "Whole Bean",
  espresso: "Espresso",
  filter: "Filter",
  cafetiere: "Cafetière",
  moka: "Moka Pot",
  aeropress: "AeroPress",
  pour_over: "Pour Over",
  omni: "Omni Grind",
  unknown: "Unknown",
};

export const PROCESS_LABELS: Record<string, string> = {
  washed: "Washed",
  natural: "Natural",
  honey: "Honey",
  anaerobic: "Anaerobic",
  wet_hulled: "Wet Hulled",
  carbonic_maceration: "Carbonic Maceration",
  experimental: "Experimental",
  unknown: "Unknown",
};

// ─── Pagination ───────────────────────────────────────────────────────────────

export const PAGINATION = {
  defaultPageSize: 24,
  maxPageSize: 100,
  adminDefaultPageSize: 50,
} as const;
