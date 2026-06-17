import { Pool } from "pg";

// Global pool singleton - ensure only ONE pool instance across all imports
let pool: Pool | null = null;

function getPool(): Pool {
  if (!pool) {
    if (!process.env.DATABASE_URL) {
      throw new Error("DATABASE_URL environment variable is not set");
    }

    // Detect if running on Railway (uses mainline.proxy.rlwy.net)
    const isRailway = process.env.DATABASE_URL?.includes("rlwy.net");
    const timeout = isRailway ? 30000 : 60000; // 60s for cold start, queries themselves are <1s when warm

    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 10,
      min: isRailway ? 0 : 1, // Start with single connection to avoid timeout on pool init
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: timeout,
      ssl: isRailway ? { rejectUnauthorized: false } : false,
    });

    pool.on("error", (err) => {
      console.error("Unexpected error on idle client:", err);
    });
  }
  return pool;
}

export async function query(text: string, params?: unknown[]) {
  const start = Date.now();
  try {
    const p = getPool();
    const result = await p.query(text, params);
    const duration = Date.now() - start;
    if (duration > 1000) {
      console.warn("Slow query detected", { text: text.substring(0, 100), duration, rows: result.rowCount });
    }
    return result;
  } catch (error) {
    const duration = Date.now() - start;
    console.error("Database query error", { text: text.substring(0, 100), duration, error: String(error).substring(0, 200) });
    throw error;
  }
}

export async function getClient() {
  const p = getPool();
  return p.connect();
}

export function getPoolInstance() {
  return getPool();
}
