"""Environment-driven configuration (Constitution: configuration over secrets-in-code)."""

from __future__ import annotations

import tempfile
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GT_", env_file=".env", extra="ignore")

    # NoDecode: take the raw env string (comma-separated) and let the validator split it,
    # instead of pydantic-settings trying to JSON-decode it as a list.
    cors_origins: Annotated[list[str], NoDecode] = []
    max_concurrency: int = 4
    rate_jobs_per_min: int = 10
    rate_resolve_per_min: int = 30
    retention_minutes: int = 30
    resolve_timeout_s: int = 30
    job_timeout_s: int = 1800
    tmp_dir: str = ""
    port: int = 8080
    proxy_url: str = ""
    cookies_file: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def work_dir(self) -> str:
        return self.tmp_dir or tempfile.gettempdir()

    @property
    def retention_seconds(self) -> int:
        return self.retention_minutes * 60


def load_settings() -> Settings:
    return Settings()
