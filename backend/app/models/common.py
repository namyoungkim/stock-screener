"""Common types and constants for input validation."""

from enum import Enum
from typing import Annotated

from pydantic import Field

# UUID v4 pattern
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class MetricType(str, Enum):
    """Allowed metric types for filtering and alerts (whitelist)."""

    # Valuation
    PE_RATIO = "pe_ratio"
    FORWARD_PE = "forward_pe"
    PB_RATIO = "pb_ratio"
    PS_RATIO = "ps_ratio"
    EV_EBITDA = "ev_ebitda"
    PEG_RATIO = "peg_ratio"

    # Profitability
    ROE = "roe"
    ROA = "roa"
    GROSS_MARGIN = "gross_margin"
    NET_MARGIN = "net_margin"

    # Financial Health
    DEBT_EQUITY = "debt_equity"
    CURRENT_RATIO = "current_ratio"

    # Dividend & Risk
    DIVIDEND_YIELD = "dividend_yield"
    BETA = "beta"

    # Price Range
    FIFTY_TWO_WEEK_HIGH = "fifty_two_week_high"
    FIFTY_TWO_WEEK_LOW = "fifty_two_week_low"

    # Moving Averages
    FIFTY_DAY_AVERAGE = "fifty_day_average"
    TWO_HUNDRED_DAY_AVERAGE = "two_hundred_day_average"

    # Technical Indicators
    RSI = "rsi"
    MFI = "mfi"
    MACD = "macd"
    MACD_SIGNAL = "macd_signal"
    MACD_HISTOGRAM = "macd_histogram"

    # Bollinger Bands
    BB_UPPER = "bb_upper"
    BB_MIDDLE = "bb_middle"
    BB_LOWER = "bb_lower"
    BB_PERCENT = "bb_percent"

    # Volume & Graham
    VOLUME_CHANGE = "volume_change"
    EPS = "eps"
    BOOK_VALUE_PER_SHARE = "book_value_per_share"
    GRAHAM_NUMBER = "graham_number"

    # Price (for alerts)
    LATEST_PRICE = "latest_price"
    MARKET_CAP = "market_cap"


# Reusable Annotated types for validation
CompanyId = Annotated[
    str,
    Field(
        pattern=UUID_PATTERN,
        description="Company UUID (v4 format)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
]

MetricValue = Annotated[
    float,
    Field(
        ge=-1e12,
        le=1e12,
        description="Metric value with reasonable bounds (-1 trillion to +1 trillion)",
    ),
]

TargetPrice = Annotated[
    float,
    Field(
        gt=0,
        le=1e9,
        description="Target price (positive, max 1 billion)",
    ),
]

NotesField = Annotated[
    str,
    Field(
        max_length=1000,
        description="User notes (max 1000 characters)",
    ),
]

DescriptionField = Annotated[
    str,
    Field(
        max_length=500,
        description="Description text (max 500 characters)",
    ),
]
