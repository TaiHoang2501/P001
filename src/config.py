from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MAIN_MODELS = {
    "google": "gemini-flash-latest",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-opus-5-5",
}


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

    # LLM (spec §9.1: Gemini or OpenAI; also Claude, and any model through OpenRouter or Groq, both OpenAI-compatible)
    llm_provider: Literal["openai", "google", "openrouter", "groq", "anthropic"] = "openai"
    # Provider of the fallback model; empty = the same as llm_provider (e.g. Claude first, OpenRouter when it fails)
    llm_fallback_provider: Literal["", "openai", "google", "openrouter", "groq", "anthropic"] = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Empty = the provider's default (gpt-4o-mini / gemini-flash-latest / openai/gpt-4o-mini on OpenRouter /
    # openai/gpt-oss-120b on Groq / claude-opus-5-5 on Anthropic)
    model_name: str = ""
    # Used when the main model fails (e.g. Gemini "high demand" 503). Empty = provider default, "none" = off
    model_fallback_name: str = ""
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # Claude's thinking depth (low | medium | high | xhigh | max); empty = the model's default. Claude ignores
    # llm_temperature (current Claude models reject sampling parameters)
    llm_effort: Literal["", "low", "medium", "high", "xhigh", "max"] = ""
    # Keep a chat turn from hanging for minutes when the provider is overloaded
    llm_timeout_seconds: float = Field(default=45, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)

    @property
    def otp_code_visible(self) -> bool:
        if self.otp_provider == "firebase":
            # The code is Firebase's and goes by SMS only; we never see it
            return False
        return self.app_env != "production" if self.otp_expose_code is None else self.otp_expose_code

    def api_key_for(self, provider: str) -> str:
        return {
            "google": self.google_api_key,
            "openrouter": self.openrouter_api_key,
            "groq": self.groq_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider, self.openai_api_key)

    @property
    def llm_api_key(self) -> str:
        return self.api_key_for(self.llm_provider)

    @property
    def llm_model(self) -> str:
        return self.model_name or _MAIN_MODELS.get(self.llm_provider, "gpt-4o-mini")

    @property
    def llm_fallback_provider_name(self) -> str:
        return self.llm_fallback_provider or self.llm_provider

    @property
    def llm_fallback_model(self) -> str | None:
        provider = self.llm_fallback_provider_name
        if provider == self.llm_provider:
            name = self.model_fallback_name or {"google": "gemini-flash-lite-latest", "groq": "openai/gpt-oss-20b"}.get(
                provider, ""
            )
            if name == self.llm_model:
                return None
        else:
            # Another provider: its own main model unless named
            name = self.model_fallback_name or _MAIN_MODELS.get(provider, "gpt-4o-mini")
        if name in ("", "none") or not self.api_key_for(provider):
            return None
        return name

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
    # Demo data (scripts/start.sh seeds it); the jobs also top up the demo owners' viewing slots once a day
    seed_demo_data: bool = True

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

    # OTP login (spec §4.17). "local": we generate and check codes (sent to the server log only, no SMS);
    # "firebase": Firebase Phone Auth generates, sends by SMS and checks the code, we verify its ID token
    otp_provider: Literal["local", "firebase"] = "local"
    # Firebase web app config (public values, sent to the browser); FIREBASE_PROJECT_ID is required for "firebase"
    firebase_project_id: str = ""
    firebase_web_api_key: str = ""
    # Empty = "<project id>.firebaseapp.com"
    firebase_auth_domain: str = ""
    otp_ttl_seconds: int = Field(default=300, ge=30)
    otp_max_attempts: int = Field(default=5, ge=1)
    otp_max_requests: int = Field(default=5, ge=1, description="Codes per target per rate-limit window")
    otp_rate_window_minutes: int = Field(default=15, ge=1)
    # Return a local code in the API response (no SMS with OTP_PROVIDER=local). Default: everywhere except production;
    # a public demo with fake data can turn it on explicitly.
    otp_expose_code: bool | None = None
    # Demo accounts (src/db/seed.py; DEMO_PHONES='[...]', '[]' = none): no SMS is sent to them, their sign-in and
    # red book code is always DEMO_OTP_CODE, shown and filled in on screen (a simulation of the OTP step)
    demo_phones: list[str] = ["0901111222", "0902222333", "0912345678", "0918765432"]
    # Wrong holder name / red book code attempts one seller account may make per hour (stops guessing codes)
    ownership_claim_failures_per_hour: int = Field(default=5, ge=1)
    # Guardrail judge (src/agents/guardrail_judge.py): a small model double-checks risky messages and replies.
    # Provider empty = LLM_PROVIDER; model empty = that provider's small default (e.g. claude-haiku-5-5)
    guardrail_judge: bool = True
    guardrail_judge_provider: Literal["", "openai", "google", "openrouter", "groq", "anthropic"] = ""
    guardrail_judge_model: str = ""
    guardrail_judge_timeout_seconds: float = Field(default=8, gt=0)
    # Developer-only API (/api/v1/admin: AI kill switch, client IP check), header X-Admin-Token. Empty = disabled.
    # A long random secret known to the dev team only (python -c "import secrets; print(secrets.token_urlsafe(32))")
    admin_api_token: str = ""
    # Live notifications (GET /notifications/stream): how often the stream checks for new ones, and how long one
    # stream lasts before the client reconnects (below the platform request timeout, Cloud Run: 300 s)
    notification_stream_poll_seconds: float = Field(default=2, gt=0)
    notification_stream_max_seconds: float = Field(default=240, gt=0)
    # Support phone shown when the dev team has the AI assistant turned off (kill switch)
    support_hotline: str = "1900xxxx"
    # Chat messages to the AI assistant (each is a model call): per signed-in buyer, and per IP for guests
    chat_messages_per_minute: int = Field(default=10, ge=1)
    chat_messages_per_hour: int = Field(default=120, ge=1)
    guest_chat_messages_per_minute: int = Field(default=6, ge=1)
    guest_chat_messages_per_hour: int = Field(default=40, ge=1)
    # All guests together per day (stops a script with many IPs from running up the model bill)
    guest_chat_messages_per_day_total: int = Field(default=3000, ge=1)
    # Guest IP for rate limits: a header the platform sets itself (e.g. "cf-connecting-ip"), else the
    # TRUSTED_PROXY_HOPS-th X-Forwarded-For entry from the right (the address our proxy appended; check it with
    # `python scripts/ai_switch.py client-ip` after a deploy)
    client_ip_header: str = ""
    trusted_proxy_hops: int = Field(default=1, ge=0)
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

    # LangSmith (LLM observability) for chat turns, alongside or instead of Langfuse; off when the key is empty
    # and always off in tests. The old LANGCHAIN_* names are accepted too.
    langsmith_api_key: str = Field(default="", validation_alias=AliasChoices("langsmith_api_key", "langchain_api_key"))
    langsmith_project: str = Field(
        default="bookingbot", validation_alias=AliasChoices("langsmith_project", "langchain_project")
    )
    # EU region: https://eu.api.smith.langchain.com
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias=AliasChoices("langsmith_endpoint", "langchain_endpoint"),
    )
    # Share of chat turns sent to LangSmith (1.0 = all)
    langsmith_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def langsmith_enabled(self) -> bool:
        return bool(self.langsmith_api_key) and self.app_env != "test"

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
        if self.otp_provider == "firebase" and not (self.firebase_project_id and self.firebase_web_api_key):
            raise ValueError("OTP_PROVIDER=firebase needs FIREBASE_PROJECT_ID and FIREBASE_WEB_API_KEY")
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
