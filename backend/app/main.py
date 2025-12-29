"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import alerts, discord, screen, stocks, user_presets, watchlist
from app.core.config import settings
from app.core.database import get_supabase_client
from app.core.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Stock Screener API...")
    settings.log_config_summary()

    # Validate database connection
    try:
        client = get_supabase_client()
        # Simple health check query
        client.table("companies").select("id").limit(1).execute()
        logger.info("Database connection verified successfully")
    except ValueError as e:
        logger.error(f"Database configuration error: {e}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.warning("API will start but database operations may fail")

    yield

    # Shutdown
    logger.info("Shutting down Stock Screener API...")


app = FastAPI(
    title=settings.app_name,
    description="Value investing screening tool for US and Korean stocks",
    version=settings.app_version,
    lifespan=lifespan,
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(stocks.router, prefix="/api")
app.include_router(screen.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(
    user_presets.router, prefix="/api/user-presets", tags=["user-presets"]
)
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
