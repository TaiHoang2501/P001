"""Load MVP demo data.

Usage:
    python -m src.db.seed           # only if the database is empty
    python -m src.db.seed --reset   # wipe all rows first (dev only!)
    python -m src.db.seed --ensure-red-books  # add demo red books missing from an existing database
    python -m src.db.seed --if-empty --ensure-slots --ensure-red-books   # deploy start-up (see scripts/start.sh)

Seeded buyers and operators use the password below; sellers sign in with phone + OTP.
Never run this against production.
"""

import argparse
import csv
import random
import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.security import hash_password
from src.db.models import (
    AvailabilitySlot,
    Base,
    Building,
    BuyerProfile,
    Deal,
    Direction,
    Furnishing,
    LegalStatus,
    MediaKind,
    OwnershipVerificationStatus,
    Project,
    Property,
    PropertyMedia,
    PropertyOwnershipVerification,
    PropertyStatus,
    PropertyType,
    SellerProfile,
    SellerVerificationStatus,
    User,
    UserRole,
    UserStatus,
    ViewType,
)
from src.db.session import get_sessionmaker

SEED_PASSWORD = "Password123!"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# From data/seed/users_seed.csv (feature/Baor)
USERS = [
    (1, UserRole.CUSTOMER, "Nguyễn Văn An", "0901111222", "an.nguyen@gmail.com", UserStatus.ACTIVE),
    (2, UserRole.CUSTOMER, "Trần Thị Bình", "0902222333", "binh.tran@gmail.com", UserStatus.ACTIVE),
    (3, UserRole.CUSTOMER, "Lê Hoàng Nam", "0903333444", "nam.le@gmail.com", UserStatus.ACTIVE),
    (4, UserRole.OWNER, "Phạm Minh Tuấn", "0918765432", "tuan.pham@gmail.com", UserStatus.ACTIVE),
    (5, UserRole.OWNER, "Hoàng Thị Lan", "0912345678", "lan.hoang@gmail.com", UserStatus.ACTIVE),
    (6, UserRole.OWNER, "Đỗ Văn Khoa", "0987654321", "khoa.do@gmail.com", UserStatus.PENDING_VERIFICATION),
    (7, UserRole.INVESTOR_OPERATOR, "Nguyễn Quang Dũng", "0901234567", "operator@vinhomes.vn", UserStatus.ACTIVE),
    (8, UserRole.INVESTOR_OPERATOR, "Trần Thu Hà", "0902345678", "coordinator@vinhomes.vn", UserStatus.ACTIVE),
]

# From data/projects_buildings_seed.csv (TaiHoang)
PROJECTS = [
    ("VHOP1", "Vinhomes Ocean Park 1", "Hà Nội", "Gia Lâm"),
    ("VHSC", "Vinhomes Smart City", "Hà Nội", "Nam Từ Liêm"),
    ("VHWP", "Vinhomes West Point", "Hà Nội", "Nam Từ Liêm"),
    ("VHGP", "Vinhomes Grand Park", "TP.HCM", "Thủ Đức"),
]
BUILDINGS = [
    ("VHOP1", "S2.01", "The Sapphire 2 - S2.01", 27, "20.9952", "105.9421"),
    ("VHOP1", "S1.08", "The Sapphire 1 - S1.08", 28, "20.9985", "105.9472"),
    ("VHOP1", "R1.02", "The Zenpark - R1.02", 31, "20.9928", "105.9385"),
    ("VHSC", "GS3", "The Miami - GS3", 38, "20.9978", "105.7432"),
    ("VHSC", "TK1", "The Tonkin - TK1", 38, "20.9935", "105.7485"),
    ("VHSC", "SA2", "The Sakura - SA2", 39, "20.9912", "105.7460"),
    ("VHWP", "W2", "West 2 - W2", 39, "21.0115", "105.7865"),
    ("VHGP", "S7.02", "The Origami - S7.02", 26, "10.8458", "106.8392"),
]

# (bedrooms, bathrooms, area range m², price per m² range in million VND)
LAYOUTS = [
    (0, 1, (28, 35), (55, 65)),
    (1, 1, (40, 50), (50, 60)),
    (2, 1, (52, 60), (55, 65)),
    (2, 2, (60, 75), (55, 70)),
    (3, 2, (80, 100), (50, 65)),
]
VIEW_TEXT = {
    ViewType.LAKE: "view hồ điều hòa",
    ViewType.RIVER: "view sông thoáng",
    ViewType.PARK: "view công viên nội khu",
    ViewType.POOL: "view bể bơi",
    ViewType.CITY: "view thành phố",
    ViewType.INTERNAL: "view nội khu yên tĩnh",
}
FURNISH_TEXT = {Furnishing.NONE: "bàn giao thô", Furnishing.BASIC: "nội thất cơ bản", Furnishing.FULL: "full nội thất"}


def _m2(area: Decimal | str) -> str:
    """Area the Vietnamese way, with a decimal comma: 57.5 -> "57,5"."""
    return str(area).replace(".", ",")


# Older seeded descriptions wrote the area with a decimal point ("Căn 2PN 57.5 m² tầng 12, ...")
_SEEDED_AREA = re.compile(r"^(Căn \S+ )(\d+)\.(\d+)( m² tầng )")


# The listings waiting for review (and the hidden one of an unverified owner): real-looking units, not "X01"
# (unit number suffix, bedrooms, area m², floor, price VND); older databases are updated by ensure_red_book_units
EXTRA_UNITS = [
    ("1206", 2, "68.5", 12, 3_650_000_000),
    ("1803", 3, "92.0", 18, 5_200_000_000),
    ("0911", 2, "55.3", 9, 2_850_000_000),
    ("2104", 2, "74.0", 21, 4_100_000_000),
]
_PLACEHOLDER_UNIT = re.compile(r"^(.+)-X0([1-4])$")


def _properties(rng: random.Random, buildings: list[Building]) -> list[Property]:
    props: list[Property] = []
    # 32 approved listings across the two active owners
    for i in range(32):
        building = buildings[i % len(buildings)]
        beds, baths, (a_lo, a_hi), (p_lo, p_hi) = rng.choice(LAYOUTS)
        area = Decimal(rng.randint(a_lo * 10, a_hi * 10)) / 10
        price = int(area * rng.randint(p_lo, p_hi)) * 1_000_000
        floor = rng.randint(3, (building.total_floors or 30) - 1)
        view = rng.choice(list(ViewType))
        furnishing = rng.choice(list(Furnishing))
        label = "Studio" if beds == 0 else f"{beds}PN"
        props.append(
            Property(
                owner_id=4 if i % 2 == 0 else 5,
                building=building,
                unit_code=f"{building.code}-{floor:02d}{i + 1:02d}",
                property_type=PropertyType.APARTMENT,
                bedrooms=beds,
                bathrooms=baths,
                area_m2=area,
                floor=floor,
                price_vnd=price,
                direction=rng.choice(list(Direction)),
                view=view,
                furnishing=furnishing,
                legal_status=rng.choice([LegalStatus.PINK_BOOK, LegalStatus.PINK_BOOK, LegalStatus.SALE_CONTRACT]),
                description=f"Căn {label} {_m2(area)} m² tầng {floor}, {VIEW_TEXT[view]}, {FURNISH_TEXT[furnishing]}.",
                status=PropertyStatus.AVAILABLE,
            )
        )
    # Moderation queue + draft + an unverified owner (must never appear in search)
    extra = [
        (5, PropertyStatus.PENDING_REVIEW, "Căn 2PN view công viên, đang chờ duyệt tin."),
        (4, PropertyStatus.PENDING_REVIEW, "Căn 3PN góc, chờ Ban quản trị duyệt."),
        (4, PropertyStatus.PENDING_REVIEW, "Căn 2PN, chờ Ban quản trị duyệt."),
        (6, PropertyStatus.AVAILABLE, "Tin của chủ nhà chưa xác minh - không được hiển thị."),
    ]
    for j, (owner_id, status, desc) in enumerate(extra):
        building = buildings[j]
        unit, beds, area, floor, price = EXTRA_UNITS[j]
        props.append(
            Property(
                owner_id=owner_id,
                building=building,
                unit_code=f"{building.code}-{unit}",
                property_type=PropertyType.APARTMENT,
                bedrooms=beds,
                bathrooms=2,
                area_m2=Decimal(area),
                floor=floor,
                price_vnd=price,
                direction=Direction.SE,
                view=ViewType.PARK,
                furnishing=Furnishing.BASIC,
                legal_status=LegalStatus.PINK_BOOK,
                description=desc,
                status=status,
            )
        )
    return props


def _media(props: list[Property]) -> list[PropertyMedia]:
    """One cover photo per seeded listing (ownership is proven by its red book, see ensure_red_book_units)."""
    media = []
    for prop in props:
        media.append(
            PropertyMedia(
                property_id=prop.id,
                kind=MediaKind.IMAGE,
                s3_key=f"public/properties/{prop.id}/cover.jpg",
                content_type="image/jpeg",
            )
        )
    return media


# Extra Ocean Park 1 two-bedroom listings (the random seed gives only three under 5 tỷ), so a search for
# "2 phòng ngủ ở Ocean Park" has enough real answers.
# (building, unit code, floor, bathrooms, area m², price VND, direction, view, furnishing, owner)
DEMO_LISTINGS = [
    ("S1.08", "S1.08-1512", 15, 2, "63.2", 3_950_000_000, Direction.SE, ViewType.LAKE, Furnishing.FULL, 4),
    ("S2.01", "S2.01-0718", 7, 2, "65.8", 4_200_000_000, Direction.E, ViewType.PARK, Furnishing.BASIC, 5),
    ("R1.02", "R1.02-2106", 21, 2, "68.5", 4_650_000_000, Direction.S, ViewType.LAKE, Furnishing.FULL, 4),
    ("S1.08", "S1.08-0904", 9, 1, "59.0", 3_720_000_000, Direction.NE, ViewType.POOL, Furnishing.BASIC, 5),
    ("S2.01", "S2.01-2209", 22, 2, "72.4", 4_890_000_000, Direction.SW, ViewType.CITY, Furnishing.NONE, 4),
]


def ensure_listings(db: Session) -> int:
    """Add the DEMO_LISTINGS missing from this database (matched by unit code); existing rows are never changed.

    Skipped when the buildings or demo owners are not there (a non-demo database). Returns how many were added.
    """
    buildings = {b.code: b for b in db.scalars(select(Building))}
    owners = set(db.scalars(select(User.id).where(User.id.in_(DEMO_OWNER_IDS))))
    existing = set(db.scalars(select(Property.unit_code)))
    added: list[Property] = []
    for code, unit, floor, baths, area, price, direction, view, furnishing, owner in DEMO_LISTINGS:
        if unit in existing or code not in buildings or owner not in owners:
            continue
        prop = Property(
            owner_id=owner,
            building=buildings[code],
            unit_code=unit,
            property_type=PropertyType.APARTMENT,
            bedrooms=2,
            bathrooms=baths,
            area_m2=Decimal(area),
            floor=floor,
            price_vnd=price,
            direction=direction,
            view=view,
            furnishing=furnishing,
            legal_status=LegalStatus.PINK_BOOK,
            description=f"Căn 2PN {_m2(area)} m² tầng {floor}, {VIEW_TEXT[view]}, {FURNISH_TEXT[furnishing]}.",
            status=PropertyStatus.AVAILABLE,
        )
        db.add(prop)
        added.append(prop)
    db.flush()
    db.add_all(_media(added))
    db.add_all(_slots(added))
    db.commit()
    return len(added)


# Demo story for the seller "Hoàng Thị Lan" (0912345678): she has verified 8 red books but sells only 4 homes,
# so the seller pages show more "đã xác thực" than "đang bán". Her other seeded listings go to another demo
# seller (still on sale, so buyers have the same homes to choose from).
STORY_SELLER_PHONE = "0912345678"
STORY_SELLING = {  # unit code -> the red book behind it
    "S1.08-2410": "SD-2018-0778901",
    "S1.08-1026": "SD-2021-0778902",
    "S2.01-0718": "SD-2023-0778903",
    "S1.08-0904": "SD-2024-0778904",
}
STORY_UNLISTED = ["SD-2019-0778905", "SD-2020-0778906", "SD-2022-0778907", "SD-2025-0778908"]
STORY_OTHER_SELLER = ("Vũ Đức Hải", "0934567890", "hai.vu@gmail.com")


def ensure_seller_story(db: Session) -> str:
    """Apply STORY_* to a demo database; safe to run again (nothing is added or moved twice).

    Only listings without any deal are moved to the other seller, so no buyer's viewing changes hands.
    """
    seller = db.scalar(select(User).where(User.phone == STORY_SELLER_PHONE, User.role == UserRole.OWNER))
    if seller is None:
        return "skipped (no demo seller)"

    # Her red books: the four behind her listings and four not listed yet
    _sync_red_book_id_sequence(db)
    codes = [*STORY_SELLING.values(), *STORY_UNLISTED]
    books = {
        v.red_book_code: v
        for v in db.scalars(
            select(PropertyOwnershipVerification).where(PropertyOwnershipVerification.red_book_code.in_(codes))
        )
    }
    added_books = 0
    for code in codes:
        if code not in books:
            books[code] = PropertyOwnershipVerification(
                user_id=seller.id,
                red_book_holder_name=seller.full_name,
                red_book_code=code,
                owner_phone=seller.phone,
                status=OwnershipVerificationStatus.VERIFIED,
                otp_attempts=1,
                verified_at=datetime.now(ZoneInfo(get_settings().timezone)),
            )
            db.add(books[code])
            added_books += 1
    db.flush()

    # The other demo seller who takes over her remaining listings
    name, phone, email = STORY_OTHER_SELLER
    other = db.scalar(select(User).where(User.phone == phone))
    if other is None:
        other = User(role=UserRole.OWNER, full_name=name, phone=phone, email=email, status=UserStatus.ACTIVE)
        db.add(other)
        db.flush()
        operator = db.scalar(select(User.id).where(User.role == UserRole.INVESTOR_OPERATOR).limit(1))
        db.add(
            SellerProfile(
                user_id=other.id,
                verification_status=SellerVerificationStatus.VERIFIED,
                id_document_s3_key=f"private/sellers/{other.id}/cccd.jpg",
                verified_by=operator,
            )
        )

    linked = moved = 0
    used = set(db.scalars(select(Property.verification_id).where(Property.verification_id.is_not(None))))
    for prop in db.scalars(select(Property).where(Property.owner_id == seller.id)):
        code = STORY_SELLING.get(prop.unit_code)
        stand_in = prop.verification if prop.verification and _generated(prop.verification.red_book_code) else None
        if code is not None:
            book = books[code]
            if (prop.verification_id is None or stand_in) and book.id not in used:
                # Her own red book replaces one made up for an older listing (ensure_red_book_units ran first)
                prop.verification_id = book.id
                used.add(book.id)
                if book.unit_code is None:
                    _copy_unit(book, prop)
                if stand_in is not None:
                    db.flush()
                    db.delete(stand_in)
                linked += 1
        elif (
            prop.status == PropertyStatus.AVAILABLE
            and db.scalar(select(Deal.id).where(Deal.property_id == prop.id)) is None
        ):
            prop.owner_id = other.id
            if stand_in is not None:
                # The made-up red book follows the home to its new owner
                stand_in.user_id, stand_in.red_book_holder_name, stand_in.owner_phone = (
                    other.id,
                    other.full_name,
                    other.phone or "",
                )
            moved += 1
    db.commit()
    return f"{added_books} red book(s) added, {linked} listing(s) linked, {moved} listing(s) moved to the other seller"


# Illustrative interiors served by the web app (frontend/public/demo/homes, Pexels License; see CREDITS.md there)
DEMO_PHOTOS = {
    "living": [f"/demo/homes/living-{i}.jpg" for i in range(1, 9)],
    "bedroom": [f"/demo/homes/bedroom-{i}.jpg" for i in range(1, 5)],
    "kitchen": [f"/demo/homes/kitchen-{i}.jpg" for i in range(1, 6)],
}


def ensure_photos(db: Session) -> int:
    """Give every demo-seeded listing four photos (living room cover, bedroom, kitchen, another living room).

    The seed only stores a placeholder cover key that no file backs; that placeholder (or an older pick of demo
    photos) is replaced. Listings with a seller's own photos are never touched. Returns how many listings changed.
    """
    living, bedroom, kitchen = DEMO_PHOTOS["living"], DEMO_PHOTOS["bedroom"], DEMO_PHOTOS["kitchen"]
    done = 0
    for prop in db.scalars(select(Property).order_by(Property.id)):
        images = [m for m in prop.media if m.kind == MediaKind.IMAGE]
        placeholder = f"public/properties/{prop.id}/cover.jpg"  # the key `_media` gives every seeded listing
        if any(m.s3_key != placeholder and not m.s3_key.startswith("/demo/homes/") for m in images):
            continue  # the seller's own photos
        # Spread the sets so listings shown together (e.g. one seller's) do not share a cover photo
        i = prop.id
        cover = (i * 7 + i // 8) % 8
        photos = [living[cover], bedroom[(i * 3 + i // 4) % 4], kitchen[(i * 2 + i // 5) % 5], living[(cover + 3) % 8]]
        if [m.s3_key for m in sorted(images, key=lambda m: m.sort_order)] == photos:
            continue
        for m in images:
            db.delete(m)
        db.add_all(
            PropertyMedia(
                property_id=prop.id, kind=MediaKind.IMAGE, s3_key=key, content_type="image/jpeg", sort_order=n
            )
            for n, key in enumerate(photos)
        )
        done += 1
    db.commit()
    return done


# Demo viewing requests for the story seller (STORY_SELLER_PHONE), from buyers with real-looking names, covering
# every case the seller pages show. (name, phone, budget min/max in tỷ, unit, case, day offset, hour, note)
DEMO_REQUESTS = [
    ("Trần Quốc Bảo", "0938100101", 3.0, 3.5, "S1.08-2410", "requested", 1, 14, "Đi cùng vợ, muốn xem cả ban công", 20),
    ("Phạm Minh Anh", "0938100102", 3.8, 4.4, "S2.01-0718", "requested", 2, 9, "Gia đình 4 người, cần bếp rộng", 6),
    ("Lê Thu Hà", "0938100103", 3.5, 4.0, "S1.08-0904", "requested", 3, 16, None, 1),
    ("Đỗ Gia Huy", "0938100104", 4.5, 5.0, "S1.08-1026", "confirmed", 2, 14, "Mua để ở, cần chỗ để ô tô", 0),
    ("Hoàng Đức Long", "0938100105", 4.0, 4.5, "S2.01-0718", "confirmed", 3, 14, None, 0),
    ("Vũ Ngọc Mai", "0938100106", 3.0, 3.4, "S1.08-2410", "reschedule", 4, 9, "Xin đổi sang chiều vì bận buổi sáng", 0),
    ("Ngô Thanh Tâm", "0938100107", 3.5, 3.8, "S1.08-0904", "rejected", 1, 9, None, 0),
    ("Bùi Khánh Linh", "0938100108", 4.0, 4.3, "S2.01-0718", "cancelled", 1, 16, None, 0),
    ("Đặng Hải Nam", "0938100109", 3.0, 3.5, "S1.08-2410", "completed", -1, 10, "Đã xem, khá ưng view", 0),
    ("Trịnh Mỹ Duyên", "0938100110", 3.5, 4.0, "S1.08-0904", "no_show", -2, 15, None, 0),
]


def ensure_demo_requests(db: Session) -> int:
    """Add DEMO_REQUESTS (buyers + their viewing requests) once; skipped if they exist or the demo seller is missing.

    Upcoming cases go through the booking service like a real buyer and seller would (deal, hold, notifications);
    past ones (completed / no-show) can no longer be booked, so they are written directly.
    """
    from src.core.actor import Actor
    from src.db.models import Booking, BookingStatus
    from src.models.booking import BookingCreate, RescheduleRequest
    from src.services import booking_service, deal_service

    seller = db.scalar(select(User).where(User.phone == STORY_SELLER_PHONE, User.role == UserRole.OWNER))
    if seller is None or db.scalar(select(User.id).where(User.phone == DEMO_REQUESTS[0][1])) is not None:
        return 0
    homes = {p.unit_code: p for p in db.scalars(select(Property).where(Property.owner_id == seller.id))}
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz).date()
    owner = Actor(seller)
    added = 0
    for name, phone, lo, hi, unit, case, day, hour, note, hours_ago in DEMO_REQUESTS:
        prop = homes.get(unit)
        if prop is None or prop.status != PropertyStatus.AVAILABLE:
            continue
        buyer = User(role=UserRole.CUSTOMER, full_name=name, phone=phone, status=UserStatus.ACTIVE)
        db.add(buyer)
        db.flush()
        db.add(BuyerProfile(user_id=buyer.id, budget_min_vnd=int(lo * 1e9), budget_max_vnd=int(hi * 1e9)))
        db.commit()
        actor = Actor(buyer)
        start = datetime.combine(today + timedelta(days=day), time(hour, 0), tzinfo=tz)

        if case in ("completed", "no_show"):
            deal = deal_service.get_or_create_open(db, actor, prop)
            db.add(
                Booking(
                    deal_id=deal.id,
                    property_id=prop.id,
                    customer_id=buyer.id,
                    start_at=start,
                    end_at=start + timedelta(minutes=SLOT_MINUTES),
                    status=BookingStatus.COMPLETED if case == "completed" else BookingStatus.NO_SHOW,
                    customer_note=note,
                    created_at=start - timedelta(days=2),
                    responded_at=start - timedelta(days=2) + timedelta(minutes=35),
                )
            )
            db.flush()
            deal_service.sync_status(db, actor, deal)
            db.commit()
            added += 1
            continue

        booking = booking_service.create_request(
            db, actor, BookingCreate(property_id=prop.id, start_at=start, note=note)
        )
        if case in ("confirmed", "reschedule"):
            booking_service.approve(db, owner, booking.id)
        if case == "reschedule":
            later = datetime.combine(today + timedelta(days=day + 1), time(16, 0), tzinfo=tz)
            booking_service.reschedule(db, actor, booking.id, RescheduleRequest(start_at=later))
        elif case == "rejected":
            booking_service.reject(db, owner, booking.id, "Khung giờ này tôi bận")
        elif case == "cancelled":
            booking_service.cancel(db, actor, booking.id)
        if hours_ago:
            # Sent a while ago, so the seller's deadlines differ (the 24 h answer window)
            row = db.get(Booking, booking.id)
            row.created_at = datetime.now(tz) - timedelta(hours=hours_ago)
            db.commit()
        added += 1
    return added


# Demo cases added by ensure_showcase (all for the story seller unless said otherwise)
SHOWCASE_LISTING_BOOK = "SD-2025-0778908"  # one of Lan's unlisted red books: a listing with uploaded photos
SHOWCASE_UPLOADS = Path(__file__).resolve().parents[2] / "data" / "demo_uploads"
SHOWCASE_PHOTOS = ("living.jpg", "bedroom.jpg", "kitchen.jpg")
# Two buyers asking for the same time on two of her homes: she can only confirm one
SHOWCASE_OVERLAP = [
    ("Nguyễn Thảo Vy", "0938100111", 3.0, 3.5, "S1.08-2410", "Muốn xem buổi chiều sau giờ làm"),
    ("Lý Minh Khôi", "0938100112", 3.8, 4.3, "S2.01-0718", None),
]
SHOWCASE_OVERLAP_DAY, SHOWCASE_OVERLAP_HOUR = 2, 16
# A confirmed viewing that is over and waits for her to record it
SHOWCASE_PAST = ("Cao Thị Hồng", "0938100113", 3.8, 4.4, "S2.01-0718")
# Recorded as a no-show, the buyer says they came: a case for the investor
SHOWCASE_DISPUTE = (
    "Mai Quốc Việt",
    "0938100114",
    4.5,
    5.0,
    "S1.08-1026",
    "Tôi đến lúc 9h05, bảo vệ toà S1.08 có gặp tôi",
)
# A seller whose red book got locked after wrong OTPs asks the investor for help
SHOWCASE_LOCKED = ("Trần Văn Đức", "0933444555", "SD-2015-0110022")


def _showcase_buyer(db: Session, name: str, phone: str, lo: float, hi: float) -> User | None:
    """A new demo buyer, or None when one with this phone already exists (the case was added before)."""
    if db.scalar(select(User.id).where(User.phone == phone)) is not None:
        return None
    buyer = User(role=UserRole.CUSTOMER, full_name=name, phone=phone, status=UserStatus.ACTIVE)
    db.add(buyer)
    db.flush()
    db.add(BuyerProfile(user_id=buyer.id, budget_min_vnd=int(lo * 1e9), budget_max_vnd=int(hi * 1e9)))
    db.commit()
    return buyer


def _past_booking(db: Session, buyer: User, prop: Property, start: datetime, status: str) -> int:
    """A viewing in the past (it can no longer be booked through the service), with its deal kept in step."""
    from src.core.actor import Actor
    from src.db.models import Booking, BookingStatus
    from src.services import deal_service

    actor = Actor(buyer)
    deal = deal_service.get_or_create_open(db, actor, prop)
    booking = Booking(
        deal_id=deal.id,
        property_id=prop.id,
        customer_id=buyer.id,
        start_at=start,
        end_at=start + timedelta(minutes=SLOT_MINUTES),
        status=BookingStatus(status),
        created_at=start - timedelta(days=2),
        responded_at=start - timedelta(days=2) + timedelta(minutes=40),
    )
    db.add(booking)
    db.flush()
    deal_service.sync_status(db, actor, deal)
    db.commit()
    return booking.id


def ensure_showcase(db: Session) -> str:
    """Demo cases beyond DEMO_REQUESTS, so a fresh deployment shows every screen; each is added once.

    - Lan posts a listing with photos uploaded from her device (waits in the operator's review queue).
    - Two buyers ask for the same time on two of her homes (confirming one closes the other).
    - A confirmed viewing of hers is over and waits for "Đã xem xong" / "Khách không đến".
    - A buyer recorded as a no-show says they came (VIEWING_DISPUTE case for the operator).
    - Trần Văn Đức's red book is locked after wrong OTPs; he asks for help (OWNERSHIP_SUPPORT case).
    Run after --ensure-requests. A case whose seller, home or red book is missing is left out.
    """
    from src.core.actor import Actor
    from src.models.booking import BookingCreate
    from src.models.ownership import OwnershipSupportCreate
    from src.models.property import PropertyCreate
    from src.services import (
        booking_service,
        media_service,
        ownership_support_service,
        property_service,
        viewing_outcome_service,
    )

    seller = db.scalar(select(User).where(User.phone == STORY_SELLER_PHONE, User.role == UserRole.OWNER))
    if seller is None:
        return "skipped (no demo seller)"
    owner = Actor(seller)
    homes = {
        p.unit_code: p
        for p in db.scalars(
            select(Property).where(Property.owner_id == seller.id, Property.status == PropertyStatus.AVAILABLE)
        )
    }
    tz = ZoneInfo(get_settings().timezone)
    now = datetime.now(tz)
    done: list[str] = []

    # 1. A listing with photos the seller uploaded (stored in media_files, like a real upload)
    book = db.scalar(
        select(PropertyOwnershipVerification).where(
            PropertyOwnershipVerification.red_book_code == SHOWCASE_LISTING_BOOK,
            PropertyOwnershipVerification.user_id == seller.id,
        )
    )
    files = [SHOWCASE_UPLOADS / name for name in SHOWCASE_PHOTOS]
    if (
        book is not None
        and book.building_id is not None
        and db.scalar(select(Property.id).where(Property.verification_id == book.id)) is None
        and all(f.is_file() for f in files)
    ):
        keys = [media_service.upload(db, owner, f.read_bytes()).key for f in files]
        property_service.create(
            db,
            owner,
            PropertyCreate(
                verification_id=book.id,
                building_id=book.building_id,
                unit_code=book.unit_code or "",
                property_type=book.property_type or PropertyType.APARTMENT,
                bedrooms=book.bedrooms or 2,
                bathrooms=book.bathrooms or 2,
                area_m2=book.area_m2 or Decimal("68.0"),
                floor=book.floor or 1,
                direction=book.direction or Direction.SE,
                price_vnd=3_950_000_000,
                view=ViewType.PARK,
                furnishing=Furnishing.FULL,
                legal_status=LegalStatus.PINK_BOOK,
                description="Căn góc 2PN nhìn công viên, nội thất đầy đủ, ảnh chụp thực tế tháng này.",
                photos=keys,
            ),
        )
        done.append("listing with uploaded photos")

    # 2. Same time, two homes of one seller: both wait for her answer
    start = datetime.combine(now.date() + timedelta(days=SHOWCASE_OVERLAP_DAY), time(SHOWCASE_OVERLAP_HOUR), tzinfo=tz)
    for name, phone, lo, hi, unit, note in SHOWCASE_OVERLAP:
        if unit not in homes:
            continue
        buyer = _showcase_buyer(db, name, phone, lo, hi)
        if buyer is not None:
            booking_service.create_request(
                db, Actor(buyer), BookingCreate(property_id=homes[unit].id, start_at=start, note=note)
            )
            done.append(f"overlapping request ({unit})")

    # 3. A confirmed viewing that is over (a few hours ago) and not recorded yet
    name, phone, lo, hi, unit = SHOWCASE_PAST
    if unit in homes and (buyer := _showcase_buyer(db, name, phone, lo, hi)) is not None:
        past = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
        _past_booking(db, buyer, homes[unit], past, "CONFIRMED")
        done.append("past viewing to record")

    # 4. A no-show the buyer disputes
    name, phone, lo, hi, unit, note = SHOWCASE_DISPUTE
    if unit in homes and (buyer := _showcase_buyer(db, name, phone, lo, hi)) is not None:
        yesterday = datetime.combine(now.date() - timedelta(days=1), time(9), tzinfo=tz)
        booking_id = _past_booking(db, buyer, homes[unit], yesterday, "NO_SHOW")
        viewing_outcome_service.dispute(db, Actor(buyer), booking_id, "I_CAME", note)
        done.append("viewing dispute")

    # 5. A locked red book: the seller asks the investor for help
    name, phone, code = SHOWCASE_LOCKED
    locked = db.scalar(select(PropertyOwnershipVerification).where(PropertyOwnershipVerification.red_book_code == code))
    if locked is not None and db.scalar(select(User.id).where(User.phone == phone)) is None:
        user = User(role=UserRole.OWNER, full_name=name, phone=phone, status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()
        db.add(SellerProfile(user_id=user.id))
        db.commit()
        ownership_support_service.request(
            db,
            Actor(user),
            OwnershipSupportCreate(
                reason="LOCKED",
                red_book_holder_name=name,
                red_book_code=code,
                note="Tôi gõ nhầm mã OTP mấy lần nên sổ bị khóa, nhờ mở lại giúp tôi.",
            ),
        )
        done.append("ownership support case")

    return ", ".join(done) if done else "nothing to add"


# A full set of cases for the demo buyer Nguyễn Văn An (0901111222) and more for the story seller, so both the
# buyer's "Hoạt động" page and the seller's requests page show every state. Days are counted from the day the seed
# runs and stay clear of DEMO_REQUESTS (days 1-4) and the showcase (day 2), so confirmed viewings never clash.
# (unit of the story seller, day, hour)
RICH_DEMO_BUYER_PHONE = "0901111222"
RICH_DEMO_MARKER = "seed.rich_demo"
# New buyers asking the story seller: (name, phone, budget min/max in tỷ)
RICH_DEMO_BUYERS = {
    "vinh": ("Đinh Quang Vinh", "0938100121", 4.5, 5.0),
    "trang": ("Tạ Thu Trang", "0938100122", 3.8, 4.4),
    "duc": ("Lương Minh Đức", "0938100123", 3.0, 3.5),
    "ngoc": ("Hồ Bảo Ngọc", "0938100124", 3.8, 4.5),
    "tuan": ("Phùng Anh Tuấn", "0938100125", 3.5, 4.0),
    "linh": ("Kiều Mỹ Linh", "0938100126", 3.5, 4.0),
    "nam": ("Võ Thành Nam", "0938100127", 4.5, 5.2),
}


def ensure_rich_demo(db: Session) -> str:
    """Add the rich demo cases once (see RICH_DEMO_*). Run after --ensure-slots (with enough days) and the showcase.

    Buyer Nguyễn Văn An: waiting for the owner, confirmed (with its viewing pass), asked for a new time, declined
    with times the owner suggested, cancelled, past viewing waiting for the owner's record, viewed (asked how it
    went), interested, recorded as a no-show. Seller Hoàng Thị Lan: more requests to answer (one due soon), viewings
    coming up, new times asked for, a past viewing to record, a buyer interested after a viewing.
    """
    from src.core.actor import Actor
    from src.db.models import AuditLog
    from src.models.booking import BookingCreate, RescheduleRequest
    from src.services import audit, booking_service, viewing_outcome_service

    if db.scalar(select(AuditLog.id).where(AuditLog.action == RICH_DEMO_MARKER)) is not None:
        return "already added"
    an = db.scalar(select(User).where(User.phone == RICH_DEMO_BUYER_PHONE, User.role == UserRole.CUSTOMER))
    lan = db.scalar(select(User).where(User.phone == STORY_SELLER_PHONE, User.role == UserRole.OWNER))
    tuan = db.scalar(select(User).where(User.phone == "0918765432", User.role == UserRole.OWNER))
    if an is None or lan is None or tuan is None:
        return "skipped (demo accounts missing)"
    available = Property.status == PropertyStatus.AVAILABLE
    lan_homes = {p.unit_code: p for p in db.scalars(select(Property).where(Property.owner_id == lan.id, available))}
    units = [u for u in ("S1.08-2410", "S1.08-1026", "S2.01-0718", "S1.08-0904") if u in lan_homes]
    if len(units) < 4:
        return "skipped (the story seller's homes are missing)"
    h1, h2, h3, h4 = (lan_homes[u] for u in units)
    # Tuấn's homes An has no deal on yet, for the past viewings
    an_deals = set(db.scalars(select(Deal.property_id).where(Deal.buyer_id == an.id)))
    tuans = [
        p
        for p in db.scalars(select(Property).where(Property.owner_id == tuan.id, available).order_by(Property.id))
        if p.id not in an_deals
    ][:5]
    if len(tuans) < 5:
        return "skipped (not enough homes of the second seller)"

    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz).date()

    def at(day: int, hour: int) -> datetime:
        return datetime.combine(today + timedelta(days=day), time(hour, 0), tzinfo=tz)

    def past(buyer: User, prop: Property, day: int, hour: int, status: str) -> int:
        """A past viewing at the first of a few hours when the home's owner had no other confirmed viewing."""
        from src.services.availability_service import owner_busy

        for h in (hour, 10, 15, 11, 17):
            start = at(day, h)
            if status not in ("CONFIRMED", "RESCHEDULE_REQUESTED") or not owner_busy(
                db, prop.owner_id, start, start + timedelta(minutes=SLOT_MINUTES)
            ):
                return _past_booking(db, buyer, prop, start, status)
        raise RuntimeError(f"no free past hour for {prop.unit_code}")

    def ask(buyer: User, prop: Property, day: int, hour: int, note: str | None = None) -> int:
        return booking_service.create_request(
            db, Actor(buyer), BookingCreate(property_id=prop.id, start_at=at(day, hour), note=note)
        ).id

    buyers = {key: _showcase_buyer(db, *data) for key, data in RICH_DEMO_BUYERS.items()}
    if any(b is None for b in buyers.values()):
        return "skipped (rich demo buyers already exist)"
    owner_lan, buyer_an = Actor(lan), Actor(an)
    done: list[str] = []

    # ---- Nguyễn Văn An ----
    ask(an, h4, 5, 14, "Đi cùng vợ, muốn xem kỹ ban công và hướng nắng")
    done.append("An: waiting for the owner")
    booking_service.approve(db, owner_lan, ask(an, h2, 5, 9, "Cần chỗ để ô tô"))
    done.append("An: confirmed")
    moved = ask(an, h1, 6, 14)
    booking_service.approve(db, owner_lan, moved)
    booking_service.reschedule(db, buyer_an, moved, RescheduleRequest(start_at=at(7, 16)))
    done.append("An: new time asked")
    declined = ask(an, h3, 5, 16)
    booking_service.reject(
        db, owner_lan, declined, "Chiều hôm đó tôi bận, mời anh chọn giờ khác", suggested_starts=[at(8, 14), at(9, 9)]
    )
    done.append("An: declined with suggested times")
    booking_service.cancel(db, buyer_an, ask(an, tuans[0], 5, 16))
    done.append("An: cancelled")
    past(an, tuans[1], -1, 14, "CONFIRMED")
    done.append("An: past viewing to record")
    past(an, tuans[2], -2, 9, "COMPLETED")
    done.append("An: viewed")
    liked = past(an, tuans[3], -3, 16, "COMPLETED")
    viewing_outcome_service.feedback(db, buyer_an, liked, "INTERESTED", "Thích view và cách bố trí bếp")
    done.append("An: interested")
    past(an, tuans[4], -1, 9, "NO_SHOW")
    done.append("An: recorded as a no-show")

    # ---- Hoàng Thị Lan ----
    ask(buyers["vinh"], h2, 1, 16, "Muốn xem sớm vì đang cân nhắc 2 căn")  # due in less than a day
    ask(buyers["trang"], h3, 7, 9, "Gia đình 3 người, quan tâm trường học gần đó")
    ask(buyers["duc"], h1, 9, 16)
    booking_service.approve(db, owner_lan, ask(buyers["ngoc"], h3, 8, 9))
    later = ask(buyers["tuan"], h4, 6, 9)
    booking_service.approve(db, owner_lan, later)
    booking_service.reschedule(db, Actor(buyers["tuan"]), later, RescheduleRequest(start_at=at(9, 14)))
    past(buyers["linh"], h4, -1, 16, "CONFIRMED")
    seen = past(buyers["nam"], h2, -2, 14, "COMPLETED")
    viewing_outcome_service.feedback(db, Actor(buyers["nam"]), seen, "INTERESTED", "Rất ưng, muốn trao đổi thêm")
    done.append("Lan: 3 to answer, 1 coming up, 1 new time asked, 1 to record, 1 buyer interested")

    audit.record(db, None, RICH_DEMO_MARKER, "user", an.id, after={"cases": done})
    db.commit()
    return ", ".join(done)


SLOT_HOURS = (9, 14, 16)
SLOT_MINUTES = 30
DEMO_OWNER_IDS = {uid for uid, role, *_ in USERS if role == UserRole.OWNER}


def _slot_starts(days: int) -> list[datetime]:
    """Viewing slot start times at 9:00 / 14:00 / 16:00 (Vietnam time) for `days` days from tomorrow."""
    tz = ZoneInfo(get_settings().timezone)
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    return [
        datetime.combine(tomorrow + timedelta(days=day), time(hour, 0), tzinfo=tz)
        for day in range(days)
        for hour in SLOT_HOURS
    ]


def _slots(props: list[Property]) -> list[AvailabilitySlot]:
    return [
        AvailabilitySlot(property_id=prop.id, start_at=start, end_at=start + timedelta(minutes=SLOT_MINUTES))
        for prop in props
        if prop.status == PropertyStatus.AVAILABLE
        for start in _slot_starts(3)
    ]


def ensure_slots(db: Session, days: int = 7) -> int:
    """Top up the demo owners' viewing slots for the next `days` days (a long-running demo never runs out).

    Only seeded demo owners are touched; real sellers manage their own availability.
    Slots that already exist or overlap an existing one are skipped. Returns how many were added.
    """
    owners = DEMO_OWNER_IDS | set(db.scalars(select(User.id).where(User.phone == STORY_OTHER_SELLER[1])))
    props = db.scalars(
        select(Property).where(Property.owner_id.in_(owners), Property.status == PropertyStatus.AVAILABLE)
    ).all()
    added = 0
    for prop in props:
        for start in _slot_starts(days):
            end = start + timedelta(minutes=SLOT_MINUTES)
            taken = db.scalar(
                select(AvailabilitySlot.id).where(
                    AvailabilitySlot.property_id == prop.id,
                    AvailabilitySlot.start_at < end,
                    AvailabilitySlot.end_at > start,
                )
            )
            if taken is None:
                db.add(AvailabilitySlot(property_id=prop.id, start_at=start, end_at=end))
                added += 1
    db.commit()
    return added


def has_data(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def _ownership_verifications() -> list[PropertyOwnershipVerification]:
    """Red book records from data/property_ownership_verifications_seed.csv (feature/Baor data set).

    Seeded OTP codes are not imported: codes are only ever stored hashed, and the seeded one has expired.
    """
    tz = ZoneInfo("Asia/Ho_Chi_Minh")

    def when(value: str) -> datetime | None:
        return datetime.fromisoformat(value).replace(tzinfo=tz) if value else None

    with open(DATA_DIR / "property_ownership_verifications_seed.csv", encoding="utf-8", newline="") as f:
        return [
            PropertyOwnershipVerification(
                id=int(row["verification_id"]),
                user_id=int(row["user_id"]) if row["user_id"] else None,
                red_book_holder_name=row["red_book_holder_name"],
                red_book_code=row["red_book_code"],
                owner_phone=row["owner_phone"],
                status=OwnershipVerificationStatus(row["status"].upper()),
                otp_attempts=int(row["otp_attempts"] or 0),
                verified_at=when(row["verified_at"]),
                created_at=when(row["created_at"]),
                updated_at=when(row["updated_at"]),
            )
            for row in csv.DictReader(f)
        ]


def _sync_red_book_id_sequence(db: Session) -> None:
    # Rows are inserted with explicit ids; move the sequence past them
    db.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('property_ownership_verifications', 'id'), "
            "(SELECT COALESCE(max(id), 1) FROM property_ownership_verifications))"
        )
    )


def ensure_red_books(db: Session) -> int:
    """Add the demo red books that are missing (by red book code) to an existing database.

    `seed()` only loads them into an empty database, so a database seeded before red books existed
    would otherwise keep an empty table. Existing rows are never changed: a real seller may already
    have verified one or listed a property with it. A row whose user or id does not fit this database
    is still added: without an owner, or with the next free id. Returns how many were added.
    """
    existing_codes = set(db.scalars(select(PropertyOwnershipVerification.red_book_code)))
    existing_ids = set(db.scalars(select(PropertyOwnershipVerification.id)))
    user_ids = set(db.scalars(select(User.id)))
    added = 0
    for record in _ownership_verifications():
        if record.red_book_code in existing_codes:
            continue
        if record.user_id is not None and record.user_id not in user_ids:
            record.user_id = None
        if record.id in existing_ids:
            record.id = None  # let the sequence pick one
        else:
            existing_ids.add(record.id)
        db.add(record)
        db.flush()  # a sequence-assigned id must not collide with a later explicit one
        added += 1
    _sync_red_book_id_sequence(db)
    db.commit()
    return added


# The investor's record of the home behind each demo red book that no listing uses yet
# (code -> building, unit, bedrooms, bathrooms, area m², floor, direction). Red books behind a listing take
# the listing's facts instead (see ensure_red_book_units).
RED_BOOK_UNITS = {
    "SD-2019-0456123": ("S1.08", "S1.08-3105", 2, 2, "69.5", 31, Direction.SE),
    "SD-2020-0456124": ("R1.02", "R1.02-2808", 3, 2, "86.0", 28, Direction.S),
    "SD-2023-0456125": ("TK1", "TK1-1506", 2, 2, "74.2", 15, Direction.E),
    "SD-2022-0991234": ("GS3", "GS3-0907", 1, 1, "47.5", 9, Direction.NW),
    "SD-2017-0332211": ("S2.01", "S2.01-1911", 2, 2, "67.0", 19, Direction.SW),
    "SD-2015-0110022": ("W2", "W2-1203", 3, 2, "95.0", 12, Direction.N),
    "SD-2019-0778905": ("S1.08", "S1.08-2702", 2, 2, "64.8", 27, Direction.NE),
    "SD-2020-0778906": ("R1.02", "R1.02-1407", 2, 2, "70.3", 14, Direction.SE),
    "SD-2022-0778907": ("SA2", "SA2-2210", 3, 2, "88.6", 22, Direction.E),
    "SD-2025-0778908": ("S7.02", "S7.02-1608", 2, 2, "68.0", 16, Direction.SE),
}

_UNIT_FIELDS = ("building_id", "unit_code", "property_type", "area_m2", "bedrooms", "bathrooms", "floor", "direction")


def _generated(code: str) -> bool:
    """A red book made up by ensure_red_book_units for a listing seeded before red books existed."""
    return re.fullmatch(r"SD-\d{4}-9\d{6}", code) is not None


def _copy_unit(book: PropertyOwnershipVerification, prop: Property) -> None:
    for field in _UNIT_FIELDS:
        setattr(book, field, getattr(prop, field))


def ensure_red_book_units(db: Session) -> str:
    """Every listing is backed by a verified red book that carries the home's facts; no uploaded documents.

    - A red book behind a listing gets that listing's facts (building, unit, type, area, rooms, floor, direction).
    - A listing without a red book (seeded before red book verification) gets a verified one in its owner's name.
    - Demo red books not listed yet get their facts from RED_BOOK_UNITS.
    - The made-up "ownership documents" of the old seed are removed.
    Safe to run again. Run after the seller story, which links Lan's listings to her own red books.
    """
    owners = {u.id: u for u in db.scalars(select(User).where(User.role == UserRole.OWNER))}
    buildings = {b.code: b for b in db.scalars(select(Building))}
    books = {b.id: b for b in db.scalars(select(PropertyOwnershipVerification))}
    filled = created = 0
    for prop in db.scalars(select(Property).order_by(Property.id)):
        book = books.get(prop.verification_id) if prop.verification_id else None
        if book is None:
            owner = owners.get(prop.owner_id)
            if owner is None:
                continue
            book = PropertyOwnershipVerification(
                user_id=owner.id,
                red_book_holder_name=owner.full_name,
                red_book_code=f"SD-{prop.created_at.year}-9{prop.id:06d}",
                owner_phone=owner.phone or "",
                status=OwnershipVerificationStatus.VERIFIED,
                otp_attempts=1,
                verified_at=prop.created_at,
            )
            db.add(book)
            db.flush()
            prop.verification_id = book.id
            created += 1
        if book.unit_code is None:
            _copy_unit(book, prop)
            filled += 1
    for code, (building, unit, beds, baths, area, floor, direction) in RED_BOOK_UNITS.items():
        book = next((b for b in books.values() if b.red_book_code == code), None)
        if book is None or book.unit_code is not None or building not in buildings:
            continue
        book.building_id = buildings[building].id
        book.unit_code = unit
        book.property_type = PropertyType.APARTMENT
        book.bedrooms, book.bathrooms, book.area_m2, book.floor, book.direction = (
            beds,
            baths,
            Decimal(area),
            floor,
            direction,
        )
        filled += 1
    removed = db.execute(delete(PropertyMedia).where(PropertyMedia.kind == MediaKind.OWNERSHIP_DOC)).rowcount
    # There are no drafts any more: a listing is sent for review when it is posted
    drafts = db.execute(
        update(Property).where(Property.status == PropertyStatus.DRAFT).values(status=PropertyStatus.PENDING_REVIEW)
    ).rowcount
    # The old seed's draft said so in its description
    db.execute(
        update(Property)
        .where(Property.description == "Bản nháp, chưa gửi duyệt.")
        .values(description="Căn 2PN, chờ Ban quản trị duyệt.")
    )
    # Listings of the old seed with placeholder units ("S1.08-X02", all 70 m² at 3,5 tỷ on floor 10)
    taken = set(db.scalars(select(Property.unit_code)))
    for prop in db.scalars(select(Property).where(Property.unit_code.like("%-X0_"))):
        match = _PLACEHOLDER_UNIT.match(prop.unit_code)
        if match is None:
            continue
        unit, beds, area, floor, price = EXTRA_UNITS[int(match.group(2)) - 1]
        code = f"{match.group(1)}-{unit}"
        if code in taken:
            continue
        taken.add(code)
        prop.unit_code, prop.bedrooms, prop.area_m2, prop.floor, prop.price_vnd = (
            code,
            beds,
            Decimal(area),
            floor,
            price,
        )
        if prop.verification is not None and _generated(prop.verification.red_book_code):
            _copy_unit(prop.verification, prop)
    for prop in db.scalars(select(Property).where(Property.description.like("Căn % m² tầng %"))):
        prop.description = _SEEDED_AREA.sub(r",", prop.description)
    db.commit()
    return (
        f"{created} red book(s) added for older listings, {filled} given their home's facts, "
        f"{removed} document(s) removed, {drafts} draft(s) sent for review"
    )


def ensure_sellers_verified(db: Session) -> int:
    """Sellers with a verified red book are verified sellers (the operator no longer reviews sellers).

    Kept out of the test seed, where an unverified seller is part of the data. Returns how many changed.
    """
    with_books = select(PropertyOwnershipVerification.user_id).where(
        PropertyOwnershipVerification.status == OwnershipVerificationStatus.VERIFIED
    )
    changed = db.execute(
        update(SellerProfile)
        .where(
            SellerProfile.user_id.in_(with_books),
            SellerProfile.verification_status != SellerVerificationStatus.VERIFIED,
        )
        .values(verification_status=SellerVerificationStatus.VERIFIED, rejection_reason=None)
    ).rowcount
    db.commit()
    return changed


def seed(db: Session, *, reset: bool = False) -> None:
    if reset:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    elif has_data(db):
        raise SystemExit("Database already has data. Use --reset to wipe it (dev only).")

    pw = hash_password(SEED_PASSWORD)
    for uid, role, name, phone, email, status in USERS:
        # Buyers and sellers sign in with phone + OTP only; only operators have a password
        password_hash = pw if role == UserRole.INVESTOR_OPERATOR else None
        db.add(
            User(
                id=uid, role=role, full_name=name, phone=phone, email=email, status=status, password_hash=password_hash
            )
        )
    db.flush()
    for uid, role, *_, status in USERS:
        if role == UserRole.CUSTOMER:
            db.add(BuyerProfile(user_id=uid))
        elif role == UserRole.OWNER:
            # Active owners are verified; the PENDING_VERIFICATION one waits in the operator queue
            verified = status == UserStatus.ACTIVE
            db.add(
                SellerProfile(
                    user_id=uid,
                    verification_status=SellerVerificationStatus.VERIFIED
                    if verified
                    else SellerVerificationStatus.PENDING,
                    id_document_s3_key=f"private/sellers/{uid}/cccd.jpg",
                    verified_by=7 if verified else None,
                )
            )

    red_books = _ownership_verifications()
    db.add_all(red_books)

    projects = {code: Project(code=code, name=name, city=city, district=d) for code, name, city, d in PROJECTS}
    db.add_all(projects.values())
    buildings = [
        Building(project=projects[p], code=c, name=n, total_floors=f, lat=Decimal(lat), lng=Decimal(lng))
        for p, c, n, f, lat, lng in BUILDINGS
    ]
    db.add_all(buildings)
    db.flush()

    props = _properties(random.Random(42), buildings)
    db.add_all(props)
    db.flush()
    db.add_all(_media(props))
    db.add_all(_slots(props))
    # Explicit ids were used for users; move the sequence past them
    db.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users))"))
    _sync_red_book_id_sequence(db)
    db.commit()
    listings = ensure_listings(db)
    print(
        f"Seeded {len(USERS)} users, {len(red_books)} red books, {len(projects)} projects, "
        f"{len(buildings)} buildings, {len(props) + listings} properties."
    )
    print(f"Operator seed accounts use password: {SEED_PASSWORD}; buyers and sellers sign in with phone + OTP")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed BookingBot demo data")
    parser.add_argument("--reset", action="store_true", help="Wipe all tables first (dev only)")
    parser.add_argument("--if-empty", action="store_true", help="Seed only when the database has no users yet")
    parser.add_argument(
        "--ensure-slots",
        type=int,
        nargs="?",
        const=7,
        metavar="DAYS",
        help="Top up demo owners' viewing slots for the next DAYS days (default 7)",
    )
    parser.add_argument(
        "--ensure-listings",
        action="store_true",
        help="Add the extra demo listings missing from an existing database (never changes existing rows)",
    )
    parser.add_argument(
        "--ensure-requests",
        action="store_true",
        help="Demo buyers and viewing requests of every kind for the story seller (see DEMO_REQUESTS)",
    )
    parser.add_argument(
        "--ensure-rich-demo",
        action="store_true",
        help="Every case for the demo buyer Nguyễn Văn An and more requests for the story seller (once)",
    )
    parser.add_argument(
        "--ensure-showcase",
        action="store_true",
        help="More demo cases: uploaded photos, overlapping requests, a viewing to record, a dispute, a locked red book",
    )
    parser.add_argument(
        "--ensure-photos",
        action="store_true",
        help="Give demo listings illustrative interior photos (replaces the seed's placeholder cover only)",
    )
    parser.add_argument(
        "--ensure-seller-story",
        action="store_true",
        help="Demo seller Hoàng Thị Lan: 8 verified red books, 4 homes on sale (see STORY_*)",
    )
    parser.add_argument(
        "--ensure-sellers-verified",
        action="store_true",
        help="Mark sellers with a verified red book as verified sellers",
    )
    parser.add_argument(
        "--ensure-red-book-units",
        action="store_true",
        help="Back every listing with a verified red book carrying the home's facts; drop uploaded documents",
    )
    parser.add_argument(
        "--ensure-red-books",
        action="store_true",
        help="Add demo red books missing from an existing database (never changes existing rows)",
    )
    args = parser.parse_args()
    with get_sessionmaker()() as session:
        if args.if_empty and has_data(session):
            print("Database already has data; skipping seed.")
        else:
            seed(session, reset=args.reset)
        if args.ensure_red_books:
            print(f"Added {ensure_red_books(session)} red book(s).")
        if args.ensure_listings:
            print(f"Added {ensure_listings(session)} demo listing(s).")
        if args.ensure_photos:
            print(f"Added photos to {ensure_photos(session)} listing(s).")
        if args.ensure_seller_story:
            print(f"Seller story: {ensure_seller_story(session)}.")
        # After the seller story, which links Lan's listings to her own red books
        if args.ensure_red_book_units:
            print(f"Red books: {ensure_red_book_units(session)}.")
        if args.ensure_sellers_verified:
            print(f"Verified {ensure_sellers_verified(session)} seller(s) by their red book.")
        if args.ensure_slots:
            print(f"Added {ensure_slots(session, args.ensure_slots)} demo viewing slot(s).")
        # Last: the demo requests book the slots topped up above
        if args.ensure_requests:
            print(f"Added {ensure_demo_requests(session)} demo viewing request(s).")
        if args.ensure_showcase:
            print(f"Showcase: {ensure_showcase(session)}.")
        if args.ensure_rich_demo:
            print(f"Rich demo: {ensure_rich_demo(session)}.")
