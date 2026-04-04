"""Application configuration — dotenv + required database URL."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """Runtime settings from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="NOSAPROFIT_",
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="MySQL URL, e.g. mysql+pymysql://user:pass@127.0.0.1:3306/nosaprofit",
    )
    rules_dir: Path | None = None
    log_level: str = "INFO"
    # When true, future Shopify Admin API create path may run (client not implemented yet).
    shopify_discount_integration_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def database_url_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError(
                "NOSAPROFIT_DATABASE_URL is required. "
                "Set it in the environment or in a .env file at the project root."
            )
        return s

    @property
    def resolved_rules_dir(self) -> Path:
        if self.rules_dir is not None:
            return Path(self.rules_dir).resolve()
        return (Path(__file__).resolve().parent / "rules").resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
