"""Shared types for data pipeline.

These types are used across KR and US pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

import pandas as pd


class Market(str, Enum):
    """Stock market identifier."""

    KR = "kr"
    US = "us"


class CollectionPhase(str, Enum):
    """Pipeline collection phases."""

    INIT = "init"
    PRICES = "prices"
    HISTORY = "history"
    METRICS = "metrics"
    TECHNICALS = "technicals"
    SAVE = "save"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class TickerData:
    """Basic ticker information."""

    ticker: str
    name: str
    market: Market
    sector: str | None = None
    industry: str | None = None


@dataclass
class PriceData:
    """Current price data for a ticker."""

    ticker: str
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    change_percent: float | None = None

    @property
    def latest_price(self) -> float | None:
        """Get the most recent price (close)."""
        return self.close


@dataclass
class HistoryData:
    """Historical OHLCV data for a ticker."""

    ticker: str
    data: pd.DataFrame  # columns: date, open, high, low, close, volume

    @property
    def days(self) -> int:
        """Number of trading days in history."""
        return len(self.data)

    @property
    def start_date(self) -> date | None:
        """First date in history."""
        if self.data.empty:
            return None
        return self.data.index.min().date() if hasattr(self.data.index, "date") else None

    @property
    def end_date(self) -> date | None:
        """Last date in history."""
        if self.data.empty:
            return None
        return self.data.index.max().date() if hasattr(self.data.index, "date") else None


@dataclass
class MetricsData:
    """Fundamental and valuation metrics for a ticker."""

    ticker: str
    date: date

    # Valuation
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    peg_ratio: float | None = None
    ev_ebitda: float | None = None

    # Profitability
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None

    # Financial health
    debt_equity: float | None = None
    current_ratio: float | None = None

    # Per share
    eps: float | None = None
    bps: float | None = None
    graham_number: float | None = None

    # Dividend
    dividend_yield: float | None = None

    # Market data
    market_cap: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    # Moving averages
    ma_50: float | None = None
    ma_200: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "ticker": self.ticker,
            "date": self.date.isoformat() if isinstance(self.date, date) else self.date,
            "pe_ratio": self.pe_ratio,
            "forward_pe": self.forward_pe,
            "pb_ratio": self.pb_ratio,
            "ps_ratio": self.ps_ratio,
            "peg_ratio": self.peg_ratio,
            "ev_ebitda": self.ev_ebitda,
            "roe": self.roe,
            "roa": self.roa,
            "gross_margin": self.gross_margin,
            "net_margin": self.net_margin,
            "debt_equity": self.debt_equity,
            "current_ratio": self.current_ratio,
            "eps": self.eps,
            "bps": self.bps,
            "graham_number": self.graham_number,
            "dividend_yield": self.dividend_yield,
            "market_cap": self.market_cap,
            "beta": self.beta,
            "fifty_two_week_high": self.fifty_two_week_high,
            "fifty_two_week_low": self.fifty_two_week_low,
            "ma_50": self.ma_50,
            "ma_200": self.ma_200,
        }


@dataclass
class TechnicalIndicators:
    """Technical indicators calculated from history."""

    ticker: str
    date: date

    # Momentum
    rsi: float | None = None
    mfi: float | None = None

    # MACD
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    # Bollinger Bands
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_percent: float | None = None

    # Volume
    volume_change: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "ticker": self.ticker,
            "date": self.date.isoformat() if isinstance(self.date, date) else self.date,
            "rsi": self.rsi,
            "mfi": self.mfi,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "bb_upper": self.bb_upper,
            "bb_middle": self.bb_middle,
            "bb_lower": self.bb_lower,
            "bb_percent": self.bb_percent,
            "volume_change": self.volume_change,
        }


T = TypeVar("T")


@dataclass
class FetchResult(Generic[T]):
    """Result of a single fetch operation.

    Attributes:
        ticker: Ticker symbol
        data: Fetched data (if successful)
        error: Error that occurred (if failed)
        latency_ms: Request latency in milliseconds
        source: Data source name
    """

    ticker: str
    data: T | None = None
    error: Exception | None = None
    latency_ms: float = 0.0
    source: str = ""

    @property
    def is_success(self) -> bool:
        """Whether the fetch was successful."""
        return self.error is None and self.data is not None

    @property
    def is_retryable(self) -> bool:
        """Whether the error is retryable."""
        if self.error is None:
            return False
        from .errors import PipelineError

        if isinstance(self.error, PipelineError):
            return self.error.is_retryable
        return False


@dataclass
class BatchFetchResult(Generic[T]):
    """Result of a batch fetch operation."""

    results: list[FetchResult[T]] = field(default_factory=list)
    total_latency_ms: float = 0.0
    source: str = ""

    @property
    def succeeded(self) -> list[FetchResult[T]]:
        """Successfully fetched results."""
        return [r for r in self.results if r.is_success]

    @property
    def failed(self) -> list[FetchResult[T]]:
        """Failed fetch results."""
        return [r for r in self.results if not r.is_success]

    @property
    def success_count(self) -> int:
        """Number of successful fetches."""
        return len(self.succeeded)

    @property
    def failed_count(self) -> int:
        """Number of failed fetches."""
        return len(self.failed)

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        if not self.results:
            return 0.0
        return len(self.succeeded) / len(self.results) * 100


@dataclass
class CollectionResult:
    """Result of a complete collection run.

    Tracks overall success/failure and phase information.
    """

    market: Market
    started_at: datetime
    ended_at: datetime | None = None

    # Counts
    total_tickers: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    # Phase tracking
    phase: CollectionPhase = CollectionPhase.INIT
    current_batch: int = 0
    total_batches: int = 0

    # Errors
    errors: list[str] = field(default_factory=list)
    failed_tickers: list[str] = field(default_factory=list)

    # Flags
    rate_limit_hit: bool = False
    circuit_breaker_tripped: bool = False

    @property
    def is_complete(self) -> bool:
        """Whether collection completed successfully."""
        return self.phase == CollectionPhase.COMPLETE

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        if self.total_tickers == 0:
            return 0.0
        return self.successful / self.total_tickers * 100

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "market": self.market.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_tickers": self.total_tickers,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "phase": self.phase.value,
            "is_complete": self.is_complete,
            "rate_limit_hit": self.rate_limit_hit,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "error_count": len(self.errors),
        }
