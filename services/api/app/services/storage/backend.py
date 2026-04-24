"""
Object storage abstraction.

Provides a unified StorageBackend interface regardless of whether we're
writing to local disk (dev) or S3 (production). The backend is selected
from settings.STORAGE_BACKEND at import time.

Storage path convention:
  raw/{source_type}/{store_domain}/{YYYY-MM-DD}/{filename}

e.g.:
  raw/shopify/shop.squaremilecoffee.com/2025-01-15/products_page_1.json
  raw/shopify/shop.squaremilecoffee.com/2025-01-15/products_full.json

The path is stored in source_pages.raw_storage_path so any audit trail
can retrieve the original payload at any time.
"""

from __future__ import annotations

import abc
import gzip
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class StorageBackend(abc.ABC):
    """Common interface for raw payload storage."""

    @abc.abstractmethod
    async def write(self, path: str, data: bytes, compress: bool = True) -> str:
        """Write bytes to storage. Returns the canonical storage path."""

    @abc.abstractmethod
    async def read(self, path: str) -> bytes:
        """Read bytes from storage. Decompresses automatically."""

    @abc.abstractmethod
    async def exists(self, path: str) -> bool:
        """Check whether a path exists."""

    def build_path(
        self,
        store_domain: str,
        source_type: str,
        filename: str,
        date: datetime | None = None,
    ) -> str:
        """Build a canonical storage path from components."""
        d = (date or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        # Sanitise domain for use as a path component
        safe_domain = store_domain.replace("/", "_").replace(":", "_")
        return f"raw/{source_type}/{safe_domain}/{d}/{filename}"


# ── Local filesystem backend ──────────────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    """
    Stores files on the local filesystem under base_dir.
    Used in development and CI. Thread-safe via Python's GIL for writes.
    """

    def __init__(self, base_dir: str = "./raw_storage") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def write(self, path: str, data: bytes, compress: bool = True) -> str:
        full_path = self.base_dir / path
        if compress and not path.endswith(".gz"):
            full_path = Path(str(full_path) + ".gz")
            path = path + ".gz"

        full_path.parent.mkdir(parents=True, exist_ok=True)

        if compress:
            compressed = gzip.compress(data, compresslevel=6)
            full_path.write_bytes(compressed)
            log.debug(
                "Wrote %s → %s (%d → %d bytes, %.0f%% reduction)",
                path, full_path, len(data), len(compressed),
                (1 - len(compressed) / len(data)) * 100 if data else 0,
            )
        else:
            full_path.write_bytes(data)

        return path

    async def read(self, path: str) -> bytes:
        full_path = self.base_dir / path
        if not full_path.exists() and not path.endswith(".gz"):
            gz_path = self.base_dir / (path + ".gz")
            if gz_path.exists():
                full_path = gz_path

        data = full_path.read_bytes()
        if str(full_path).endswith(".gz"):
            return gzip.decompress(data)
        return data

    async def exists(self, path: str) -> bool:
        return (self.base_dir / path).exists() or (self.base_dir / (path + ".gz")).exists()


# ── S3 backend ────────────────────────────────────────────────────────────────

class S3StorageBackend(StorageBackend):
    """
    Stores files in an S3-compatible bucket.
    Requires boto3. Lazy-imported so the local backend works without it.
    """

    def __init__(self, bucket: str, region: str = "eu-west-2") -> None:
        import boto3  # type: ignore
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    async def write(self, path: str, data: bytes, compress: bool = True) -> str:
        import asyncio
        key = path
        body = data
        content_encoding = None

        if compress:
            body = gzip.compress(data, compresslevel=6)
            content_encoding = "gzip"
            if not key.endswith(".gz"):
                key = key + ".gz"

        extra_args: dict = {"ContentType": "application/json"}
        if content_encoding:
            extra_args["ContentEncoding"] = content_encoding

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, **extra_args),
        )
        log.debug("S3 write: s3://%s/%s (%d bytes)", self.bucket, key, len(body))
        return key

    async def read(self, path: str) -> bytes:
        import asyncio
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3.get_object(Bucket=self.bucket, Key=path),
        )
        body = response["Body"].read()
        encoding = response.get("ContentEncoding", "")
        if encoding == "gzip" or path.endswith(".gz"):
            return gzip.decompress(body)
        return body

    async def exists(self, path: str) -> bool:
        import asyncio
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3.head_object(Bucket=self.bucket, Key=path),
            )
            return True
        except Exception:
            return False


# ── Factory ───────────────────────────────────────────────────────────────────

def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend from settings."""
    from app.core.config import settings

    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket=settings.AWS_BUCKET_NAME,
            region=settings.AWS_REGION,
        )
    return LocalStorageBackend(base_dir=settings.STORAGE_LOCAL_PATH)


# ── Content hashing ───────────────────────────────────────────────────────────

def compute_hash(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes. Used for change detection."""
    return hashlib.sha256(data).hexdigest()
