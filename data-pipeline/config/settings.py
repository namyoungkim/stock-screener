"""Application settings using Pydantic. No side effects at import time."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import (
    DATA_DIR,
    DEFAULT_BASE_DELAY,
    DEFAULT_BATCH_SIZE,
    DEFAULT_HISTORY_BATCH_SIZE,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_RETRIES,
)


class Settings(BaseSettings):
    """Application settings with validation.

    Settings are loaded from environment variables and .env file.
    No side effects at class definition time - .env is loaded only when
    Settings() is instantiated.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    # === Database ===
    supabase_url: str | None = None
    supabase_key: str | None = None

    # === KIS API (Korean Investment & Securities) ===
    kis_app_key: str | None = None
    kis_app_secret: str | None = None
    kis_paper_trading: bool = Field(default=False, description="Use paper trading API")

    # === Rate Limits ===
    batch_size: Annotated[int, Field(gt=0)] = DEFAULT_BATCH_SIZE
    batch_size_history: Annotated[int, Field(gt=0)] = DEFAULT_HISTORY_BATCH_SIZE
    base_delay: Annotated[float, Field(ge=0)] = DEFAULT_BASE_DELAY
    request_timeout: Annotated[float, Field(gt=0)] = DEFAULT_REQUEST_TIMEOUT
    max_retries: Annotated[int, Field(ge=0)] = MAX_RETRIES

    # === Paths ===
    data_dir: Path = DATA_DIR

    @property
    def companies_dir(self) -> Path:
        """Directory for company master data."""
        return self.data_dir / "companies"

    @property
    def has_supabase(self) -> bool:
        """Check if Supabase credentials are configured."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def has_kis(self) -> bool:
        """Check if KIS API credentials are configured."""
        return bool(self.kis_app_key and self.kis_app_secret)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    This is the recommended way to access settings to avoid
    repeated .env file parsing.
    """
    return Settings()
