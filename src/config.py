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

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database (PostgreSQL 15+ required: btree_gist exclusion constraints, pg_trgm)
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bookingbot"
    # Used by pytest; defaults to database_url with a "_test" suffix on the DB name
    test_database_url: str = ""

    # Auth
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24, ge=5)

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
