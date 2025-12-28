"""Watchlist API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.watchlist import (
    WatchlistAddResponse,
    WatchlistItemCreate,
    WatchlistItemUpdate,
    WatchlistRemoveResponse,
    WatchlistResponse,
)
from app.services import watchlist as watchlist_service
from supabase import Client

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get current user's watchlist."""
    total, items = await watchlist_service.get_user_watchlist(
        db=db,
        user_id=user["user_id"],
        limit=limit,
        offset=offset,
    )
    return WatchlistResponse(total=total, items=items)


@router.post("", response_model=WatchlistAddResponse)
async def add_to_watchlist(
    item: WatchlistItemCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Add stock to watchlist."""
    # Check if already in watchlist
    if await watchlist_service.is_in_watchlist(db, user["user_id"], item.company_id):
        raise HTTPException(
            status_code=400,
            detail="Stock already in watchlist",
        )

    created = await watchlist_service.add_to_watchlist(
        db=db,
        user_id=user["user_id"],
        item=item,
    )
    return WatchlistAddResponse(success=True, item=created)


@router.delete("/{company_id}", response_model=WatchlistRemoveResponse)
async def remove_from_watchlist(
    company_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Remove stock from watchlist."""
    success = await watchlist_service.remove_from_watchlist(
        db=db,
        user_id=user["user_id"],
        company_id=company_id,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Stock not found in watchlist",
        )
    return WatchlistRemoveResponse(success=True, message="Removed from watchlist")


@router.patch("/{company_id}", response_model=WatchlistAddResponse)
async def update_watchlist_item(
    company_id: str,
    update: WatchlistItemUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update notes/target_price for a watchlist item."""
    updated = await watchlist_service.update_watchlist_item(
        db=db,
        user_id=user["user_id"],
        company_id=company_id,
        update=update,
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Stock not found in watchlist",
        )
    return WatchlistAddResponse(success=True, item=updated)


@router.get("/check/{company_id}")
async def check_in_watchlist(
    company_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Check if stock is in user's watchlist."""
    in_watchlist = await watchlist_service.is_in_watchlist(
        db=db,
        user_id=user["user_id"],
        company_id=company_id,
    )
    return {"in_watchlist": in_watchlist}
