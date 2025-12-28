"""User presets API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user_preset import (
    UserPreset,
    UserPresetCreate,
    UserPresetCreateResponse,
    UserPresetDeleteResponse,
    UserPresetResponse,
    UserPresetUpdate,
)
from app.services import user_presets as user_presets_service
from supabase import Client

router = APIRouter()


@router.get("", response_model=UserPresetResponse)
async def get_user_presets(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get current user's presets."""
    total, items = await user_presets_service.get_user_presets(
        db=db,
        user_id=user["user_id"],
        limit=limit,
        offset=offset,
    )
    return UserPresetResponse(total=total, items=items)


@router.post("", response_model=UserPresetCreateResponse)
async def create_user_preset(
    item: UserPresetCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Create a new user preset."""
    try:
        created = await user_presets_service.create_user_preset(
            db=db,
            user_id=user["user_id"],
            item=item,
        )
        return UserPresetCreateResponse(success=True, item=created)
    except Exception as e:
        # Handle unique constraint violation
        if "unique_user_preset_name" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="A preset with this name already exists",
            ) from e
        raise


@router.get("/{preset_id}", response_model=UserPreset)
async def get_user_preset(
    preset_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get a specific preset by ID."""
    preset = await user_presets_service.get_user_preset(
        db=db,
        user_id=user["user_id"],
        preset_id=preset_id,
    )
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@router.patch("/{preset_id}", response_model=UserPresetCreateResponse)
async def update_user_preset(
    preset_id: str,
    update: UserPresetUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update a user preset."""
    try:
        updated = await user_presets_service.update_user_preset(
            db=db,
            user_id=user["user_id"],
            preset_id=preset_id,
            update=update,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Preset not found")
        return UserPresetCreateResponse(success=True, item=updated)
    except Exception as e:
        if "unique_user_preset_name" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="A preset with this name already exists",
            ) from e
        raise


@router.delete("/{preset_id}", response_model=UserPresetDeleteResponse)
async def delete_user_preset(
    preset_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Delete a user preset."""
    success = await user_presets_service.delete_user_preset(
        db=db,
        user_id=user["user_id"],
        preset_id=preset_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Preset not found")
    return UserPresetDeleteResponse(success=True, message="Preset deleted")
