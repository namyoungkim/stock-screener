"""Alerts API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.alert import (
    AlertCreateResponse,
    AlertDeleteResponse,
    AlertItem,
    AlertItemCreate,
    AlertItemUpdate,
    AlertResponse,
)
from app.services import alerts as alerts_service
from supabase import Client

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertResponse)
async def get_alerts(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get current user's alerts."""
    total, items = await alerts_service.get_user_alerts(
        db=db,
        user_id=user["user_id"],
        limit=limit,
        offset=offset,
        active_only=active_only,
    )
    return AlertResponse(total=total, items=items)


@router.post("", response_model=AlertCreateResponse)
async def create_alert(
    item: AlertItemCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Create a new alert."""
    created = await alerts_service.create_alert(
        db=db,
        user_id=user["user_id"],
        item=item,
    )
    return AlertCreateResponse(success=True, item=created)


@router.get("/{alert_id}", response_model=AlertItem)
async def get_alert(
    alert_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get a specific alert by ID."""
    alert = await alerts_service.get_alert_by_id(
        db=db,
        user_id=user["user_id"],
        alert_id=alert_id,
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertCreateResponse)
async def update_alert(
    alert_id: str,
    update: AlertItemUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Update an alert."""
    updated = await alerts_service.update_alert(
        db=db,
        user_id=user["user_id"],
        alert_id=alert_id,
        update=update,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertCreateResponse(success=True, item=updated)


@router.delete("/{alert_id}", response_model=AlertDeleteResponse)
async def delete_alert(
    alert_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Delete an alert."""
    success = await alerts_service.delete_alert(
        db=db,
        user_id=user["user_id"],
        alert_id=alert_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertDeleteResponse(success=True, message="Alert deleted")


@router.post("/{alert_id}/toggle", response_model=AlertCreateResponse)
async def toggle_alert(
    alert_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Toggle alert active status."""
    toggled = await alerts_service.toggle_alert(
        db=db,
        user_id=user["user_id"],
        alert_id=alert_id,
    )
    if not toggled:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertCreateResponse(success=True, item=toggled)


@router.get("/company/{company_id}", response_model=list[AlertItem])
async def get_alerts_for_company(
    company_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get all alerts for a specific company."""
    alerts = await alerts_service.get_alerts_for_company(
        db=db,
        user_id=user["user_id"],
        company_id=company_id,
    )
    return alerts
