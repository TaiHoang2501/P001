import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import jobs
from src.agents import graph as agent_graph
from src.api.routers import (
    admin,
    auth,
    bookings,
    chat,
    deals,
    escalations,
    media,
    notifications,
    operator,
    owner,
    properties,
)
from src.config import get_settings
from src.core.errors import AgentUnavailableError, register_error_handlers
from src.services import agent_memory, llm_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    memory_pool = await agent_memory.open_memory() if settings.app_env != "test" else None
    if settings.app_env != "test":
        # Build the agent now (model SDK imports, graph): done lazily it held up the first chat ~20s on Cloud Run
        with contextlib.suppress(AgentUnavailableError):
            agent_graph.get_agent()
    job = None
    if settings.jobs_enabled and settings.app_env != "test":
        job = asyncio.create_task(jobs.run_forever())
    yield
    if job is not None:
        job.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await job
    await agent_memory.close_memory(memory_pool)
    llm_observability.shutdown()
    print("Shutting down...")


app = FastAPI(
    title="BookingBot API",
    description="BookingBot AI Agent — Vinhomes viewing booking backend",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(properties.router, prefix=API_PREFIX)
app.include_router(bookings.router, prefix=API_PREFIX)
app.include_router(bookings.passes, prefix=API_PREFIX)
app.include_router(deals.router, prefix=API_PREFIX)
app.include_router(owner.router, prefix=API_PREFIX)
app.include_router(operator.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(escalations.router, prefix=API_PREFIX)
app.include_router(media.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0", "environment": settings.app_env}
