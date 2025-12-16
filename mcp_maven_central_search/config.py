"""Application configuration using pydantic-settings.

This module centralizes all runtime configuration with explicit types and sane defaults
as defined in PLANNING.md. All fields are overridable via environment variables with the
same names (case-insensitive).

Notes:
- CACHE_MAX_ENTRIES default is bounded (2048) to avoid unbounded memory growth while still
  accommodating typical workloads.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings.

    Env var precedence follows pydantic-settings rules. All fields can be overridden via
    environment variables with the same names, e.g., `HTTP_TIMEOUT_SECONDS=20`.
    """

    # Maven Central endpoints
    MAVEN_CENTRAL_BASE_URL: str = "https://search.maven.org/solrsearch/select"
    MAVEN_CENTRAL_REMOTE_CONTENT_BASE_URL: str = "https://search.maven.org/remotecontent"

    # HTTP behavior
    HTTP_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
    HTTP_MAX_RETRIES: int = Field(default=2, ge=0)
    HTTP_CONCURRENCY: int = Field(default=10, ge=1)

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS_SEARCH: int = Field(default=21600, ge=0)  # 6 hours
    CACHE_TTL_SECONDS_POM: int = Field(default=86400, ge=0)  # 24 hours
    # Bounded to prevent unbounded memory; see module docstring.
    CACHE_MAX_ENTRIES: int = Field(default=2048, ge=1)

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON: bool = False

    # Forward-looking / reserved
    TRANSPORT: Literal["stdio", "http"] = "stdio"
    HTTP_HOST: str = "127.0.0.1"
    HTTP_PORT: int = Field(default=8000, ge=1, le=65535)
    AUTH_MODE: Literal["none", "api_key", "oauth"] = "none"

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)


__all__ = ["Settings"]
