from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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

    # LLM (spec §9.1: Gemini or OpenAI; also any model through OpenRouter or Groq, both OpenAI-compatible)
    llm_provider: Literal["openai", "google", "openrouter", "groq"] = "openai"
    openai_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Empty = the provider's default (gpt-4o-mini / gemini-flash-latest / openai/gpt-4o-mini on OpenRouter /
    # openai/gpt-oss-120b on Groq)
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
        return {
            "google": self.google_api_key,
            "openrouter": self.openrouter_api_key,
            "groq": self.groq_api_key,
        }.get(self.llm_provider, self.openai_api_key)

    @property
    def llm_model(self) -> str:
        defaults = {"google": "gemini-flash-latest", "openrouter": "openai/gpt-4o-mini", "groq": "openai/gpt-oss-120b"}
        return self.model_name or defaults.get(self.llm_provider, "gpt-4o-mini")

    @property
    def llm_fallback_model(self) -> str | None:
        defaults = {"google": "gemini-flash-lite-latest", "groq": "openai/gpt-oss-20b"}
        name = self.model_fallback_name or defaults.get(self.llm_provider, "")
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
    # A viewing is offered and booked at least this long ahead, so the seller has time to answer and get there
    viewing_min_notice_minutes: int = Field(default=120, ge=0, le=24 * 60)

    # Hours a seller has to answer a viewing request before an operator is asked (TBD in spec §10 Q8)
    seller_response_hours: int = Field(default=24, ge=1)
    # ...and at the latest this long before the viewing, so an unanswered request reaches the investor's staff in time
    seller_response_lead_minutes: int = Field(default=60, ge=0)

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
    # Photos uploaded from the seller's device are served by this API; this is its public address, so the
    # web app on another domain can show them (Render sets RENDER_EXTERNAL_URL). Empty: same-origin path.
    public_api_url: str = Field(default="", validation_alias=AliasChoices("PUBLIC_API_URL", "RENDER_EXTERNAL_URL"))
    media_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    # After a viewing, the owner records whether the buyer came; unrecorded viewings close after this many hours
    viewing_outcome_hours: int = Field(default=48, ge=1)
    # Photos one listing can have
    media_max_photos: int = Field(default=10, ge=1)
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
    # Wrong holder name / red book code attempts one seller account may make per hour (stops guessing codes)
    ownership_claim_failures_per_hour: int = Field(default=5, ge=1)
    # Developer traces of chat turns (ai_turns) and unclaimed guest conversations are kept this many days
    ai_trace_retention_days: int = Field(default=180, ge=1)
    # Langfuse (LLM observability) for chat turns; off when the keys are empty and always off in tests
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com", validation_alias=AliasChoices("langfuse_base_url", "langfuse_host")
    )
    # Share of chat turns sent to Langfuse (1.0 = all)
    langfuse_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key) and self.app_env != "test"

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
