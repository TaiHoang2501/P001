from httpx import AsyncClient

from src.db.seed import SEED_PASSWORD

# Seeded accounts (see src/db/seed.py)
CUSTOMER_AN = "an.nguyen@gmail.com"
CUSTOMER_BINH = "binh.tran@gmail.com"
OWNER_TUAN = "tuan.pham@gmail.com"  # owns even-indexed seed properties (ids 1, 3, 5, ...)
OWNER_LAN = "lan.hoang@gmail.com"  # owns odd-indexed seed properties (ids 2, 4, 6, ...)
OPERATOR = "operator@vinhomes.vn"


async def auth(client: AsyncClient, identifier: str, password: str = SEED_PASSWORD) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def first_free_slot(client: AsyncClient, property_id: int) -> dict:
    r = await client.get(f"/api/v1/properties/{property_id}/slots")
    assert r.status_code == 200, r.text
    return r.json()[0]
