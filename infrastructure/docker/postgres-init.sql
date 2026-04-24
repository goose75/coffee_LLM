-- Run once on first container start, before Alembic migrations.
-- Alembic also runs CREATE EXTENSION IF NOT EXISTS, so this is belt-and-braces.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
