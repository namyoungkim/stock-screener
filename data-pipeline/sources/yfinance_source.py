"""YFinance data source for US stocks."""

import asyncio
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf
from rate_limit import (
    FailureType,
    classify_failure,
)

from .base import BaseDataSource, FetchResult, ProgressCallback, TickerData

logger = logging.getLogger(__name__)


def _create_browser_session():
    """Create browser-like session.

    Note: curl_cffi with Chrome impersonate was causing Rate Limits.
    Using default requests session instead which works better.
    """
    # curl_cffi disabled - it triggers Yahoo Finance rate limiting
    # The default requests session works much better
    return None


@dataclass
class YFinanceSource(BaseDataSource):
    """YFinance data source for US stocks.

    Uses yfinance library to fetch stock data from Yahoo Finance.
    Includes TLS fingerprinting bypass using curl_cffi.
    """

    batch_size: int = 10
    history_batch_size: int = 300
    base_delay: float = 2.5
    jitter: float = 1.0
    history_days: int = 300
    max_workers: int = 4
    _session: Any = field(default=None, init=False, repr=False)
    _executor: ThreadPoolExecutor = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__(name="yfinance", market="US")
        self._session = _create_browser_session()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch latest prices using yf.download() in batches."""
        result = FetchResult()

        if not tickers:
            return result

        # Process in smaller batches to avoid rate limiting
        # 100 tickers per batch with 3s delay between batches
        price_batch_size = 100
        total_processed = 0

        for i in range(0, len(tickers), price_batch_size):
            batch = tickers[i : i + price_batch_size]

            try:
                # Use yf.download for batch price fetching
                # threads=False to avoid triggering rate limits
                df = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda b=batch: yf.download(
                        b,
                        period="5d",
                        progress=False,
                        threads=False,
                        session=self._session,
                    ),
                )

                if df.empty:
                    for ticker in batch:
                        result.failed[ticker] = "No price data"
                    continue

                # Extract trading date from the most recent data
                trading_date = self._extract_trading_date(df)

                # Process results
                for ticker in batch:
                    try:
                        price_data = self._extract_price_data(df, ticker, trading_date)
                        if price_data:
                            result.succeeded[ticker] = TickerData(
                                ticker=ticker,
                                prices=price_data,
                            )
                        else:
                            result.failed[ticker] = "No price data"
                    except Exception as e:
                        result.failed[ticker] = str(e)

                total_processed += len(batch)
                if on_progress:
                    on_progress(total_processed, len(tickers))

            except Exception as e:
                logger.error(f"Batch price fetch failed: {e}")
                for ticker in batch:
                    result.failed[ticker] = str(e)

            # Inter-batch delay
            if i + price_batch_size < len(tickers):
                await asyncio.sleep(self.base_delay + random.uniform(0, self.jitter))

        return result

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch OHLCV history using yf.download()."""
        result = FetchResult()

        if not tickers:
            return result

        # Calculate period string
        months = max(1, days // 30)
        period = f"{months}mo"

        # Process in batches for large ticker lists
        # Reduced batch size to avoid rate limiting
        history_batch = min(self.history_batch_size, 100)
        total_processed = 0
        for i in range(0, len(tickers), history_batch):
            batch = tickers[i : i + history_batch]

            try:
                # threads=False to avoid triggering rate limits
                df = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda b=batch: yf.download(
                        b,
                        period=period,
                        progress=False,
                        threads=False,
                        session=self._session,
                    ),
                )

                if df.empty:
                    for ticker in batch:
                        result.failed[ticker] = "No history data"
                    continue

                # Process each ticker
                for ticker in batch:
                    try:
                        history_df = self._extract_history(df, ticker)
                        if history_df is not None and not history_df.empty:
                            result.succeeded[ticker] = TickerData(
                                ticker=ticker,
                                history=history_df,
                            )
                        else:
                            result.failed[ticker] = "No history data"
                    except Exception as e:
                        result.failed[ticker] = str(e)

                total_processed += len(batch)
                if on_progress:
                    on_progress(total_processed, len(tickers))

            except Exception as e:
                logger.error(f"Batch history fetch failed: {e}")
                for ticker in batch:
                    result.failed[ticker] = str(e)

            # Inter-batch delay
            if i + history_batch < len(tickers):
                await asyncio.sleep(self.base_delay + random.uniform(0, self.jitter))

        return result

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch fundamental metrics using yf.Ticker().info.

        Note: This is the most rate-limited operation. Use with caution.
        """
        result = FetchResult()

        if not tickers:
            return result

        total_processed = 0
        for i in range(0, len(tickers), self.batch_size):
            batch = tickers[i : i + self.batch_size]

            for ticker in batch:
                try:
                    metrics = await self._fetch_single_metrics(ticker)
                    if metrics:
                        result.succeeded[ticker] = TickerData(
                            ticker=ticker,
                            metrics=metrics,
                        )
                    else:
                        result.failed[ticker] = "No metrics data"
                except Exception as e:
                    failure_type = classify_failure(e)
                    result.failed[ticker] = str(e)
                    if failure_type == FailureType.RATE_LIMIT:
                        logger.warning(f"Rate limit hit at {ticker}")
                        # Don't continue if rate limited
                        return result

            total_processed += len(batch)
            if on_progress:
                on_progress(total_processed, len(tickers))

            # Inter-batch delay
            if i + self.batch_size < len(tickers):
                await asyncio.sleep(self.base_delay + random.uniform(0, self.jitter))

        return result

    async def _fetch_single_metrics(self, ticker: str) -> dict | None:
        """Fetch metrics for a single ticker."""
        try:
            stock = yf.Ticker(ticker, session=self._session)
            info = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: stock.info,
            )

            if not info or info.get("regularMarketPrice") is None:
                return None

            return self._extract_metrics(info)

        except Exception as e:
            logger.debug(f"Failed to fetch metrics for {ticker}: {e}")
            raise

    def _extract_trading_date(self, df: pd.DataFrame) -> str:
        """Extract trading date from download DataFrame."""
        if df.empty:
            return date.today().isoformat()

        # Get the last valid date from index
        last_date = df.index[-1]
        if hasattr(last_date, "date"):
            return last_date.date().isoformat()
        return date.today().isoformat()

    def _extract_price_data(
        self, df: pd.DataFrame, ticker: str, trading_date: str
    ) -> dict | None:
        """Extract price data for a ticker from download DataFrame."""
        try:
            # Handle single ticker vs multiple ticker DataFrame structure
            if isinstance(df.columns, pd.MultiIndex):
                # Multiple tickers: columns are (field, ticker)
                if ticker not in df.columns.get_level_values(1):
                    return None
                close = df["Close"][ticker].dropna()
                open_ = df["Open"][ticker].dropna()
                high = df["High"][ticker].dropna()
                low = df["Low"][ticker].dropna()
                volume = df["Volume"][ticker].dropna()
            else:
                # Single ticker: columns are just fields
                close = df["Close"].dropna()
                open_ = df["Open"].dropna()
                high = df["High"].dropna()
                low = df["Low"].dropna()
                volume = df["Volume"].dropna()

            if close.empty:
                return None

            return {
                "close": float(close.iloc[-1]),
                "open": float(open_.iloc[-1]) if not open_.empty else None,
                "high": float(high.iloc[-1]) if not high.empty else None,
                "low": float(low.iloc[-1]) if not low.empty else None,
                "volume": int(volume.iloc[-1]) if not volume.empty else None,
                "date": trading_date,
            }

        except Exception as e:
            logger.debug(f"Failed to extract price data for {ticker}: {e}")
            return None

    def _extract_history(
        self, df: pd.DataFrame, ticker: str
    ) -> pd.DataFrame | None:
        """Extract history DataFrame for a ticker."""
        try:
            if isinstance(df.columns, pd.MultiIndex):
                # Multiple tickers
                if ticker not in df.columns.get_level_values(1):
                    return None
                history = df.xs(ticker, axis=1, level=1).dropna()
            else:
                # Single ticker
                history = df.dropna()

            if history.empty:
                return None

            # Ensure standard column names
            history.columns = [c.title() for c in history.columns]
            return history

        except Exception as e:
            logger.debug(f"Failed to extract history for {ticker}: {e}")
            return None

    def _extract_metrics(self, info: dict) -> dict:
        """Extract metrics from yfinance info dict."""
        def safe_get(key: str, default=None):
            val = info.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return val

        return {
            # Valuation
            "pe_ratio": safe_get("trailingPE"),
            "forward_pe": safe_get("forwardPE"),
            "pb_ratio": safe_get("priceToBook"),
            "ps_ratio": safe_get("priceToSalesTrailing12Months"),
            "peg_ratio": safe_get("pegRatio"),
            "ev_ebitda": safe_get("enterpriseToEbitda"),
            # Profitability
            "roe": safe_get("returnOnEquity"),
            "roa": safe_get("returnOnAssets"),
            "gross_margin": safe_get("grossMargins"),
            "net_margin": safe_get("profitMargins"),
            "operating_margin": safe_get("operatingMargins"),
            # Financial health
            "debt_equity": safe_get("debtToEquity"),
            "current_ratio": safe_get("currentRatio"),
            "quick_ratio": safe_get("quickRatio"),
            # Dividend
            "dividend_yield": safe_get("dividendYield"),
            "payout_ratio": safe_get("payoutRatio"),
            # Per share
            "eps": safe_get("trailingEps"),
            "book_value_per_share": safe_get("bookValue"),
            # Price levels
            "fifty_two_week_high": safe_get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": safe_get("fiftyTwoWeekLow"),
            "fifty_day_average": safe_get("fiftyDayAverage"),
            "two_hundred_day_average": safe_get("twoHundredDayAverage"),
            # Market data
            "market_cap": safe_get("marketCap"),
            "beta": safe_get("beta"),
            "shares_outstanding": safe_get("sharesOutstanding"),
            # Company info
            "name": safe_get("longName") or safe_get("shortName"),
            "sector": safe_get("sector"),
            "industry": safe_get("industry"),
        }

    async def close(self) -> None:
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False)
        if self._session and hasattr(self._session, "close"):
            self._session.close()
