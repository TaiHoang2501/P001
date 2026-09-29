from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import auth, bookings, operator, owner, properties
from src.api.routes import router as agent_router
from src.config import get_settings
from src.core.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
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
app.include_router(owner.router, prefix=API_PREFIX)
app.include_router(operator.router, prefix=API_PREFIX)
# AI chat endpoints (owned by the AI workstream)
app.include_router(agent_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0", "environment": settings.app_env}
