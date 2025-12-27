"""Screening API routes."""

from fastapi import APIRouter, Depends, Request

from app.core.database import get_db
from app.core.rate_limit import limiter, RATE_LIMITS
from app.models.stock import (
    PresetStrategy,
    ScreenRequest,
    ScreenResponse,
)
from app.services import screener
from supabase import Client

router = APIRouter(prefix="/screen", tags=["screening"])


@router.post("", response_model=ScreenResponse)
@limiter.limit(RATE_LIMITS["screen"])
async def screen_stocks(
    request: ScreenRequest,
    req: Request,
    db: Client = Depends(get_db),
):
    """
    Screen stocks based on filters and/or preset.

    - **filters**: List of metric filters (metric, operator, value)
    - **preset**: Preset strategy ID (graham, buffett, dividend, deep_value)
    - **market**: Filter by market (US, KOSPI, KOSDAQ)
    - **limit**: Maximum results (default 100, max 500)
    - **offset**: Offset for pagination

    Example filters:
    ```json
    {
        "filters": [
            {"metric": "pe_ratio", "operator": "<", "value": 15},
            {"metric": "roe", "operator": ">", "value": 0.15}
        ],
        "market": "US",
        "limit": 50
    }
    ```

    Or use a preset:
    ```json
    {
        "preset": "graham",
        "market": "US"
    }
    ```
    """
    filters = request.filters.copy()

    # If preset is specified, add its filters
    if request.preset:
        preset = screener.get_preset(request.preset)
        if preset:
            filters.extend(preset.filters)

    total, stocks = await screener.screen_stocks(
        db=db,
        filters=filters,
        market=request.market,
        limit=request.limit,
        offset=request.offset,
    )

    return ScreenResponse(total=total, stocks=stocks)


@router.get("/presets", response_model=list[PresetStrategy])
@limiter.limit(RATE_LIMITS["default"])
async def list_presets(request: Request):
    """
    Get all available preset strategies.

    Returns a list of preset strategies with their filters.
    """
    return screener.get_presets()


@router.get("/presets/{preset_id}", response_model=PresetStrategy)
@limiter.limit(RATE_LIMITS["default"])
async def get_preset(request: Request, preset_id: str):
    """
    Get a specific preset strategy by ID.

    Available presets:
    - **graham**: Benjamin Graham's classic value criteria
    - **buffett**: Warren Buffett style quality stocks
    - **dividend**: High dividend yield stocks
    - **deep_value**: Deep value stocks (low P/B, low P/E)
    """
    preset = screener.get_preset(preset_id)
    if not preset:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Preset {preset_id} not found")
    return preset
