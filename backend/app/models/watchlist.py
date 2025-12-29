"""Watchlist-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel

from app.models.common import CompanyId, NotesField, TargetPrice


class WatchlistItemBase(BaseModel):
    """Base watchlist item model."""

    company_id: CompanyId
    notes: NotesField | None = None
    target_price: TargetPrice | None = None


class WatchlistItemCreate(WatchlistItemBase):
    """Create watchlist item request."""

    pass


class WatchlistItemUpdate(BaseModel):
    """Update watchlist item request."""

    notes: NotesField | None = None
    target_price: TargetPrice | None = None


class WatchlistItem(WatchlistItemBase):
    """Watchlist item response."""

    id: str
    user_id: str
    added_at: datetime

    # Joined company info
    ticker: str | None = None
    name: str | None = None
    market: str | None = None
    latest_price: float | None = None


class WatchlistResponse(BaseModel):
    """Watchlist response with items."""

    total: int
    items: list[WatchlistItem]


class WatchlistAddResponse(BaseModel):
    """Response after adding to watchlist."""

    success: bool
    item: WatchlistItem


class WatchlistRemoveResponse(BaseModel):
    """Response after removing from watchlist."""

    success: bool
    message: str
