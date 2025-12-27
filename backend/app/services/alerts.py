"""Alerts service."""

from app.models.alert import (
    AlertItem,
    AlertItemCreate,
    AlertItemUpdate,
)
from supabase import Client


async def get_user_alerts(
    db: Client,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
) -> tuple[int, list[AlertItem]]:
    """Get user's alerts with company details."""
    query = (
        db.table("alerts")
        .select(
            "id, user_id, company_id, metric, operator, value, "
            "is_active, triggered_at, triggered_count, created_at, updated_at, "
            "companies!inner(ticker, name, market)",
            count="exact",
        )
        .eq("user_id", user_id)
    )

    if active_only:
        query = query.eq("is_active", True)

    result = (
        query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    )

    items = []
    for row in result.data:
        company = row.pop("companies", {})
        items.append(
            AlertItem(
                **row,
                ticker=company.get("ticker"),
                name=company.get("name"),
                market=company.get("market"),
            )
        )

    return result.count or len(items), items


async def create_alert(
    db: Client,
    user_id: str,
    item: AlertItemCreate,
) -> AlertItem:
    """Create a new alert."""
    result = (
        db.table("alerts")
        .insert(
            {
                "user_id": user_id,
                "company_id": item.company_id,
                "metric": item.metric,
                "operator": item.operator.value,
                "value": item.value,
            }
        )
        .execute()
    )

    if not result.data:
        raise ValueError("Failed to create alert")

    row = result.data[0]

    # Fetch company info
    company_result = (
        db.table("companies")
        .select("ticker, name, market")
        .eq("id", item.company_id)
        .limit(1)
        .execute()
    )
    company = company_result.data[0] if company_result.data else {}

    return AlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def delete_alert(
    db: Client,
    user_id: str,
    alert_id: str,
) -> bool:
    """Delete an alert."""
    result = (
        db.table("alerts").delete().eq("user_id", user_id).eq("id", alert_id).execute()
    )
    return len(result.data) > 0


async def update_alert(
    db: Client,
    user_id: str,
    alert_id: str,
    update: AlertItemUpdate,
) -> AlertItem | None:
    """Update an alert."""
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        return None

    # Convert operator enum to string if present
    if "operator" in update_data and update_data["operator"] is not None:
        update_data["operator"] = update_data["operator"].value

    result = (
        db.table("alerts")
        .update(update_data)
        .eq("user_id", user_id)
        .eq("id", alert_id)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]

    # Fetch company info
    company_result = (
        db.table("companies")
        .select("ticker, name, market")
        .eq("id", row["company_id"])
        .limit(1)
        .execute()
    )
    company = company_result.data[0] if company_result.data else {}

    return AlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def get_alert_by_id(
    db: Client,
    user_id: str,
    alert_id: str,
) -> AlertItem | None:
    """Get a specific alert by ID."""
    result = (
        db.table("alerts")
        .select(
            "id, user_id, company_id, metric, operator, value, "
            "is_active, triggered_at, triggered_count, created_at, updated_at, "
            "companies!inner(ticker, name, market)",
        )
        .eq("user_id", user_id)
        .eq("id", alert_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    company = row.pop("companies", {})

    return AlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def get_alerts_for_company(
    db: Client,
    user_id: str,
    company_id: str,
) -> list[AlertItem]:
    """Get all alerts for a specific company."""
    result = (
        db.table("alerts")
        .select(
            "id, user_id, company_id, metric, operator, value, "
            "is_active, triggered_at, triggered_count, created_at, updated_at, "
            "companies!inner(ticker, name, market)",
        )
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )

    items = []
    for row in result.data:
        company = row.pop("companies", {})
        items.append(
            AlertItem(
                **row,
                ticker=company.get("ticker"),
                name=company.get("name"),
                market=company.get("market"),
            )
        )

    return items


async def toggle_alert(
    db: Client,
    user_id: str,
    alert_id: str,
) -> AlertItem | None:
    """Toggle alert active status."""
    # First get current status
    current = await get_alert_by_id(db, user_id, alert_id)
    if not current:
        return None

    # Toggle status
    result = (
        db.table("alerts")
        .update({"is_active": not current.is_active})
        .eq("user_id", user_id)
        .eq("id", alert_id)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]

    # Fetch company info
    company_result = (
        db.table("companies")
        .select("ticker, name, market")
        .eq("id", row["company_id"])
        .limit(1)
        .execute()
    )
    company = company_result.data[0] if company_result.data else {}

    return AlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )
