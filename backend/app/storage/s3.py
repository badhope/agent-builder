"""S3 / MinIO storage adapter.

Uses ``boto3`` with an async wrapper around the sync client. For
very large files aioboto3 would be preferable, but boto3 is more
mature and easier to operate.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.exceptions import StorageError
from app.logging_config import get_logger
from app.settings import S3Settings
from app.storage.base import ObjectMeta, PresignedUrl, Storage

logger = get_logger(__name__)


class S3Storage(Storage):
    """S3 / MinIO storage adapter.

    Compatible with both AWS S3 and any S3-protocol server (MinIO, etc.).
    """

    backend_name = "s3"

    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url or None,
            region_name=settings.region,
            aws_access_key_id=settings.access_key.get_secret_value() or None,
            aws_secret_access_key=settings.secret_key.get_secret_value() or None,
            use_ssl=settings.use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.addressing_style},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        self._bucket = settings.bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    self._client.create_bucket(Bucket=self._bucket)
                    logger.info("s3.bucket_created", bucket=self._bucket)
                except ClientError as create_exc:
                    logger.warning("s3.bucket_create_failed", error=str(create_exc))
            else:
                logger.warning("s3.head_bucket_failed", error=str(exc))

    # ---- Read ----

    async def get_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_bytes_sync, key)

    def _get_bytes_sync(self, key: str) -> bytes:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise StorageError(f"Object not found: {key}", code="OBJECT_NOT_FOUND") from exc
            raise StorageError(f"S3 get failed: {exc}", code="S3_ERROR") from exc
        return obj["Body"].read()

    async def stream(self, key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        obj = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        body = obj["Body"]
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    async def stat(self, key: str) -> ObjectMeta | None:
        try:
            head = await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                return None
            raise StorageError(f"S3 head failed: {exc}", code="S3_ERROR") from exc
        return ObjectMeta(
            key=key,
            size=int(head.get("ContentLength", 0)),
            content_type=head.get("ContentType"),
            last_modified=head.get("LastModified"),
            etag=head.get("ETag", "").strip('"') or None,
            checksum_sha256=None,
        )

    async def exists(self, key: str) -> bool:
        return (await self.stat(key)) is not None

    # ---- Write ----

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        sha = hashlib.sha256(data).hexdigest()
        try:
            await asyncio.to_thread(self._client.put_object, **kwargs)
        except ClientError as exc:
            raise StorageError(f"S3 put failed: {exc}", code="S3_ERROR") from exc
        return ObjectMeta(
            key=key,
            size=len(data),
            content_type=content_type,
            last_modified=datetime.now(tz=UTC),
            etag=sha,
            checksum_sha256=sha,
        )

    async def put_file(
        self,
        key: str,
        source: Path | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type

        if isinstance(source, Path):
            sha = await asyncio.to_thread(_sha256_of_file, source)
            try:
                await asyncio.to_thread(
                    self._client.upload_file,
                    str(source),
                    self._bucket,
                    key,
                    ExtraArgs=extra,
                )
            except ClientError as exc:
                raise StorageError(f"S3 upload failed: {exc}", code="S3_ERROR") from exc
            size = source.stat().st_size
        else:
            data = source.read()
            sha = hashlib.sha256(data).hexdigest()
            extra["Body"] = data
            try:
                await asyncio.to_thread(self._client.put_object, Bucket=self._bucket, Key=key, **extra)
            except ClientError as exc:
                raise StorageError(f"S3 put failed: {exc}", code="S3_ERROR") from exc
            size = len(data)

        return ObjectMeta(
            key=key,
            size=size,
            content_type=content_type,
            last_modified=datetime.now(tz=UTC),
            etag=sha,
            checksum_sha256=sha,
        )

    async def delete(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            logger.warning("s3.delete_failed", key=key, error=str(exc))
            return False
        return True

    async def delete_many(self, keys: list[str]) -> int:
        if not keys:
            return 0
        try:
            await asyncio.to_thread(
                self._client.delete_objects,
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
            )
        except ClientError as exc:
            logger.warning("s3.bulk_delete_failed", error=str(exc))
            return 0
        return len(keys)

    async def list_keys(self, prefix: str = "", *, limit: int = 1000) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix, PaginationConfig={"MaxItems": limit}):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
                if len(keys) >= limit:
                    return keys
        return keys

    async def presigned_get_url(self, key: str, *, expires_s: int = 3600) -> PresignedUrl:
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_s,
        )
        from datetime import timedelta
        return PresignedUrl(
            url=url,
            method="GET",
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=expires_s),
            headers={},
        )

    async def healthcheck(self) -> bool:
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
            return True
        except (ClientError, EndpointConnectionError) as exc:
            logger.warning("s3.healthcheck_failed", error=str(exc))
            return False

    def get_local_path(self, key: str) -> str:
        # Materialise to a tmp file. Caller is expected to clean up.
        import tempfile
        from pathlib import Path
        fd, path = tempfile.mkstemp(prefix="dfc-s3-", suffix=Path(key).suffix)
        os.close(fd)
        try:
            self._client.download_file(self._bucket, key, path)
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
        return path


def _sha256_of_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


__all__ = ["S3Storage"]


def _guess_mime(path: Path) -> str | None:  # pragma: no cover
    mime, _ = mimetypes.guess_type(path.name)
    return mime
