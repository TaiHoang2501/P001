"""Photos uploaded by sellers: upload (owner) and the public image itself (listing photos are public)."""

from fastapi import APIRouter, File, Form, Response, UploadFile

from src.core.deps import AnyActor, DbSession, OwnerActor
from src.models.property import MediaUploadOut
from src.services import media_service

router = APIRouter(tags=["media"])


@router.post("/owner/media", response_model=MediaUploadOut, status_code=201)
async def upload_photo(
    actor: OwnerActor, db: DbSession, file: UploadFile = File(...), private: bool = Form(False)
) -> MediaUploadOut:
    """A photo from the seller's device; attach it to a listing with its `key`.

    `private`: an identity / authorisation document (ownership support), only shown to the investor.
    """
    return media_service.upload(db, actor, await file.read(), private=private)


@router.get("/media/{media_id}/private", response_class=Response)
def private_document(media_id: str, actor: AnyActor, db: DbSession) -> Response:
    file = media_service.get_private(db, actor, media_id)
    return Response(content=file.data, media_type=file.content_type, headers={"Cache-Control": "private, no-store"})


@router.get("/media/{media_id}", response_class=Response)
def photo(media_id: str, db: DbSession) -> Response:
    file = media_service.get(db, media_id)
    # A photo never changes once uploaded (a new one gets a new id)
    return Response(
        content=file.data,
        media_type=file.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
