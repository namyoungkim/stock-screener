"""Discord bot specific service functions."""

from app.models.discord import (
    DiscordAlertCreate,
    DiscordAlertItem,
    DiscordWatchlistCreate,
    DiscordWatchlistItem,
)
from supabase import Client

# ============================================
# Watchlist Functions
# ============================================


async def get_discord_watchlist(
    db: Client,
    discord_user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[DiscordWatchlistItem]]:
    """Get Discord user's watchlist with company details."""
    result = (
        db.table("discord_watchlist")
        .select(
            "id, discord_user_id, company_id, added_at, notes, target_price, "
            "companies!inner(ticker, name, market)",
            count="exact",
        )
        .eq("discord_user_id", discord_user_id)
        .order("added_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items = []
    for row in result.data:
        company = row.pop("companies", {})
        items.append(
            DiscordWatchlistItem(
                **row,
                ticker=company.get("ticker"),
                name=company.get("name"),
                market=company.get("market"),
            )
        )

    return result.count or len(items), items


async def add_to_discord_watchlist(
    db: Client,
    discord_user_id: str,
    item: DiscordWatchlistCreate,
) -> DiscordWatchlistItem:
    """Add stock to Discord user's watchlist."""
    result = (
        db.table("discord_watchlist")
        .insert(
            {
                "discord_user_id": discord_user_id,
                "company_id": item.company_id,
                "notes": item.notes,
                "target_price": item.target_price,
            }
        )
        .execute()
    )

    if not result.data:
        raise ValueError("Failed to add to watchlist")

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

    return DiscordWatchlistItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def remove_from_discord_watchlist(
    db: Client,
    discord_user_id: str,
    company_id: str,
) -> bool:
    """Remove stock from Discord user's watchlist."""
    result = (
        db.table("discord_watchlist")
        .delete()
        .eq("discord_user_id", discord_user_id)
        .eq("company_id", company_id)
        .execute()
    )
    return len(result.data) > 0


async def is_in_discord_watchlist(
    db: Client,
    discord_user_id: str,
    company_id: str,
) -> bool:
    """Check if stock is in Discord user's watchlist."""
    result = (
        db.table("discord_watchlist")
        .select("id")
        .eq("discord_user_id", discord_user_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


# ============================================
# Alert Functions
# ============================================


async def get_discord_alerts(
    db: Client,
    discord_user_id: str,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[DiscordAlertItem]]:
    """Get Discord user's alerts with company details."""
    query = (
        db.table("discord_alerts")
        .select(
            "id, discord_user_id, company_id, metric, operator, value, "
            "is_active, triggered_at, triggered_count, created_at, updated_at, "
            "companies!inner(ticker, name, market)",
            count="exact",
        )
        .eq("discord_user_id", discord_user_id)
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
            DiscordAlertItem(
                **row,
                ticker=company.get("ticker"),
                name=company.get("name"),
                market=company.get("market"),
            )
        )

    return result.count or len(items), items


async def create_discord_alert(
    db: Client,
    discord_user_id: str,
    alert: DiscordAlertCreate,
) -> DiscordAlertItem:
    """Create a new Discord alert."""
    result = (
        db.table("discord_alerts")
        .insert(
            {
                "discord_user_id": discord_user_id,
                "company_id": alert.company_id,
                "metric": alert.metric.value
                if hasattr(alert.metric, "value")
                else alert.metric,
                "operator": alert.operator.value
                if hasattr(alert.operator, "value")
                else alert.operator,
                "value": alert.value,
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
        .eq("id", alert.company_id)
        .limit(1)
        .execute()
    )
    company = company_result.data[0] if company_result.data else {}

    return DiscordAlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def delete_discord_alert(
    db: Client,
    discord_user_id: str,
    alert_id: str,
) -> bool:
    """Delete a Discord alert."""
    result = (
        db.table("discord_alerts")
        .delete()
        .eq("discord_user_id", discord_user_id)
        .eq("id", alert_id)
        .execute()
    )
    return len(result.data) > 0


async def toggle_discord_alert(
    db: Client,
    discord_user_id: str,
    alert_id: str,
) -> DiscordAlertItem | None:
    """Toggle Discord alert active status."""
    # First get current status
    current = (
        db.table("discord_alerts")
        .select("is_active")
        .eq("discord_user_id", discord_user_id)
        .eq("id", alert_id)
        .limit(1)
        .execute()
    )

    if not current.data:
        return None

    new_status = not current.data[0]["is_active"]

    result = (
        db.table("discord_alerts")
        .update({"is_active": new_status})
        .eq("discord_user_id", discord_user_id)
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

    return DiscordAlertItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


# ============================================
# Helper Functions
# ============================================


async def get_company_by_ticker(
    db: Client,
    ticker: str,
    market: str | None = None,
) -> dict | None:
    """Get company by ticker (and optionally market)."""
    query = (
        db.table("companies")
        .select("id, ticker, name, market")
        .eq("ticker", ticker.upper())
    )

    if market:
        query = query.eq("market", market.upper())

    result = query.limit(1).execute()

    return result.data[0] if result.data else None
