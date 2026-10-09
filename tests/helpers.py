from httpx import AsyncClient

from src.db.seed import SEED_PASSWORD

# Seeded accounts (see src/db/seed.py)
CUSTOMER_AN = "an.nguyen@gmail.com"
CUSTOMER_BINH = "binh.tran@gmail.com"
OWNER_TUAN = "tuan.pham@gmail.com"  # owns even-indexed seed properties (ids 1, 3, 5, ...)
OWNER_LAN = "lan.hoang@gmail.com"  # owns odd-indexed seed properties (ids 2, 4, 6, ...)
OPERATOR = "operator@vinhomes.vn"
OWNER_KHOA = "khoa.do@gmail.com"  # seeded with a PENDING verification

# Sellers and buyers have no password: they sign in with phone + OTP (only operators use a password)
SELLER_PHONES = {OWNER_TUAN: "0918765432", OWNER_LAN: "0912345678", OWNER_KHOA: "0987654321"}
BUYER_PHONES = {CUSTOMER_AN: "0901111222", CUSTOMER_BINH: "0902222333"}

# Red books from data/property_ownership_verifications_seed.csv
TUAN_RED_BOOK = 1  # verified by Tuấn, not yet backing a listing
UNCLAIMED_RED_BOOK = {"id": 7, "red_book_holder_name": "Nguyễn Thị Hương", "red_book_code": "SD-2017-0332211"}
# The owner's phone on that red book: only an account signed in with it verifies the red book on its own
UNCLAIMED_RED_BOOK_PHONE = "0909888777"


async def auth(client: AsyncClient, identifier: str, password: str = SEED_PASSWORD) -> dict[str, str]:
    if identifier in SELLER_PHONES:
        return await otp_auth(client, SELLER_PHONES[identifier])
    if identifier in BUYER_PHONES:
        return await otp_auth(client, BUYER_PHONES[identifier])
    r = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def otp_auth(client: AsyncClient, phone: str, **signup: str) -> dict[str, str]:
    """Phone + OTP login (the dev API returns the code); pass full_name/role to sign up a new phone."""
    code = (await client.post("/api/v1/auth/otp/request", json={"target": phone})).json()["debug_code"]
    r = await client.post("/api/v1/auth/otp/verify", json={"target": phone, "code": code, **signup})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def first_free_slot(client: AsyncClient, property_id: int) -> dict:
    r = await client.get(f"/api/v1/properties/{property_id}/slots")
    assert r.status_code == 200, r.text
    return r.json()[0]
