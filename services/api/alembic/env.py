"""
Alembic migration environment — FIXED VERSION.

Uses a synchronous psycopg2 connection for migrations.
The DATABASE_URL in settings uses asyncpg; this file swaps the driver
to psycopg2 so Alembic can use its standard synchronous engine.

Root cause of original bug:
  async_engine_from_config + psycopg2 URL →
  "asyncio extension requires an async driver"

Fix: use synchronous engine_from_config with psycopg2 URL.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Base
from app.core.config import settings
import app.models  # noqa: F401 — registers all models against Base.metadata

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    """
    Convert asyncpg URL → psycopg2 URL for synchronous Alembic migrations.
    postgresql+asyncpg://... → postgresql+psycopg2://...
    """
    url = settings.DATABASE_URL
    return url.replace("+asyncpg", "+psycopg2")


# ── Offline migrations ────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Generate SQL without a live connection."""
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations ─────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """Run migrations against a live database using synchronous psycopg2."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling for migration runs
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
