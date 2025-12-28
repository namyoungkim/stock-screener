"""User preset Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.stock import MetricFilter


class UserPresetBase(BaseModel):
    """Base user preset model."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class UserPresetCreate(UserPresetBase):
    """Create user preset request."""

    filters: list[MetricFilter] = Field(..., min_length=1)


class UserPresetUpdate(BaseModel):
    """Update user preset request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    filters: list[MetricFilter] | None = None


class UserPreset(UserPresetBase):
    """User preset response."""

    id: str
    user_id: str
    filters: list[MetricFilter]
    created_at: datetime
    updated_at: datetime


class UserPresetResponse(BaseModel):
    """User preset list response."""

    total: int
    items: list[UserPreset]


class UserPresetCreateResponse(BaseModel):
    """Response after creating user preset."""

    success: bool
    item: UserPreset


class UserPresetDeleteResponse(BaseModel):
    """Response after deleting user preset."""

    success: bool
    message: str
