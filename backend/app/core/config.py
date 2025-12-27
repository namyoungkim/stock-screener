"""Application configuration."""

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

# Default allowed origins
DEFAULT_CORS_ORIGINS = [
    "https://stock-screener-inky.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_name: str = "Stock Screener API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")

    # CORS - comma-separated origins or use default
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
