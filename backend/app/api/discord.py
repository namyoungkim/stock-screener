"""Discord bot API endpoints."""

import logging

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.database import get_supabase_client
from app.models.discord import (
    DiscordAlertCreate,
    DiscordAlertItem,
    DiscordAlertsResponse,
    DiscordWatchlistCreate,
    DiscordWatchlistItem,
    DiscordWatchlistResponse,
)
from app.services import discord_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_discord_user_id(x_discord_user_id: str = Header(...)) -> str:
    """Extract and validate Discord user ID from header."""
    if not x_discord_user_id or len(x_discord_user_id) < 17:
        raise HTTPException(status_code=401, detail="Invalid Discord user ID")
    return x_discord_user_id


# ============================================
# Watchlist Endpoints
# ============================================


@router.get("/watchlist", response_model=DiscordWatchlistResponse)
async def get_watchlist(
    x_discord_user_id: str = Header(...),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get Discord user's watchlist."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    total, items = await discord_service.get_discord_watchlist(
        db, discord_user_id, limit=limit, offset=offset
    )

    return DiscordWatchlistResponse(items=items, total=total)


@router.post("/watchlist", response_model=DiscordWatchlistItem, status_code=201)
async def add_to_watchlist(
    ticker: str = Query(..., description="Stock ticker to add"),
    market: str | None = Query(None, description="Market (US, KOSPI, KOSDAQ)"),
    x_discord_user_id: str = Header(...),
):
    """Add stock to Discord user's watchlist by ticker."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    # Find company by ticker
    company = await discord_service.get_company_by_ticker(db, ticker, market)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Stock '{ticker}' not found" + (f" in {market}" if market else ""),
        )

    # Check if already in watchlist
    if await discord_service.is_in_discord_watchlist(
        db, discord_user_id, company["id"]
    ):
        raise HTTPException(
            status_code=409,
            detail=f"{ticker} is already in your watchlist",
        )

    # Add to watchlist
    item = DiscordWatchlistCreate(company_id=company["id"])
    result = await discord_service.add_to_discord_watchlist(db, discord_user_id, item)

    return result


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    market: str | None = Query(None, description="Market (US, KOSPI, KOSDAQ)"),
    x_discord_user_id: str = Header(...),
):
    """Remove stock from Discord user's watchlist by ticker."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    # Find company by ticker
    company = await discord_service.get_company_by_ticker(db, ticker, market)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Stock '{ticker}' not found",
        )

    # Remove from watchlist
    removed = await discord_service.remove_from_discord_watchlist(
        db, discord_user_id, company["id"]
    )

    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"{ticker} is not in your watchlist",
        )

    return {"message": f"{ticker} removed from watchlist"}


# ============================================
# Alert Endpoints
# ============================================


@router.get("/alerts", response_model=DiscordAlertsResponse)
async def get_alerts(
    x_discord_user_id: str = Header(...),
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get Discord user's alerts."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    total, items = await discord_service.get_discord_alerts(
        db, discord_user_id, active_only=active_only, limit=limit, offset=offset
    )

    return DiscordAlertsResponse(items=items, total=total)


@router.post("/alerts", response_model=DiscordAlertItem, status_code=201)
async def create_alert(
    alert: DiscordAlertCreate,
    ticker: str = Query(..., description="Stock ticker"),
    market: str | None = Query(None, description="Market (US, KOSPI, KOSDAQ)"),
    x_discord_user_id: str = Header(...),
):
    """Create a new Discord alert."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    # Find company by ticker
    company = await discord_service.get_company_by_ticker(db, ticker, market)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Stock '{ticker}' not found",
        )

    # Update alert with company_id
    alert_with_company = DiscordAlertCreate(
        company_id=company["id"],
        metric=alert.metric,
        operator=alert.operator,
        value=alert.value,
    )

    try:
        result = await discord_service.create_discord_alert(
            db, discord_user_id, alert_with_company
        )
        return result
    except Exception as e:
        if "unique_discord_alert_condition" in str(e):
            raise HTTPException(
                status_code=409,
                detail="This alert condition already exists",
            ) from None
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: str,
    x_discord_user_id: str = Header(...),
):
    """Delete a Discord alert."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    deleted = await discord_service.delete_discord_alert(db, discord_user_id, alert_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return {"message": "Alert deleted"}


@router.post("/alerts/{alert_id}/toggle", response_model=DiscordAlertItem)
async def toggle_alert(
    alert_id: str,
    x_discord_user_id: str = Header(...),
):
    """Toggle Discord alert active status."""
    discord_user_id = get_discord_user_id(x_discord_user_id)
    db = get_supabase_client()

    result = await discord_service.toggle_discord_alert(db, discord_user_id, alert_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return result
