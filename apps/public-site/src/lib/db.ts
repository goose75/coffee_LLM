import { Pool } from "pg";

// Create a connection pool for the database
let pool: Pool | null = null;

function getPool() {
  if (!pool) {
    if (!process.env.DATABASE_URL) {
      throw new Error("DATABASE_URL environment variable is not set");
    }
    console.log("Creating connection pool with DATABASE_URL:", process.env.DATABASE_URL?.replace(/:[^:]*@/, ":***@"));
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 10,
      min: 0,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 30000,
      statement_timeout: 30000,
      query_timeout: 30000,
    });

    pool.on("error", (err) => {
      console.error("Pool error event:", err);
    });

    pool.on("connect", () => {
      console.log("Pool connection established");
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
