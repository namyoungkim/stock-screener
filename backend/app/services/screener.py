"""Screening service."""

from typing import Any

from app.models.stock import (
    CompanyWithMetrics,
    MarketType,
    MetricFilter,
    OperatorType,
    PresetStrategy,
)
from supabase import Client

# Preset strategies
PRESETS: dict[str, PresetStrategy] = {
    "graham": PresetStrategy(
        id="graham",
        name="Graham Classic",
        description="Benjamin Graham's classic value criteria: P/E < 15, P/B < 1.5, D/E < 0.5",
        filters=[
            MetricFilter(metric="pe_ratio", operator=OperatorType.LT, value=15),
            MetricFilter(metric="pb_ratio", operator=OperatorType.LT, value=1.5),
            MetricFilter(metric="debt_equity", operator=OperatorType.LT, value=0.5),
        ],
    ),
    "buffett": PresetStrategy(
        id="buffett",
        name="Buffett Quality",
        description="Warren Buffett style: ROE > 15%, positive margins",
        filters=[
            MetricFilter(metric="roe", operator=OperatorType.GT, value=0.15),
            MetricFilter(metric="net_margin", operator=OperatorType.GT, value=0.1),
        ],
    ),
    "dividend": PresetStrategy(
        id="dividend",
        name="Dividend Value",
        description="High dividend yield stocks: Dividend Yield > 3%",
        filters=[
            MetricFilter(metric="dividend_yield", operator=OperatorType.GT, value=0.03),
        ],
    ),
    "deep_value": PresetStrategy(
        id="deep_value",
        name="Deep Value",
        description="Deep value stocks: P/B < 1, P/E < 10",
        filters=[
            MetricFilter(metric="pb_ratio", operator=OperatorType.LT, value=1),
            MetricFilter(metric="pe_ratio", operator=OperatorType.LT, value=10),
        ],
    ),
}


def get_presets() -> list[PresetStrategy]:
    """Get all preset strategies."""
    return list(PRESETS.values())


def get_preset(preset_id: str) -> PresetStrategy | None:
    """Get preset by ID."""
    return PRESETS.get(preset_id)


def _build_filter_query(
    query: Any,
    filters: list[MetricFilter],
) -> Any:
    """Apply filters to query."""
    for f in filters:
        column = f.metric
        value = f.value

        match f.operator:
            case OperatorType.LT:
                query = query.lt(column, value)
            case OperatorType.LTE:
                query = query.lte(column, value)
            case OperatorType.EQ:
                query = query.eq(column, value)
            case OperatorType.GTE:
                query = query.gte(column, value)
            case OperatorType.GT:
                query = query.gt(column, value)

    return query


async def screen_stocks(
    db: Client,
    filters: list[MetricFilter],
    market: MarketType | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[CompanyWithMetrics]]:
    """
    Screen stocks based on filters.

    Returns:
        Tuple of (total count, list of stocks)
    """
    # Use the view for screening
    query = db.table("company_latest_metrics").select("*", count="exact")

    # Apply market filter
    if market:
        query = query.eq("market", market.value)

    # Apply metric filters
    query = _build_filter_query(query, filters)

    # Apply pagination
    query = query.range(offset, offset + limit - 1)

    # Execute
    result = query.execute()

    stocks = [CompanyWithMetrics(**row) for row in result.data]
    total = result.count or len(stocks)

    return total, stocks


async def get_stocks(
    db: Client,
    market: MarketType | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[CompanyWithMetrics]]:
    """Get stocks with optional filtering."""
    query = db.table("company_latest_metrics").select("*", count="exact")

    if market:
        query = query.eq("market", market.value)

    if search:
        # Search by ticker or name
        query = query.or_(f"ticker.ilike.%{search}%,name.ilike.%{search}%")

    query = query.range(offset, offset + limit - 1)
    result = query.execute()

    stocks = [CompanyWithMetrics(**row) for row in result.data]
    total = result.count or len(stocks)

    return total, stocks


async def get_stock_by_ticker(
    db: Client,
    ticker: str,
    market: MarketType | None = None,
) -> CompanyWithMetrics | None:
    """Get stock by ticker."""
    query = db.table("company_latest_metrics").select("*").eq("ticker", ticker)

    if market:
        query = query.eq("market", market.value)

    result = query.execute()

    if not result.data:
        return None

    return CompanyWithMetrics(**result.data[0])
