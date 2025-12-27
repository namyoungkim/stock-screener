"""Alert-related Pydantic models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OperatorType(str, Enum):
    """Alert operator types."""

    LT = "<"
    LTE = "<="
    EQ = "="
    GTE = ">="
    GT = ">"


class AlertItemBase(BaseModel):
    """Base alert item model."""

    company_id: str
    metric: str = Field(
        ...,
        description="Metric to monitor (e.g., 'pe_ratio', 'pb_ratio', 'price', 'rsi')",
    )
    operator: OperatorType
    value: float


class AlertItemCreate(AlertItemBase):
    """Create alert item request."""

    pass


class AlertItemUpdate(BaseModel):
    """Update alert item request."""

    metric: str | None = None
    operator: OperatorType | None = None
    value: float | None = None
    is_active: bool | None = None


class AlertItem(AlertItemBase):
    """Alert item response."""

    id: str
    user_id: str
    is_active: bool
    triggered_at: datetime | None = None
    triggered_count: int
    created_at: datetime
    updated_at: datetime

    # Joined company info
    ticker: str | None = None
    name: str | None = None
    market: str | None = None
    latest_price: float | None = None


class AlertResponse(BaseModel):
    """Alert list response."""

    total: int
    items: list[AlertItem]


class AlertCreateResponse(BaseModel):
    """Response after creating alert."""

    success: bool
    item: AlertItem


class AlertDeleteResponse(BaseModel):
    """Response after deleting alert."""

    success: bool
    message: str
