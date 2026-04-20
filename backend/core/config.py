"""Application configuration management.

This module centralizes runtime settings for the backend API using
`pydantic-settings`, providing a single, typed source of truth for
environment-driven configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables.

    The class is intentionally strict and explicit so that configuration
    failures happen as early as possible during application startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    app_name: str = Field(
        default="Sistema Institucional de Gestao de Compras",
        description="Human-readable application name.",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Semantic version of the API.",
    )
    environment: Literal["local", "development", "staging", "production"] = Field(
        default="development",
        description="Current runtime environment.",
    )
    debug: bool = Field(
        default=False,
        description="Enables debug behavior. Must remain disabled in production.",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="Prefix for versioned REST endpoints.",
    )

    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Async SQLAlchemy connection string for PostgreSQL/Supabase.",
        examples=["postgresql+asyncpg://user:password@host:5432/database"],
    )
    database_echo: bool = Field(
        default=False,
        alias="DATABASE_ECHO",
        description="Enables SQLAlchemy SQL logging.",
    )
    database_pool_size: int = Field(
        default=10,
        alias="DATABASE_POOL_SIZE",
        ge=1,
        description="Primary size of the async database connection pool.",
    )
    database_max_overflow: int = Field(
        default=20,
        alias="DATABASE_MAX_OVERFLOW",
        ge=0,
        description="Maximum overflow connections above the base pool size.",
    )
    database_pool_timeout: int = Field(
        default=30,
        alias="DATABASE_POOL_TIMEOUT",
        ge=1,
        description="Seconds to wait for a connection from the pool.",
    )
    database_pool_recycle: int = Field(
        default=1800,
        alias="DATABASE_POOL_RECYCLE",
        ge=0,
        description="Seconds before recycling pooled connections.",
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        alias="DATABASE_POOL_PRE_PING",
        description="Validates pooled connections before use.",
    )

    secret_key: SecretStr = Field(
        ...,
        alias="SECRET_KEY",
        description="Primary application secret used for signing and security tasks.",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        ge=1,
        description="Default expiration for access tokens in minutes.",
    )
    algorithm: str = Field(
        default="HS256",
        alias="ALGORITHM",
        description="JWT signing algorithm.",
    )

    supabase_url: str | None = Field(
        default=None,
        alias="SUPABASE_URL",
        description="Base URL of the Supabase project.",
    )
    supabase_key: SecretStr | None = Field(
        default=None,
        alias="SUPABASE_KEY",
        description="Supabase service or anon key depending on the integration strategy.",
    )

    cors_origins: list[str] = Field(
        default_factory=list,
        alias="CORS_ORIGINS",
        description="Allowed CORS origins. Can be set as JSON array or comma-separated values.",
    )

    @computed_field(return_type=bool)
    @property
    def is_production(self) -> bool:
        """Return whether the current environment is production."""

        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance.

    Caching avoids reparsing environment variables on every import or request,
    which is especially important in ASGI applications.
    """

    return Settings()


settings: Settings = get_settings()
