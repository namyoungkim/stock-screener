"""Database connection using Supabase."""

from app.core.config import settings
from supabase import Client, create_client

_client: Client | None = None


def get_supabase_client() -> Client:
    """Get Supabase client singleton."""
    global _client

    if _client is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(settings.supabase_url, settings.supabase_key)

    return _client


async def get_db() -> Client:
    """Dependency for FastAPI routes."""
    return get_supabase_client()
