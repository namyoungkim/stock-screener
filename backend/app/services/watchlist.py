"""Watchlist service."""

from supabase import Client

from app.models.watchlist import (
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistItemUpdate,
)


async def get_user_watchlist(
    db: Client,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[WatchlistItem]]:
    """Get user's watchlist with company details."""
    # Query watchlist with company join
    result = (
        db.table("watchlist")
        .select(
            "id, user_id, company_id, added_at, notes, target_price, "
            "companies!inner(ticker, name, market)",
            count="exact",
        )
        .eq("user_id", user_id)
        .order("added_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items = []
    for row in result.data:
        company = row.pop("companies", {})
        items.append(
            WatchlistItem(
                **row,
                ticker=company.get("ticker"),
                name=company.get("name"),
                market=company.get("market"),
            )
        )

    return result.count or len(items), items


async def add_to_watchlist(
    db: Client,
    user_id: str,
    item: WatchlistItemCreate,
) -> WatchlistItem:
    """Add stock to user's watchlist."""
    result = (
        db.table("watchlist")
        .insert(
            {
                "user_id": user_id,
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

    return WatchlistItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def remove_from_watchlist(
    db: Client,
    user_id: str,
    company_id: str,
) -> bool:
    """Remove stock from user's watchlist."""
    result = (
        db.table("watchlist")
        .delete()
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .execute()
    )
    return len(result.data) > 0


async def update_watchlist_item(
    db: Client,
    user_id: str,
    company_id: str,
    update: WatchlistItemUpdate,
) -> WatchlistItem | None:
    """Update notes/target_price for a watchlist item."""
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        return None

    result = (
        db.table("watchlist")
        .update(update_data)
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]

    # Fetch company info
    company_result = (
        db.table("companies")
        .select("ticker, name, market")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    company = company_result.data[0] if company_result.data else {}

    return WatchlistItem(
        **row,
        ticker=company.get("ticker"),
        name=company.get("name"),
        market=company.get("market"),
    )


async def is_in_watchlist(
    db: Client,
    user_id: str,
    company_id: str,
) -> bool:
    """Check if stock is in user's watchlist."""
    result = (
        db.table("watchlist")
        .select("id")
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0
