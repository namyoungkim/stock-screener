"""Application configuration."""

import logging
import os
import sys

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings

load_dotenv()

logger = logging.getLogger(__name__)

# Default allowed origins
DEFAULT_CORS_ORIGINS = [
    "https://stock-screener-inky.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for safe logging."""
    if not value:
        return "(not set)"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_name: str = "Stock Screener API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Supabase (required for API operations)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_jwt_secret: str = ""

    # CORS - comma-separated origins or use default
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS

    class Config:
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def validate_required_settings(self) -> "Settings":
        """Validate required environment variables on startup."""
        missing = []

        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_key:
            missing.append("SUPABASE_KEY")

        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            logger.error("Please set these variables in your .env file or environment.")
            # Exit in production, warn in development
            if os.getenv("RENDER") or os.getenv("VERCEL"):
                sys.exit(1)
            else:
                logger.warning(
                    "Continuing without database connection (development mode)"
                )

        return self

    def log_config_summary(self) -> None:
        """Log configuration summary with masked secrets."""
        logger.info("=== Configuration Summary ===")
        logger.info(f"App: {self.app_name} v{self.app_version}")
        logger.info(f"Debug: {self.debug}")
        logger.info(f"SUPABASE_URL: {mask_secret(self.supabase_url, 20)}")
        logger.info(f"SUPABASE_KEY: {mask_secret(self.supabase_key)}")
        logger.info(f"CORS Origins: {len(self.cors_origins)} domains")
        logger.info("=============================")


settings = Settings()
