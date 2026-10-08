"""Object storage for listing media (any S3-compatible provider: Supabase Storage, Cloudflare R2, AWS S3).

Public media (photos, floor plans, videos) lives in the public bucket and is served as MEDIA_BASE_URL + key.
Private media (ownership documents) lives in the private bucket and is only reachable through short-lived
presigned URLs, which are only handed to the owner and operators.
"""

import logging
from functools import lru_cache
from typing import Any, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.config import get_settings
from src.core.errors import StorageUnavailableError

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return get_settings().storage_enabled


@lru_cache
def _client() -> Any:
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        region_name=s.s3_region,
        aws_access_key_id=s.s3_access_key_id,
        aws_secret_access_key=s.s3_secret_access_key,
        # Supabase Storage needs path-style URLs; R2 and S3 accept them too
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _bucket(private: bool) -> str:
    s = get_settings()
    return s.s3_private_bucket if private else s.s3_public_bucket


def upload(key: str, body: BinaryIO, content_type: str, *, private: bool) -> None:
    if not is_enabled():
        raise StorageUnavailableError("Media storage is not configured")
    try:
        _client().upload_fileobj(body, _bucket(private), key, ExtraArgs={"ContentType": content_type})
    except (BotoCoreError, ClientError) as exc:
        logger.exception("media upload failed")
        raise StorageUnavailableError("Could not upload the file, please try again") from exc


def delete(key: str, *, private: bool) -> None:
    """Best effort: a leftover object is harmless, so failures are only logged."""
    if not is_enabled():
        return
    try:
        _client().delete_object(Bucket=_bucket(private), Key=key)
    except (BotoCoreError, ClientError):
        logger.warning("could not delete media object %s", key, exc_info=True)


def signed_url(key: str) -> str:
    """Short-lived download URL for an object in the private bucket (signed locally, no network call)."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(private=True), "Key": key},
        ExpiresIn=get_settings().media_signed_url_seconds,
    )
