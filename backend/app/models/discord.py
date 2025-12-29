"""Discord bot specific models."""

from pydantic import BaseModel

from app.models.common import (
    CompanyId,
    MetricType,
    MetricValue,
    NotesField,
    TargetPrice,
)
from app.models.stock import OperatorType

# Discord User ID validation (snowflake: 17-20 digit string)
DiscordUserId = str


class DiscordWatchlistBase(BaseModel):
    """Base model for Discord watchlist items."""

    company_id: CompanyId
    notes: NotesField | None = None
    target_price: TargetPrice | None = None


class DiscordWatchlistCreate(DiscordWatchlistBase):
    """Create Discord watchlist item request."""

    pass


class DiscordWatchlistItem(DiscordWatchlistBase):
    """Discord watchlist item response."""

    id: str
    discord_user_id: str
    added_at: str

    # Joined company info
    ticker: str | None = None
    name: str | None = None
    market: str | None = None

    class Config:
        from_attributes = True


class DiscordAlertBase(BaseModel):
    """Base model for Discord alert items."""

    company_id: CompanyId
    metric: MetricType
    operator: OperatorType
    value: MetricValue


class DiscordAlertCreate(DiscordAlertBase):
    """Create Discord alert request."""

    pass


class DiscordAlertItem(DiscordAlertBase):
    """Discord alert item response."""

    id: str
    discord_user_id: str
    is_active: bool = True
    triggered_at: str | None = None
    triggered_count: int = 0
    created_at: str
    updated_at: str

    # Joined company info
    ticker: str | None = None
    name: str | None = None
    market: str | None = None

    class Config:
        from_attributes = True


class DiscordWatchlistResponse(BaseModel):
    """Discord watchlist response."""

    items: list[DiscordWatchlistItem]
    total: int


class DiscordAlertsResponse(BaseModel):
    """Discord alerts response."""

    items: list[DiscordAlertItem]
    total: int
