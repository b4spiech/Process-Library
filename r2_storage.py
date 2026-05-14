"""Cloudflare R2 storage helpers.

R2 is S3-compatible, so we use boto3 with a custom endpoint URL.
All config comes from environment variables (see .env.example).
The client is lazy-initialised and reused; functions raise RuntimeError
if R2 isn't configured so callers can translate that to a 503.
"""
from __future__ import annotations

import os
import threading
from typing import BinaryIO, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


_client = None
_client_lock = threading.Lock()


def _config_ok() -> bool:
    return all(
        os.getenv(k)
        for k in (
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_ENDPOINT_URL",
            "R2_BUCKET_NAME",
        )
    )


def bucket_name() -> str:
    name = os.getenv("R2_BUCKET_NAME")
    if not name:
        raise RuntimeError("R2_BUCKET_NAME is not configured")
    return name


def get_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        if not _config_ok():
            raise RuntimeError(
                "R2 is not configured. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
                "R2_ENDPOINT_URL, and R2_BUCKET_NAME in the environment."
            )
        _client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def upload_fileobj(
    fileobj: BinaryIO,
    key: str,
    content_type: Optional[str] = None,
) -> None:
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    try:
        get_client().upload_fileobj(fileobj, bucket_name(), key, ExtraArgs=extra)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"R2 upload failed: {e}") from e


def put_bytes(
    contents: bytes,
    key: str,
    content_type: Optional[str] = None,
) -> None:
    """Upload an in-memory byte string. Safer than upload_fileobj when the
    source UploadFile may be closed by the time the upload runs.
    """
    kwargs = {"Bucket": bucket_name(), "Key": key, "Body": contents}
    if content_type:
        kwargs["ContentType"] = content_type
    try:
        get_client().put_object(**kwargs)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"R2 upload failed: {e}") from e


def delete_object(key: str) -> None:
    try:
        get_client().delete_object(Bucket=bucket_name(), Key=key)
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"R2 delete failed: {e}") from e


def generate_download_url(
    key: str,
    expires_in: int = 3600,
    download_filename: Optional[str] = None,
) -> str:
    params = {"Bucket": bucket_name(), "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = (
            f'attachment; filename="{download_filename}"'
        )
    try:
        return get_client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"R2 presign failed: {e}") from e


def is_configured() -> bool:
    return _config_ok()
