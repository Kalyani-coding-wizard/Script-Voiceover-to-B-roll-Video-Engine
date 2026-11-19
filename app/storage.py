"""Reusable artifact storage for MinIO/S3 and local/mock deployments."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class ArtifactStorage:
    """Stores artifact files locally or in an S3-compatible object store.

    Local mode is intentionally the fallback: mock runs, absent credentials,
    and unavailable MinIO/S3 endpoints still leave downloadable job artifacts.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.local_root = Path("outputs")
        self.bucket = self.settings.s3_bucket
        backend = getattr(self.settings, "artifact_backend", "auto")
        self.backend: Literal["local", "s3"] = (
            "local" if backend == "local" or self.settings.mock_mode else "s3"
            if backend == "s3" else "s3"
        )
        self._client = None

    @property
    def using_s3(self) -> bool:
        return self.backend == "s3"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3/botocore is required for S3 storage") from exc

        kwargs = {
            "aws_access_key_id": self.settings.s3_access_key,
            "aws_secret_access_key": self.settings.s3_secret_key,
            "region_name": getattr(self.settings, "s3_region", "us-east-1"),
            "config": Config(signature_version="s3v4"),
        }
        if self.settings.s3_endpoint:
            kwargs["endpoint_url"] = self.settings.s3_endpoint
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _ensure_bucket(self) -> None:
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket)
        except Exception:
            client.create_bucket(Bucket=self.bucket)

    def _fallback_to_local(self, operation: str, exc: Exception) -> None:
        logger.warning(
            "artifact_storage_s3_unavailable_using_local",
            operation=operation,
            error=str(exc),
        )
        self.backend = "local"

    @staticmethod
    def _object_key(job_id: str, filename: str) -> str:
        return f"{job_id}/{Path(filename).name}"

    def upload_file(self, job_id: str, local_path: str | Path) -> str:
        """Upload an artifact and return its object key."""
        local_path = Path(local_path)
        key = self._object_key(job_id, local_path.name)
        if not local_path.exists():
            raise FileNotFoundError(str(local_path))

        if self.backend == "local":
            destination = self.local_root / job_id / local_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if local_path.resolve() != destination.resolve():
                import shutil
                shutil.copy2(local_path, destination)
            return key

        try:
            self._ensure_bucket()
            self._get_client().upload_file(str(local_path), self.bucket, key)
            return key
        except Exception as exc:
            self._fallback_to_local("upload", exc)
            return self.upload_file(job_id, local_path)

    def download_file(self, job_id: str, filename: str, destination: str | Path) -> Path:
        """Download an artifact to a local path."""
        key = self._object_key(job_id, filename)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if self.backend == "local":
            source = self.local_root / job_id / Path(filename).name
            if not source.exists():
                raise FileNotFoundError(str(source))
            if source.resolve() != destination.resolve():
                import shutil
                shutil.copy2(source, destination)
            return destination

        try:
            self._ensure_bucket()
            self._get_client().download_file(self.bucket, key, str(destination))
            return destination
        except Exception as exc:
            self._fallback_to_local("download", exc)
            return self.download_file(job_id, filename, destination)

    def exists(self, job_id: str, filename: str) -> bool:
        key = self._object_key(job_id, filename)
        if self.backend == "local":
            return (self.local_root / job_id / Path(filename).name).exists()
        try:
            self._ensure_bucket()
            self._get_client().head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            status_code = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status_code == 404:
                return False
            self._fallback_to_local("exists", exc)
            return self.exists(job_id, filename)

    def presigned_url(self, job_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
        if self.backend != "s3":
            return None
        key = self._object_key(job_id, filename)
        try:
            return self._get_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            self._fallback_to_local("presigned_url", exc)
            return None
