"""Pluggable file storage — local filesystem (dev) or Cloudflare R2 / S3 (production).

Usage:
    from app.services.storage import storage
    storage.put("documents/tenant_id/logo.png", raw_bytes)
    data = storage.get("documents/tenant_id/logo.png")   # raises FileNotFoundError if absent
    storage.delete("documents/tenant_id/logo.png")
    exists = storage.exists("documents/tenant_id/logo.png")

Backend selection (checked once at import):
  - R2_BUCKET_NAME set in env  →  Cloudflare R2 via boto3 (S3-compatible)
  - Otherwise                  →  local filesystem under settings.upload_dir
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Protocol


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


# ── Local filesystem ─────────────────────────────────────────────────────────

class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str) -> None:
        self._base = base_dir

    def _full(self, key: str) -> str:
        # Prevent path traversal
        safe = os.path.normpath(key).lstrip("/\\")
        return os.path.join(self._base, safe)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._full(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get(self, key: str) -> bytes:
        path = self._full(key)
        if not os.path.exists(path):
            raise FileNotFoundError(key)
        with open(path, "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        path = self._full(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._full(key))


# ── Cloudflare R2 / S3 ───────────────────────────────────────────────────────

class R2Storage(StorageBackend):
    def __init__(self, bucket: str, endpoint_url: str, access_key: str, secret_key: str) -> None:
        import boto3  # type: ignore[import-untyped]
        from botocore.config import Config  # type: ignore[import-untyped]

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from e
            raise

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False


# ── Factory ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _build_backend() -> StorageBackend:
    bucket = os.environ.get("R2_BUCKET_NAME", "").strip()
    if bucket:
        account_id = os.environ.get("R2_ACCOUNT_ID", "")
        access_key = os.environ.get("R2_ACCESS_KEY_ID", "")
        secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
        endpoint = os.environ.get(
            "R2_ENDPOINT_URL",
            f"https://{account_id}.r2.cloudflarestorage.com",
        )
        return R2Storage(bucket, endpoint, access_key, secret_key)

    # Fall back to local filesystem
    from app.core.settings import get_settings
    return LocalStorage(get_settings().upload_dir)


class _StorageProxy:
    """Thin proxy so callers use `storage.put(...)` without importing the backend directly."""

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        _build_backend().put(key, data, content_type)

    def get(self, key: str) -> bytes:
        return _build_backend().get(key)

    def delete(self, key: str) -> None:
        _build_backend().delete(key)

    def exists(self, key: str) -> bool:
        return _build_backend().exists(key)


storage = _StorageProxy()
