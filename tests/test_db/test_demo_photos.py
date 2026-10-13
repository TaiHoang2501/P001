"""Demo listings get illustrative photos; a seller's own photos are never replaced."""

from pathlib import Path

from sqlalchemy import select

from src.db.models import MediaKind, Property, PropertyMedia
from src.db.seed import DEMO_PHOTOS, ensure_photos
from src.services.property_service import media_url


def _images(db, prop_id: int) -> list[str]:
    return list(
        db.scalars(
            select(PropertyMedia.s3_key)
            .where(PropertyMedia.property_id == prop_id, PropertyMedia.kind == MediaKind.IMAGE)
            .order_by(PropertyMedia.sort_order)
        )
    )


def test_demo_listings_get_six_photos_once(db):
    first = db.scalar(select(Property.id).order_by(Property.id))
    assert ensure_photos(db) > 0
    photos = _images(db, first)
    assert len(photos) == 6 and all(p.startswith("/demo/homes/") for p in photos)
    assert ensure_photos(db) == 0  # running again changes nothing
    assert _images(db, first) == photos


def test_seller_photos_are_kept(db):
    first = db.scalar(select(Property.id).order_by(Property.id))
    own = PropertyMedia(
        property_id=first, kind=MediaKind.IMAGE, s3_key="public/sellers/own.jpg", content_type="image/jpeg"
    )
    db.add(own)
    db.commit()
    ensure_photos(db)
    assert "public/sellers/own.jpg" in _images(db, first)


def test_every_demo_photo_is_shipped():
    public = Path(__file__).resolve().parents[2] / "frontend" / "public"
    missing = [p for paths in DEMO_PHOTOS.values() for p in paths if not (public / p.lstrip("/")).is_file()]
    assert missing == []


def test_paths_and_urls_are_served_as_is():
    assert media_url("/demo/homes/living-1.jpg") == "/demo/homes/living-1.jpg"
    assert media_url("https://cdn.example/x.jpg") == "https://cdn.example/x.jpg"
