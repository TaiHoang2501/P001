"""Test setup.

Tests run against a real PostgreSQL database (the anti-double-booking guarantee lives in
Postgres constraints, so SQLite would not test it). The test DB is TEST_DATABASE_URL, or
DATABASE_URL with "_test" appended to the database name. It is created and migrated
automatically, and every test starts from freshly seeded data.
"""

import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.config import Settings, get_settings


def _test_database_url() -> str:
    settings = Settings()
    if settings.test_database_url:
        return settings.test_database_url
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


# Must happen before the app/engine are created so every module sees the test DB
TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
# Never touch the real media storage configured in .env; storage tests patch storage_service instead
for _var in ("MEDIA_BASE_URL", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
    os.environ[_var] = ""
get_settings.cache_clear()

from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from alembic import command  # noqa: E402
from src.db.seed import ensure_red_book_units, seed  # noqa: E402
from src.db.session import get_engine, get_sessionmaker  # noqa: E402
from src.main import app  # noqa: E402


def _create_database_if_missing(url_str: str) -> None:
    url = make_url(url_str)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    _create_database_if_missing(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def seeded_db(_migrated_database):
    """Fresh demo data for every test (users 1-3 customers, 4-6 owners, 7-8 operators)."""
    with get_sessionmaker()() as db:
        seed(db, reset=True)
        # Like a deployed demo database: every listing backed by a verified red book with the home's facts
        ensure_red_book_units(db)
    yield


@pytest.fixture
def db():
    session = get_sessionmaker()()
    yield session
    session.close()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests."""
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
