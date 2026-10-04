"""Load MVP demo data.

Usage:
    python -m src.db.seed           # only if the database is empty
    python -m src.db.seed --reset   # wipe all rows first (dev only!)
    python -m src.db.seed --ensure-red-books  # add demo red books missing from an existing database
    python -m src.db.seed --if-empty --ensure-slots --ensure-red-books   # deploy start-up

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
            description=f"Căn 2PN {area} m² tầng {floor}, {VIEW_TEXT[view]}, {FURNISH_TEXT[furnishing]}.",
            status=PropertyStatus.AVAILABLE,
        )
        db.add(prop)
        added.append(prop)
    db.flush()
    db.add_all(_media(added))
    db.add_all(_slots(added))
    db.commit()
    return len(added)


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
    props = db.scalars(
        select(Property).where(Property.owner_id.in_(DEMO_OWNER_IDS), Property.status == PropertyStatus.AVAILABLE)
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


def seed(db: Session, *, reset: bool = False) -> None:
    if reset:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    elif has_data(db):
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
    _sync_red_book_id_sequence(db)
    db.commit()
    listings = ensure_listings(db)
    print(
        f"Seeded {len(USERS)} users, {len(red_books)} red books, {len(projects)} projects, "
        f"{len(buildings)} buildings, {len(props) + listings} properties."
    )
    print(f"Buyer/operator seed accounts use password: {SEED_PASSWORD}; sellers sign in with phone + OTP")


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
        if args.ensure_slots:
            print(f"Added {ensure_slots(session, args.ensure_slots)} demo viewing slot(s).")
