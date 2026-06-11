"""Application configuration — reads from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = True
    AUTO_CREATE_TABLES: bool = False  # Use Alembic in production

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://coffee:coffee@localhost:5432/coffee_platform"
    DATABASE_POOL_SIZE: int = 20            # Increased from 10 to reduce pool exhaustion
    DATABASE_MAX_OVERFLOW: int = 40         # Increased from 20 to handle spikes
    DATABASE_POOL_RECYCLE: int = 3600       # Recycle connections after 1 hour (prevent stale connections)
    DATABASE_POOL_PRE_PING: bool = True     # Test connection before use (catch stale connections)

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",  # public site
        "http://localhost:3001",  # admin app
    ]

    # ── Object Storage ────────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    STORAGE_LOCAL_PATH: str = "./raw_storage"
    AWS_BUCKET_NAME: str = ""
    AWS_REGION: str = "eu-west-2"

    # ── LLM ──────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-1"

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # ── Confidence Thresholds ─────────────────────────────────────────────────
    CONFIDENCE_AUTO_ACCEPT: float = 0.78
    CONFIDENCE_REVIEW_QUEUE: float = 0.55


settings = Settings()
