"""Schema-level guarantees for the identity & media tables (spec §4.16)."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.models import (
    BuyerProfile,
    MediaKind,
    Property,
    PropertyMedia,
    PropertyStatus,
    SellerProfile,
    SellerVerificationStatus,
    User,
    UserRole,
)


def _first(db, role: UserRole) -> User:
    return db.query(User).filter_by(role=role).order_by(User.id).first()


def test_seller_profile_defaults_to_unverified(db):
    owner = User(role=UserRole.OWNER, full_name="New Owner", phone="0999000222")
    db.add(owner)
    db.flush()
    db.add(SellerProfile(user_id=owner.id))
    db.commit()

    profile = db.get(SellerProfile, owner.id)
    assert profile.verification_status == SellerVerificationStatus.UNVERIFIED


def test_buyer_profile_rejects_inverted_budget(db):
    buyer = _first(db, UserRole.CUSTOMER)
    db.add(BuyerProfile(user_id=buyer.id, budget_min_vnd=6_000_000_000, budget_max_vnd=5_000_000_000))
    with pytest.raises(IntegrityError, match="ck_buyer_profiles_budget_order"):
        db.commit()


def test_profiles_are_removed_with_their_user(db):
    buyer = _first(db, UserRole.CUSTOMER)
    new_user = User(role=UserRole.CUSTOMER, full_name="Temp", phone="0999000111", password_hash="x")
    db.add(new_user)
    db.flush()
    db.add(BuyerProfile(user_id=new_user.id, budget_max_vnd=5_000_000_000))
    db.commit()

    db.delete(new_user)
    db.commit()
    assert db.get(BuyerProfile, new_user.id) is None
    assert db.get(User, buyer.id) is not None


def test_property_media_ownership_doc_can_be_private(db):
    prop = db.query(Property).order_by(Property.id).first()
    db.add(
        PropertyMedia(
            property_id=prop.id,
            kind=MediaKind.OWNERSHIP_DOC,
            s3_key=f"private/properties/{prop.id}/so-hong.pdf",
            content_type="application/pdf",
            is_public=False,
        )
    )
    db.commit()

    media = db.query(PropertyMedia).filter_by(property_id=prop.id).one()
    assert media.is_public is False
    assert media.sort_order == 0


def test_property_can_be_withdrawn(db):
    prop = db.query(Property).order_by(Property.id).first()
    prop.status = PropertyStatus.WITHDRAWN
    db.commit()
    db.refresh(prop)
    assert prop.status == PropertyStatus.WITHDRAWN
