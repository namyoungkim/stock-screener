"""YFinance data source for US stocks.

yfinance library provides:
- Current prices (batch via yf.download)
- Historical OHLCV data (batch via yf.download)
- Fundamental metrics (individual via yf.Ticker().info)

Note: yf.Ticker().info is rate-limited by Yahoo Finance.
Use circuit breaker and rate limiter for metrics fetching.
"""

from __future__ import annotations

import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd
import yfinance as yf

from core.errors import (
    DataNotFoundError,
    RateLimitError,
    TimeoutError,
    classify_exception,
)
from core.types import (
    BatchFetchResult,
    FetchResult,
    HistoryData,
    MetricsData,
    PriceData,
)
from observability.logger import get_logger, log_context

if TYPE_CHECKING:
    from us.config import USConfig

logger = get_logger(__name__)


@dataclass
class YFinanceSource:
    """YFinance data source for US stocks.

    Provides price, history, and metrics data for US stocks.
    Includes rate limiting and circuit breaker protection.
    """

    config: USConfig
    _executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize ThreadPoolExecutor."""
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

    async def fetch_prices(
        self,
        tickers: list[str],
    ) -> BatchFetchResult[PriceData]:
        """Fetch latest prices for multiple tickers.

        Uses yf.download() which is more forgiving of rate limits.

        Args:
            tickers: List of US ticker symbols

        Returns:
            BatchFetchResult containing PriceData for each ticker
        """
        results: list[FetchResult[PriceData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="yfinance")

        batch_size = self.config.price_batch_size

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_start = time.monotonic()

            with log_context(
                source="yfinance",
                phase="prices",
                batch_index=i // batch_size,
                batch_size=len(batch),
            ):
                try:
                    # Use yf.download for batch price fetching
                    df = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            lambda b=batch: yf.download(
                                b,
                                period="5d",
                                progress=False,
                                threads=False,
                            ),
                        ),
                        timeout=self.config.download_timeout,
                    )

                    batch_latency = (time.monotonic() - batch_start) * 1000

                    if df.empty:
                        logger.warning(f"Empty response for batch starting with {batch[0]}")
                        for ticker in batch:
                            results.append(
                                FetchResult(
                                    ticker=ticker,
                                    error=DataNotFoundError("No price data", ticker=ticker),
                                    latency_ms=batch_latency / len(batch),
                                    source="yfinance",
                                )
                            )
                    else:
                        # Extract trading date
                        trading_date = self._extract_trading_date(df)

                        # Process each ticker
                        for ticker in batch:
                            price = self._extract_price_data(df, ticker, trading_date)
                            if price:
                                results.append(
                                    FetchResult(
                                        ticker=ticker,
                                        data=price,
                                        latency_ms=batch_latency / len(batch),
                                        source="yfinance",
                                    )
                                )
                            else:
                                results.append(
                                    FetchResult(
                                        ticker=ticker,
                                        error=DataNotFoundError(
                                            "No price data", ticker=ticker
                                        ),
                                        latency_ms=batch_latency / len(batch),
                                        source="yfinance",
                                    )
                                )

                    total_latency += batch_latency

                except asyncio.TimeoutError:
                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency
                    logger.warning(f"Timeout fetching prices for batch starting with {batch[0]}")
                    for ticker in batch:
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=TimeoutError(
                                    f"Timeout after {self.config.download_timeout}s",
                                    timeout=self.config.download_timeout,
                                    ticker=ticker,
                                ),
                                latency_ms=batch_latency / len(batch),
                                source="yfinance",
                            )
                        )

                except Exception as e:
                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency
                    error = classify_exception(e, source="yfinance")
                    logger.error(f"Batch price fetch failed: {e}")
                    for ticker in batch:
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=error,
                                latency_ms=batch_latency / len(batch),
                                source="yfinance",
                            )
                        )

                # Log batch completion
                batch_succeeded = sum(1 for r in results[i:] if r.is_success)
                logger.info(
                    "Batch completed",
                    extra={
                        "success_count": batch_succeeded,
                        "failed_count": len(batch) - batch_succeeded,
                        "duration_ms": round(batch_latency, 2),
                    },
                )

            # Inter-batch delay
            if i + batch_size < len(tickers):
                delay = self.config.batch_delay + random.uniform(0, self.config.batch_jitter)
                await asyncio.sleep(delay)

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="yfinance",
        )

    async def fetch_history(
        self,
        tickers: list[str],
        days: int | None = None,
    ) -> BatchFetchResult[HistoryData]:
        """Fetch OHLCV history for multiple tickers.

        Args:
            tickers: List of US ticker symbols
            days: Number of days of history (default: from config)

        Returns:
            BatchFetchResult containing HistoryData for each ticker
        """
        results: list[FetchResult[HistoryData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="yfinance")

        if days is None:
            days = self.config.history_days

        # Calculate period string
        months = max(1, days // 30)
        period = f"{months}mo"

        batch_size = self.config.history_batch_size

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_start = time.monotonic()

            with log_context(
                source="yfinance",
                phase="history",
                batch_index=i // batch_size,
                batch_size=len(batch),
            ):
                try:
                    df = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            lambda b=batch: yf.download(
                                b,
                                period=period,
                                progress=False,
                                threads=False,
                            ),
                        ),
                        timeout=self.config.download_timeout,
                    )

                    batch_latency = (time.monotonic() - batch_start) * 1000

                    if df.empty:
                        logger.warning(f"Empty history for batch starting with {batch[0]}")
                        for ticker in batch:
                            results.append(
                                FetchResult(
                                    ticker=ticker,
                                    error=DataNotFoundError(
                                        "No history data", ticker=ticker
                                    ),
                                    latency_ms=batch_latency / len(batch),
                                    source="yfinance",
                                )
                            )
                    else:
                        for ticker in batch:
                            history = self._extract_history(df, ticker)
                            if history is not None and not history.empty:
                                results.append(
                                    FetchResult(
                                        ticker=ticker,
                                        data=HistoryData(ticker=ticker, data=history),
                                        latency_ms=batch_latency / len(batch),
                                        source="yfinance",
                                    )
                                )
                            else:
                                results.append(
                                    FetchResult(
                                        ticker=ticker,
                                        error=DataNotFoundError(
                                            "No history data", ticker=ticker
                                        ),
                                        latency_ms=batch_latency / len(batch),
                                        source="yfinance",
                                    )
                                )

                    total_latency += batch_latency

                except asyncio.TimeoutError:
                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency
                    logger.warning(f"Timeout fetching history for batch starting with {batch[0]}")
                    for ticker in batch:
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=TimeoutError(
                                    f"Timeout after {self.config.download_timeout}s",
                                    timeout=self.config.download_timeout,
                                    ticker=ticker,
                                ),
                                latency_ms=batch_latency / len(batch),
                                source="yfinance",
                            )
                        )

                except Exception as e:
                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency
                    error = classify_exception(e, source="yfinance")
                    logger.error(f"Batch history fetch failed: {e}")
                    for ticker in batch:
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=error,
                                latency_ms=batch_latency / len(batch),
                                source="yfinance",
                            )
                        )

                # Log batch completion
                batch_succeeded = sum(1 for r in results[i:] if r.is_success)
                logger.info(
                    "Batch completed",
                    extra={
                        "success_count": batch_succeeded,
                        "failed_count": len(batch) - batch_succeeded,
                        "duration_ms": round(batch_latency, 2),
                    },
                )

            # Inter-batch delay
            if i + batch_size < len(tickers):
                delay = self.config.batch_delay + random.uniform(0, self.config.batch_jitter)
                await asyncio.sleep(delay)

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="yfinance",
        )

    async def fetch_metrics(
        self,
        tickers: list[str],
        trading_date: date | None = None,
    ) -> BatchFetchResult[MetricsData]:
        """Fetch fundamental metrics for multiple tickers.

        WARNING: This uses yf.Ticker().info which is heavily rate-limited.
        Use circuit breaker and rate limiter for protection.

        Args:
            tickers: List of US ticker symbols
            trading_date: Date for the metrics

        Returns:
            BatchFetchResult containing MetricsData for each ticker
        """
        if trading_date is None:
            trading_date = date.today()

        results: list[FetchResult[MetricsData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="yfinance")

        batch_size = self.config.metrics_batch_size

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_start = time.monotonic()

            with log_context(
                source="yfinance",
                phase="metrics",
                batch_index=i // batch_size,
                batch_size=len(batch),
            ):
                for ticker in batch:
                    result = await self._fetch_single_metrics(ticker, trading_date)
                    results.append(result)

                batch_latency = (time.monotonic() - batch_start) * 1000
                total_latency += batch_latency

                # Log batch completion
                batch_succeeded = sum(1 for r in results[i:] if r.is_success)
                logger.info(
                    "Batch completed",
                    extra={
                        "success_count": batch_succeeded,
                        "failed_count": len(batch) - batch_succeeded,
                        "duration_ms": round(batch_latency, 2),
                    },
                )

            # Inter-batch delay
            if i + batch_size < len(tickers):
                delay = self.config.batch_delay + random.uniform(0, self.config.batch_jitter)
                await asyncio.sleep(delay)

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="yfinance",
        )

    async def _fetch_single_metrics(
        self,
        ticker: str,
        trading_date: date,
    ) -> FetchResult[MetricsData]:
        """Fetch metrics for a single ticker."""
        fetch_start = time.monotonic()

        try:
            stock = yf.Ticker(ticker)
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda: stock.info,
                ),
                timeout=self.config.info_timeout,
            )

            latency = (time.monotonic() - fetch_start) * 1000

            if not info or info.get("regularMarketPrice") is None:
                return FetchResult(
                    ticker=ticker,
                    error=DataNotFoundError("No metrics data", ticker=ticker),
                    latency_ms=latency,
                    source="yfinance",
                )

            metrics = self._extract_metrics(info, ticker, trading_date)

            return FetchResult(
                ticker=ticker,
                data=metrics,
                latency_ms=latency,
                source="yfinance",
            )

        except asyncio.TimeoutError:
            latency = (time.monotonic() - fetch_start) * 1000
            return FetchResult(
                ticker=ticker,
                error=TimeoutError(
                    f"Timeout after {self.config.info_timeout}s",
                    timeout=self.config.info_timeout,
                    ticker=ticker,
                ),
                latency_ms=latency,
                source="yfinance",
            )

        except Exception as e:
            latency = (time.monotonic() - fetch_start) * 1000

            # Check for rate limit
            if self._is_rate_limit_error(e):
                return FetchResult(
                    ticker=ticker,
                    error=RateLimitError(str(e), ticker=ticker),
                    latency_ms=latency,
                    source="yfinance",
                )

            return FetchResult(
                ticker=ticker,
                error=classify_exception(e, source="yfinance"),
                latency_ms=latency,
                source="yfinance",
            )

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error indicates rate limiting."""
        error_str = str(error).lower()
        rate_limit_indicators = ["429", "rate limit", "too many requests", "throttl"]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    def _extract_trading_date(self, df: pd.DataFrame) -> date:
        """Extract trading date from download DataFrame."""
        if df.empty:
            return date.today()

        last_date = df.index[-1]
        if hasattr(last_date, "date"):
            return last_date.date()
        return date.today()

    def _extract_price_data(
        self,
        df: pd.DataFrame,
        ticker: str,
        trading_date: date,
    ) -> PriceData | None:
        """Extract price data for a ticker from download DataFrame."""
        try:
            # Handle single ticker vs multiple ticker DataFrame structure
            if isinstance(df.columns, pd.MultiIndex):
                if ticker not in df.columns.get_level_values(1):
                    return None
                close = df["Close"][ticker].dropna()
                open_ = df["Open"][ticker].dropna()
                high = df["High"][ticker].dropna()
                low = df["Low"][ticker].dropna()
                volume = df["Volume"][ticker].dropna()
            else:
                close = df["Close"].dropna()
                open_ = df["Open"].dropna()
                high = df["High"].dropna()
                low = df["Low"].dropna()
                volume = df["Volume"].dropna()

            if close.empty:
                return None

            # Calculate change percent
            change_percent = None
            if len(close) > 1:
                prev_close = close.iloc[-2]
                if prev_close and prev_close > 0:
                    change_percent = (
                        (float(close.iloc[-1]) - float(prev_close)) / float(prev_close)
                    ) * 100

            return PriceData(
                ticker=ticker,
                date=trading_date,
                open=float(open_.iloc[-1]) if not open_.empty else None,
                high=float(high.iloc[-1]) if not high.empty else None,
                low=float(low.iloc[-1]) if not low.empty else None,
                close=float(close.iloc[-1]),
                volume=int(volume.iloc[-1]) if not volume.empty else None,
                change_percent=change_percent,
            )

        except Exception as e:
            logger.debug(f"Failed to extract price data for {ticker}: {e}")
            return None

    def _extract_history(
        self,
        df: pd.DataFrame,
        ticker: str,
    ) -> pd.DataFrame | None:
        """Extract history DataFrame for a ticker."""
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if ticker not in df.columns.get_level_values(1):
                    return None
                history = df.xs(ticker, axis=1, level=1).dropna()
            else:
                history = df.dropna()

            if history.empty:
                return None

            # Ensure standard column names
            history.columns = [c.title() for c in history.columns]
            return history

        except Exception as e:
            logger.debug(f"Failed to extract history for {ticker}: {e}")
            return None

    def _extract_metrics(
        self,
        info: dict[str, Any],
        ticker: str,
        trading_date: date,
    ) -> MetricsData:
        """Extract metrics from yfinance info dict."""

        def safe_get(key: str) -> Any:
            val = info.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return val

        return MetricsData(
            ticker=ticker,
            date=trading_date,
            # Valuation
            pe_ratio=safe_get("trailingPE"),
            forward_pe=safe_get("forwardPE"),
            pb_ratio=safe_get("priceToBook"),
            ps_ratio=safe_get("priceToSalesTrailing12Months"),
            peg_ratio=safe_get("pegRatio"),
            ev_ebitda=safe_get("enterpriseToEbitda"),
            # Profitability
            roe=safe_get("returnOnEquity"),
            roa=safe_get("returnOnAssets"),
            gross_margin=safe_get("grossMargins"),
            net_margin=safe_get("profitMargins"),
            # Financial health
            debt_equity=safe_get("debtToEquity"),
            current_ratio=safe_get("currentRatio"),
            # Dividend
            dividend_yield=safe_get("dividendYield"),
            # Per share
            eps=safe_get("trailingEps"),
            bps=safe_get("bookValue"),
            # Price levels
            fifty_two_week_high=safe_get("fiftyTwoWeekHigh"),
            fifty_two_week_low=safe_get("fiftyTwoWeekLow"),
            ma_50=safe_get("fiftyDayAverage"),
            ma_200=safe_get("twoHundredDayAverage"),
            # Market data
            market_cap=safe_get("marketCap"),
            beta=safe_get("beta"),
        )

    async def fetch_index_history(
        self,
        index_code: str = "^GSPC",  # S&P 500
        days: int | None = None,
    ) -> pd.DataFrame | None:
        """Fetch index history for Beta calculation.

        Args:
            index_code: Index code (^GSPC=S&P500, ^DJI=Dow Jones)
            days: Number of days of history

        Returns:
            DataFrame with index OHLCV or None if failed
        """
        if days is None:
            days = self.config.history_days

        months = max(1, days // 30)
        period = f"{months}mo"

        try:
            df = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda: yf.download(
                        index_code,
                        period=period,
                        progress=False,
                        threads=False,
                    ),
                ),
                timeout=self.config.download_timeout,
            )

            if df is not None and not df.empty:
                df.columns = [c.title() for c in df.columns]
                return df

            return None

        except Exception as e:
            logger.debug(f"Failed to fetch index {index_code}: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
