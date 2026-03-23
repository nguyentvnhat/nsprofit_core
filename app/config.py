"""Application configuration (env-driven; SaaS-ready: add tenant settings here later)."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of `app/` (where `.env` lives).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """Runtime settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="NOSAPROFIT_",
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Env: NOSAPROFIT_DATABASE_URL (e.g. in `.env` at project root, loaded via load_dotenv above).
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/nosaprofit"
    rules_dir: Path | None = None
    log_level: str = "INFO"

    @property
    def resolved_rules_dir(self) -> Path:
        """Directory containing YAML rule packs."""
        if self.rules_dir is not None:
            return Path(self.rules_dir).resolve()
        # Default: app/rules next to this package
        return (Path(__file__).resolve().parent / "rules").resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
