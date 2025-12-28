"""User presets service."""

import json

from app.models.stock import MetricFilter
from app.models.user_preset import (
    UserPreset,
    UserPresetCreate,
    UserPresetUpdate,
)
from supabase import Client


def _parse_filters(filters_json: list[dict]) -> list[MetricFilter]:
    """Parse JSON filters to MetricFilter list."""
    return [MetricFilter(**f) for f in filters_json]


def _serialize_filters(filters: list[MetricFilter]) -> list[dict]:
    """Serialize MetricFilter list to JSON-compatible format."""
    return [{"metric": f.metric, "operator": f.operator, "value": f.value} for f in filters]


async def get_user_presets(
    db: Client,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[UserPreset]]:
    """Get user's presets."""
    result = (
        db.table("user_presets")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items = []
    for row in result.data:
        row["filters"] = _parse_filters(row["filters"])
        items.append(UserPreset(**row))

    return result.count or len(items), items


async def get_user_preset(
    db: Client,
    user_id: str,
    preset_id: str,
) -> UserPreset | None:
    """Get a specific preset by ID."""
    result = (
        db.table("user_presets")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", preset_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    row["filters"] = _parse_filters(row["filters"])
    return UserPreset(**row)


async def create_user_preset(
    db: Client,
    user_id: str,
    item: UserPresetCreate,
) -> UserPreset:
    """Create a new user preset."""
    result = (
        db.table("user_presets")
        .insert(
            {
                "user_id": user_id,
                "name": item.name,
                "description": item.description,
                "filters": _serialize_filters(item.filters),
            }
        )
        .execute()
    )

    if not result.data:
        raise ValueError("Failed to create preset")

    row = result.data[0]
    row["filters"] = _parse_filters(row["filters"])
    return UserPreset(**row)


async def update_user_preset(
    db: Client,
    user_id: str,
    preset_id: str,
    update: UserPresetUpdate,
) -> UserPreset | None:
    """Update a user preset."""
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        return None

    # Serialize filters if present
    if "filters" in update_data and update_data["filters"] is not None:
        update_data["filters"] = _serialize_filters(update_data["filters"])

    result = (
        db.table("user_presets")
        .update(update_data)
        .eq("user_id", user_id)
        .eq("id", preset_id)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    row["filters"] = _parse_filters(row["filters"])
    return UserPreset(**row)


async def delete_user_preset(
    db: Client,
    user_id: str,
    preset_id: str,
) -> bool:
    """Delete a user preset."""
    result = (
        db.table("user_presets")
        .delete()
        .eq("user_id", user_id)
        .eq("id", preset_id)
        .execute()
    )
    return len(result.data) > 0
