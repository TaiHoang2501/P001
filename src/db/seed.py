"""Load MVP demo data.

Usage:
    python -m src.db.seed           # only if the database is empty
    python -m src.db.seed --reset   # wipe all rows first (dev only!)

Seeded buyers and operators use the password below; sellers sign in with phone + OTP.
Never run this against production.
"""

import argparse
import csv
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.security import hash_password
from src.db.models import (
    AvailabilitySlot,
    Base,
    Building,
    BuyerProfile,
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
                description=f"Căn {label} {area} m² tầng {floor}, {VIEW_TEXT[view]}, {FURNISH_TEXT[furnishing]}.",
                status=PropertyStatus.AVAILABLE,
            )
        )
    # Moderation queue + draft + an unverified owner (must never appear in search)
    extra = [
        (5, PropertyStatus.PENDING_REVIEW, "Căn 2PN view công viên, đang chờ duyệt tin."),
        (4, PropertyStatus.PENDING_REVIEW, "Căn 3PN góc, chờ Ban quản trị duyệt."),
        (4, PropertyStatus.DRAFT, "Bản nháp, chưa gửi duyệt."),
        (6, PropertyStatus.AVAILABLE, "Tin của chủ nhà chưa xác minh - không được hiển thị."),
    ]
    for j, (owner_id, status, desc) in enumerate(extra):
        building = buildings[j]
        props.append(
            Property(
                owner_id=owner_id,
                building=building,
                unit_code=f"{building.code}-X{j + 1:02d}",
                property_type=PropertyType.APARTMENT,
                bedrooms=2,
                bathrooms=2,
                area_m2=Decimal("70.0"),
                floor=10,
                price_vnd=3_500_000_000,
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
    """Every seeded listing has a private ownership document and one cover photo."""
    media = []
    for prop in props:
        media.append(
            PropertyMedia(
                property_id=prop.id,
                kind=MediaKind.OWNERSHIP_DOC,
                s3_key=f"private/properties/{prop.id}/so-hong.pdf",
                content_type="application/pdf",
                is_public=False,
            )
        )
        media.append(
            PropertyMedia(
                property_id=prop.id,
                kind=MediaKind.IMAGE,
                s3_key=f"public/properties/{prop.id}/cover.jpg",
                content_type="image/jpeg",
            )
        )
    return media


def _slots(props: list[Property]) -> list[AvailabilitySlot]:
    tz = ZoneInfo(get_settings().timezone)
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    slots = []
    for prop in props:
        if prop.status != PropertyStatus.AVAILABLE:
            continue
        for day in range(3):
            for hour in (9, 14, 16):
                start = datetime.combine(tomorrow + timedelta(days=day), time(hour, 0), tzinfo=tz)
                slots.append(
                    AvailabilitySlot(property_id=prop.id, start_at=start, end_at=start + timedelta(minutes=30))
                )
    return slots


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


def seed(db: Session, *, reset: bool = False) -> None:
    if reset:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    elif db.scalar(select(User.id).limit(1)) is not None:
        raise SystemExit("Database already has data. Use --reset to wipe it (dev only).")

    pw = hash_password(SEED_PASSWORD)
    for uid, role, name, phone, email, status in USERS:
        # Sellers sign in with phone + OTP only, so they get no password
        password_hash = None if role == UserRole.OWNER else pw
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
    db.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('property_ownership_verifications', 'id'), "
            "(SELECT max(id) FROM property_ownership_verifications))"
        )
    )
    db.commit()
    print(
        f"Seeded {len(USERS)} users, {len(red_books)} red books, {len(projects)} projects, "
        f"{len(buildings)} buildings, {len(props)} properties."
    )
    print(f"Buyer/operator seed accounts use password: {SEED_PASSWORD}; sellers sign in with phone + OTP")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed BookingBot demo data")
    parser.add_argument("--reset", action="store_true", help="Wipe all tables first (dev only)")
    args = parser.parse_args()
    with get_sessionmaker()() as session:
        seed(session, reset=args.reset)
