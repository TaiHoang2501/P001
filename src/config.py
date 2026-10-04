from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "BookingBot API"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    timezone: str = "Asia/Ho_Chi_Minh"

    # LLM (spec §9.1: Gemini or OpenAI)
    llm_provider: Literal["openai", "google"] = "openai"
    openai_api_key: str = ""
    google_api_key: str = ""
    # Empty = the provider's default (gpt-4o-mini / gemini-flash-latest)
    model_name: str = ""
    # Used when the main model fails (e.g. Gemini "high demand" 503). Empty = provider default, "none" = off
    model_fallback_name: str = ""
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # Keep a chat turn from hanging for minutes when the provider is overloaded
    llm_timeout_seconds: float = Field(default=45, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)

    @property
    def otp_code_visible(self) -> bool:
        return self.app_env != "production" if self.otp_expose_code is None else self.otp_expose_code

    @property
    def llm_api_key(self) -> str:
        return self.google_api_key if self.llm_provider == "google" else self.openai_api_key

    @property
    def llm_model(self) -> str:
        return self.model_name or ("gemini-flash-latest" if self.llm_provider == "google" else "gpt-4o-mini")

    @property
    def llm_fallback_model(self) -> str | None:
        name = self.model_fallback_name or ("gemini-flash-lite-latest" if self.llm_provider == "google" else "")
        return None if name in ("", "none") or name == self.llm_model else name

    # Database (PostgreSQL 15+ required: btree_gist exclusion constraints, pg_trgm)
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bookingbot"
    # Used by pytest; defaults to database_url with a "_test" suffix on the DB name
    test_database_url: str = ""

    # Auth
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24, ge=5)

    # Viewing scheduling (spec §4.8; viewing length and buffer are TBD in §10 Q12-13)
    viewing_duration_minutes: int = Field(default=30, ge=15, le=240)
    viewing_step_minutes: int = Field(default=30, ge=5, le=120)
    viewing_max_proposals: int = Field(default=3, ge=1, le=10)
    viewing_alternative_days: int = Field(default=14, ge=1, le=60)

    # Hours a seller has to answer a viewing request before an operator is asked (TBD in spec §10 Q8)
    seller_response_hours: int = Field(default=24, ge=1)

    # Agent memory: "postgres" keeps conversations across restarts (falls back to "memory" if it cannot connect)
    agent_memory: Literal["postgres", "memory"] = "postgres"
    # Minutes a viewing request may wait for the seller before the agent sends the buyer alternatives
    agent_followup_minutes: int = Field(default=60, ge=5)
    # Let the model word follow-ups and reminders (facts are fixed; falls back to templates on any failure)
    agent_personalize: bool = True

    # In-process periodic jobs (hold expiry, reminders); disabled under APP_ENV=test
    jobs_enabled: bool = True
    job_interval_seconds: int = Field(default=60, ge=5)

    # Media: public URL = media_base_url + s3_key (e.g. a CloudFront domain); empty means return the key
    media_base_url: str = ""
    # S3-compatible object storage (Supabase Storage, Cloudflare R2, AWS S3). Empty endpoint/keys = uploads disabled.
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    # Photos/floor plans/videos, served as media_base_url + key
    s3_public_bucket: str = ""
    # Ownership documents (PII), only reachable through short-lived presigned URLs
    s3_private_bucket: str = ""
    media_signed_url_seconds: int = Field(default=600, ge=60, le=3600)

    @property
    def storage_enabled(self) -> bool:
        return all(
            (
                self.s3_endpoint_url,
                self.s3_access_key_id,
                self.s3_secret_access_key,
                self.s3_public_bucket,
                self.s3_private_bucket,
            )
        )

    # OTP login (spec §4.17); SMS/Zalo provider is TBD, so codes are only logged for now
    otp_ttl_seconds: int = Field(default=300, ge=30)
    otp_max_attempts: int = Field(default=5, ge=1)
    otp_max_requests: int = Field(default=5, ge=1, description="Codes per target per rate-limit window")
    otp_rate_window_minutes: int = Field(default=15, ge=1)
    # Return the code in the API response (no SMS/Zalo provider yet). Default: everywhere except production;
    # a public demo with fake data can turn it on explicitly.
    otp_expose_code: bool | None = None

    # Recommendation scoring weights (spec §4.6: TBD, calibrate with real data)
    score_weight_price: float = 0.25
    score_weight_area: float = 0.15
    score_weight_bedrooms: float = 0.15
    score_weight_direction: float = 0.10
    score_weight_view: float = 0.15
    score_weight_floor: float = 0.10
    score_weight_furnishing: float = 0.10

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and (self.jwt_secret == "change-me-in-env" or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random string of at least 32 characters in production")
        return self

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _use_psycopg3(cls, url: str) -> str:
        # Accept plain postgresql:// URLs but always use the psycopg (v3) driver
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
