"""Where the agent keeps conversations: PostgreSQL (survives restarts, shared by workers) or process memory.

Opened once at start-up from the app lifespan. Any failure (database unreachable, or the Windows Proactor
event loop that psycopg's async driver cannot use; run uvicorn with --reload there) falls back to process
memory with a warning, so the API still starts.
"""

import asyncio
import logging

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.agents import graph as agent_graph
from src.config import get_settings

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SECONDS = 10


def _conninfo(database_url: str) -> str:
    # SQLAlchemy URL -> libpq URL (psycopg reads ?sslmode=require etc. as is)
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


async def open_memory() -> AsyncConnectionPool | None:
    """Use Postgres for agent memory when configured; returns the pool to close at shutdown."""
    settings = get_settings()
    if settings.agent_memory != "postgres":
        return None
    pool = AsyncConnectionPool(
        _conninfo(settings.database_url),
        min_size=1,
        max_size=5,
        open=False,
        # autocommit + no prepared statements: required by the saver, and safe behind Neon's pooler
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        await asyncio.wait_for(pool.open(wait=True), _CONNECT_TIMEOUT_SECONDS)
        saver = AsyncPostgresSaver(pool)
        await saver.setup()  # creates/migrates its own checkpoint tables
    except Exception as e:
        logger.warning("Agent memory falls back to process memory (Postgres unavailable: %s)", e)
        await pool.close()
        return None
    agent_graph.use_checkpointer(saver)
    logger.info("Agent memory: PostgreSQL")
    return pool


async def close_memory(pool: AsyncConnectionPool | None) -> None:
    if pool is not None:
        agent_graph.use_checkpointer(None)
        await pool.close()
