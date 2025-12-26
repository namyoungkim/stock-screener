"""Stock API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_db
from app.models.stock import (
    MarketType,
    StockDetailResponse,
    StockListResponse,
)
from app.services import screener
from supabase import Client

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
async def list_stocks(
    market: MarketType | None = Query(None, description="Filter by market"),
    search: str | None = Query(None, description="Search by ticker or name"),
    limit: int = Query(100, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Client = Depends(get_db),
):
    """
    Get list of stocks with optional filtering.

    - **market**: Filter by market (US, KOSPI, KOSDAQ)
    - **search**: Search by ticker or company name
    - **limit**: Maximum number of results (default 100, max 500)
    - **offset**: Offset for pagination
    """
    total, stocks = await screener.get_stocks(
        db=db,
        market=market,
        search=search,
        limit=limit,
        offset=offset,
    )

    return StockListResponse(total=total, stocks=stocks)


@router.get("/{ticker}", response_model=StockDetailResponse)
async def get_stock(
    ticker: str,
    market: MarketType | None = Query(
        None, description="Market (required for KR stocks)"
    ),
    db: Client = Depends(get_db),
):
    """
    Get stock details by ticker.

    - **ticker**: Stock ticker symbol (e.g., AAPL, 005930)
    - **market**: Market type (optional for US, required for KR to disambiguate)
    """
    # Get company with metrics from view
    stock = await screener.get_stock_by_ticker(db, ticker, market)

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    # Get full company info
    company_result = db.table("companies").select("*").eq("ticker", ticker)
    if market:
        company_result = company_result.eq("market", market.value)
    company_data = company_result.execute()

    if not company_data.data:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    company = company_data.data[0]

    # Get latest metrics
    metrics_result = (
        db.table("metrics")
        .select("*")
        .eq("company_id", company["id"])
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    metrics = metrics_result.data[0] if metrics_result.data else None

    # Get latest price
    price_result = (
        db.table("prices")
        .select("*")
        .eq("company_id", company["id"])
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    price = price_result.data[0] if price_result.data else None

    return StockDetailResponse(
        company=company,
        metrics=metrics,
        price=price,
    )
