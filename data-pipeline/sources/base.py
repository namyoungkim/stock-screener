"""Base protocol and data classes for data sources."""

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

import pandas as pd


@dataclass
class TickerData:
    """Unified data container for a single ticker.

    This is the canonical format that all data sources should produce.
    Collectors work with this format regardless of the underlying source.
    """

    ticker: str
    prices: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    history: pd.DataFrame | None = None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        """Check if this ticker has valid data (no error and has some data)."""
        return self.error is None and (
            self.prices is not None
            or self.metrics is not None
            or self.history is not None
        )


@dataclass
class FetchResult:
    """Result of a batch fetch operation.

    Contains successful results and failed tickers with their errors.
    """

    succeeded: dict[str, TickerData] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)  # ticker -> error message

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    def merge(self, other: "FetchResult") -> "FetchResult":
        """Merge another FetchResult into this one."""
        return FetchResult(
            succeeded={**self.succeeded, **other.succeeded},
            failed={**self.failed, **other.failed},
        )


# Type alias for progress callback: (completed, total) -> None
ProgressCallback = Callable[[int, int], None]


@runtime_checkable
class DataSource(Protocol):
    """Protocol for data sources (yfinance, FDR, Naver, KIS).

    All data sources must implement this protocol to be used with collectors.
    The protocol is runtime checkable, so you can use isinstance() to verify.

    Methods are async to support both sync and async implementations.
    Sync implementations can use asyncio.to_thread() or similar wrappers.
    """

    @property
    def name(self) -> str:
        """Source identifier (e.g., 'yfinance', 'fdr', 'naver', 'kis')."""
        ...

    @property
    def market(self) -> str:
        """Market this source is for ('US', 'KR', or 'ALL')."""
        ...

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch latest prices for tickers.

        Args:
            tickers: List of ticker symbols to fetch
            on_progress: Optional callback for progress updates

        Returns:
            FetchResult with succeeded tickers containing prices dict:
            {
                "close": float,
                "open": float,
                "high": float,
                "low": float,
                "volume": int,
                "date": str (YYYY-MM-DD),
            }
        """
        ...

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch OHLCV history for tickers.

        Args:
            tickers: List of ticker symbols to fetch
            days: Number of days of history to fetch
            on_progress: Optional callback for progress updates

        Returns:
            FetchResult with succeeded tickers containing history DataFrame:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index: DatetimeIndex
        """
        ...

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch fundamental metrics for tickers.

        Args:
            tickers: List of ticker symbols to fetch
            on_progress: Optional callback for progress updates

        Returns:
            FetchResult with succeeded tickers containing metrics dict.
            The exact fields depend on the source, but common fields include:
            - pe_ratio, forward_pe
            - pb_ratio, ps_ratio
            - roe, roa
            - dividend_yield
            - market_cap
            - eps, book_value_per_share
            - fifty_two_week_high, fifty_two_week_low
            - etc.
        """
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP sessions).

        This should be called when the source is no longer needed.
        Sources should also implement __aenter__ and __aexit__ for
        async context manager support.
        """
        ...


class BaseDataSource:
    """Base implementation with common functionality.

    Subclasses should override the fetch methods and implement
    the actual data fetching logic.
    """

    def __init__(self, name: str, market: str):
        self._name = name
        self._market = market

    @property
    def name(self) -> str:
        return self._name

    @property
    def market(self) -> str:
        return self._market

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        raise NotImplementedError("Subclass must implement fetch_prices")

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        raise NotImplementedError("Subclass must implement fetch_history")

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        raise NotImplementedError("Subclass must implement fetch_metrics")

    async def close(self) -> None:
        """Default no-op close."""
        pass

    async def __aenter__(self) -> "BaseDataSource":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
