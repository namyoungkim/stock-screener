"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import alerts, screen, stocks, watchlist
from app.core.config import settings
from app.core.rate_limit import limiter

app = FastAPI(
    title=settings.app_name,
    description="Value investing screening tool for US and Korean stocks",
    version=settings.app_version,
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
