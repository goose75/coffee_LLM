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
    const timeout = isRailway ? 60000 : 10000; // 60s on Railway, 10s locally

    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 5,
      min: isRailway ? 0 : 1, // Don't maintain min connections on Railway (stateless)
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: timeout,
      ssl: isRailway ? { rejectUnauthorized: false } : false, // Railway requires SSL
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
    console.log("Executed query", { text, duration, rows: result.rowCount });
    return result;
  } catch (error) {
    console.error("Database query error", { text, error });
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
