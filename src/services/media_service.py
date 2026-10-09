"""Photos a seller uploads from their device for a listing.

Kept in the database (`media_files`) so they survive restarts of the API host (its disk is not kept);
a listing refers to one by the key `/api/v1/media/<id>`, which `property_service.media_url` turns into a
full URL. Swapping the storage for S3 later only changes this module.
"""

import uuid

from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import BusinessRuleViolationError, NotFoundError
from src.db.models import MediaFile, UserRole
from src.models.property import MediaUploadOut

UPLOAD_PREFIX = "/api/v1/media/"

# Accepted photo types, recognised by their first bytes (the declared content type alone is not trusted)
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


def _sniff(data: bytes) -> str | None:
    for content_type, starts in _SIGNATURES.items():
        if any(data.startswith(s) for s in starts):
            if content_type == "image/webp" and data[8:12] != b"WEBP":
                continue
            return content_type
    return None


def upload(db: Session, actor: Actor, data: bytes, *, private: bool = False) -> MediaUploadOut:
    from src.services.property_service import media_url  # avoid an import cycle

    limit = get_settings().media_max_bytes
    if not data:
        raise BusinessRuleViolationError("The file is empty")
    if len(data) > limit:
        raise BusinessRuleViolationError(
            f"Photos must be at most {limit // (1024 * 1024)} MB", details={"max_bytes": limit}
        )
    content_type = _sniff(data)
    if content_type is None:
        raise BusinessRuleViolationError("Only JPEG, PNG or WebP photos can be uploaded")
    file = MediaFile(
        id=uuid.uuid4().hex, owner_id=actor.id, content_type=content_type, size=len(data), data=data, is_private=private
    )
    db.add(file)
    db.commit()
    key = UPLOAD_PREFIX + file.id
    return MediaUploadOut(key=key, url=media_url(key), content_type=content_type)


def get(db: Session, media_id: str) -> MediaFile:
    """A public photo (listing photos). Private documents are never served here."""
    file = db.get(MediaFile, media_id) if len(media_id) == 32 else None
    if file is None or file.is_private:
        raise NotFoundError("Photo not found")
    return file


def get_private(db: Session, actor: Actor, media_id: str) -> MediaFile:
    """A private document: only for the seller who uploaded it and the investor."""
    file = db.get(MediaFile, media_id) if len(media_id) == 32 else None
    if file is None or not (file.owner_id == actor.id or actor.role == UserRole.INVESTOR_OPERATOR):
        raise NotFoundError("Document not found")
    return file


def require_own_upload(db: Session, actor: Actor, key: str) -> MediaFile | None:
    """For a key of an uploaded photo: it must be one this seller uploaded. Other keys (S3 / URLs) -> None."""
    if not key.startswith(UPLOAD_PREFIX):
        return None
    file = db.get(MediaFile, key.removeprefix(UPLOAD_PREFIX))
    if file is None or file.owner_id != actor.id:
        raise NotFoundError("Photo not found")
    return file
