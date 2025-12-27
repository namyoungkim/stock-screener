"""Stock-related Pydantic models."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class MarketType(str, Enum):
    """Market type enum."""

    US = "US"
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"


class CompanyBase(BaseModel):
    """Base company model."""

    ticker: str
    name: str
    market: MarketType
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"


class Company(CompanyBase):
    """Company model with ID."""

    id: str
    corp_code: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CompanyWithMetrics(Company):
    """Company with latest metrics."""

    # Price
    latest_price: float | None = None
    market_cap: float | None = None
    metrics_date: date | None = None

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None

    # Profitability
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None

    # Financial Health
    debt_equity: float | None = None
    current_ratio: float | None = None

    # Dividend
    dividend_yield: float | None = None

    # Graham Number
    eps: float | None = None
    book_value_per_share: float | None = None
    graham_number: float | None = None

    # Price Range
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    # Risk
    beta: float | None = None

    # Moving Averages
    fifty_day_average: float | None = None
    two_hundred_day_average: float | None = None

    # PEG
    peg_ratio: float | None = None

    # RSI
    rsi: float | None = None

    # Volume
    volume_change: float | None = None

    # MACD
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None


class Metrics(BaseModel):
    """Metrics model."""

    company_id: str
    date: date

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None

    # Profitability
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None

    # Financial Health
    debt_equity: float | None = None
    current_ratio: float | None = None

    # Dividend
    dividend_yield: float | None = None

    # Graham Number
    eps: float | None = None
    book_value_per_share: float | None = None
    graham_number: float | None = None

    # Price Range
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    # Risk
    beta: float | None = None

    # Moving Averages
    fifty_day_average: float | None = None
    two_hundred_day_average: float | None = None

    # PEG
    peg_ratio: float | None = None

    # RSI
    rsi: float | None = None

    # Volume
    volume_change: float | None = None

    # MACD
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    data_source: str | None = None


class Price(BaseModel):
    """Price model."""

    company_id: str
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None
    market_cap: float | None = None


class OperatorType(str, Enum):
    """Filter operator type."""

    LT = "<"
    LTE = "<="
    EQ = "="
    GTE = ">="
    GT = ">"


class MetricFilter(BaseModel):
    """Single metric filter."""

    metric: str
    operator: OperatorType
    value: float


class ScreenRequest(BaseModel):
    """Screening request model."""

    filters: list[MetricFilter] = Field(default_factory=list)
    preset: str | None = None
    market: MarketType | None = None
    limit: int = Field(default=100, le=500)
    offset: int = Field(default=0, ge=0)


class ScreenResponse(BaseModel):
    """Screening response model."""

    total: int
    stocks: list[CompanyWithMetrics]


class PresetStrategy(BaseModel):
    """Preset strategy model."""

    id: str
    name: str
    description: str
    filters: list[MetricFilter]


class StockListResponse(BaseModel):
    """Stock list response."""

    total: int
    stocks: list[CompanyWithMetrics]


class StockDetailResponse(BaseModel):
    """Stock detail response."""

    company: Company
    metrics: Metrics | None = None
    price: Price | None = None
