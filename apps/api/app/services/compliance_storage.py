# ruff: noqa: E501
"""Storage abstraction for compliance source snapshots (raw + extracted text).

Current backend: local filesystem under COMPLIANCE_STORAGE_PATH.

FUTURE AWS MAPPING:
  local filesystem  -> S3 / Cloudflare R2 bucket (swap LocalComplianceStorage for an S3 impl)
  get_download_url  -> presigned S3 URL
  COMPLIANCE_STORAGE_PATH -> S3 bucket/prefix
The interface (save_file / read_file / get_download_url / delete_file) is kept stable
so only this module changes when moving to object storage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.settings import get_settings


class ComplianceStorage(ABC):
    @abstractmethod
    def save_file(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    def read_file(self, key: str) -> bytes: ...

    @abstractmethod
    def get_download_url(self, key: str) -> str: ...

    @abstractmethod
    def delete_file(self, key: str) -> None: ...


class LocalComplianceStorage(ComplianceStorage):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent traversal; keys are slash-delimited logical paths.
        safe = key.replace("\\", "/").lstrip("/")
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key.")
        return path

    def save_file(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read_file(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def get_download_url(self, key: str) -> str:
        # Local dev returns a file:// URL; production returns a presigned HTTPS URL.
        return self._path(key).as_uri()

    def delete_file(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


_backend: ComplianceStorage | None = None


def get_compliance_storage() -> ComplianceStorage:
    global _backend
    if _backend is not None:
        return _backend
    settings = get_settings()
    # settings.compliance_storage_backend == "local" for now; "s3"/"r2" plug in here later.
    _backend = LocalComplianceStorage(settings.compliance_storage_path)
    return _backend


def reset_compliance_storage() -> None:
    """Test hook: clear the cached backend so a new path takes effect."""
    global _backend
    _backend = None
