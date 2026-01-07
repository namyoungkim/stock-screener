"""FinanceDataReader data source for Korean stocks."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from config import get_settings
from config.constants import FDR_REQUEST_TIMEOUT, DEFAULT_HISTORY_DAYS

from .base import BaseDataSource, FetchResult, ProgressCallback, TickerData

logger = logging.getLogger(__name__)


@dataclass
class FDRSource(BaseDataSource):
    """FinanceDataReader data source for Korean stocks.

    Uses FinanceDataReader library (wraps Naver Finance) to fetch
    Korean stock prices and history.

    Note: FDR doesn't provide fundamental metrics.
    Use NaverSource or KISSource for metrics.
    """

    batch_size: int = 100
    history_days: int = DEFAULT_HISTORY_DAYS
    timeout: float = FDR_REQUEST_TIMEOUT
    _executor: ThreadPoolExecutor = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__(name="fdr", market="KR")
        self._executor = ThreadPoolExecutor(max_workers=8)

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch latest prices from FDR.

        Actually fetches recent history and extracts the latest price.
        """
        # FDR doesn't have a separate "latest price" API
        # We fetch short history and extract the latest
        return await self.fetch_history(
            tickers,
            days=5,  # Just need recent data for latest price
            on_progress=on_progress,
        )

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch OHLCV history from FDR."""
        import FinanceDataReader as fdr

        result = FetchResult()

        if not tickers:
            return result

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        total_processed = 0
        for i in range(0, len(tickers), self.batch_size):
            batch = tickers[i : i + self.batch_size]

            # Process batch concurrently using ThreadPoolExecutor
            futures = {}
            for ticker in batch:
                future = self._executor.submit(
                    self._fetch_single_history,
                    fdr,
                    ticker,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
                futures[ticker] = future

            # Collect results
            for ticker, future in futures.items():
                try:
                    df = future.result(timeout=self.timeout)
                    if df is not None and not df.empty:
                        # Extract latest price data
                        price_data = self._extract_latest_price(df)
                        result.succeeded[ticker] = TickerData(
                            ticker=ticker,
                            history=df,
                            prices=price_data,
                        )
                    else:
                        result.failed[ticker] = "No data"
                except FuturesTimeoutError:
                    result.failed[ticker] = "Timeout"
                    logger.warning(f"Timeout fetching {ticker}")
                except Exception as e:
                    result.failed[ticker] = str(e)
                    logger.debug(f"Failed to fetch {ticker}: {e}")

            total_processed += len(batch)
            if on_progress:
                on_progress(total_processed, len(tickers))

        return result

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """FDR doesn't provide fundamental metrics.

        Use NaverSource or KISSource for metrics.
        """
        result = FetchResult()
        for ticker in tickers:
            result.failed[ticker] = "FDR doesn't provide metrics"
        return result

    def _fetch_single_history(
        self,
        fdr,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """Fetch history for a single ticker (runs in thread)."""
        try:
            df = fdr.DataReader(ticker, start_date, end_date)
            if df is None or df.empty:
                return None

            # Standardize column names
            df.columns = [c.title() for c in df.columns]

            # Ensure we have required columns
            required = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in df.columns for col in required):
                return None

            return df

        except Exception as e:
            logger.debug(f"FDR fetch failed for {ticker}: {e}")
            return None

    def _extract_latest_price(self, df: pd.DataFrame) -> dict | None:
        """Extract latest price data from history DataFrame."""
        if df is None or df.empty:
            return None

        try:
            last_row = df.iloc[-1]
            trading_date = df.index[-1]

            if hasattr(trading_date, "date"):
                date_str = trading_date.date().isoformat()
            else:
                date_str = str(trading_date)[:10]

            return {
                "close": float(last_row["Close"]),
                "open": float(last_row["Open"]),
                "high": float(last_row["High"]),
                "low": float(last_row["Low"]),
                "volume": int(last_row["Volume"]),
                "date": date_str,
            }

        except Exception as e:
            logger.debug(f"Failed to extract latest price: {e}")
            return None

    async def fetch_index_history(
        self,
        index_code: str = "KS11",  # KOSPI
        days: int = 300,
    ) -> pd.DataFrame | None:
        """Fetch index history (for Beta calculation)."""
        import FinanceDataReader as fdr

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        try:
            df = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: fdr.DataReader(
                    index_code,
                    start_date.isoformat(),
                    end_date.isoformat(),
                ),
            )

            if df is not None and not df.empty:
                df.columns = [c.title() for c in df.columns]
                return df

        except Exception as e:
            logger.warning(f"Failed to fetch index {index_code}: {e}")

        return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)


@dataclass
class NaverSource(BaseDataSource):
    """Naver Finance scraper for Korean stock metrics.

    Provides fundamental metrics like PER, PBR, ROE, ROA.
    Uses web scraping, so be careful with rate limits.
    """

    concurrency: int = 10
    timeout: float = 10.0
    delay: float = 0.1

    def __post_init__(self) -> None:
        super().__init__(name="naver", market="KR")

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Naver source doesn't provide efficient price fetching.

        Use FDRSource for prices.
        """
        result = FetchResult()
        for ticker in tickers:
            result.failed[ticker] = "Use FDRSource for prices"
        return result

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Naver source doesn't provide efficient history fetching.

        Use FDRSource for history.
        """
        result = FetchResult()
        for ticker in tickers:
            result.failed[ticker] = "Use FDRSource for history"
        return result

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch fundamental metrics from Naver Finance."""
        from common.naver_finance import NaverFinanceClient

        result = FetchResult()

        if not tickers:
            return result

        try:
            async with NaverFinanceClient(
                concurrency=self.concurrency,
                timeout=self.timeout,
                delay_between_requests=self.delay,
            ) as client:
                naver_data = await client.fetch_bulk(tickers)

            for ticker, data in naver_data.items():
                if data:
                    result.succeeded[ticker] = TickerData(
                        ticker=ticker,
                        metrics=data,
                    )
                else:
                    result.failed[ticker] = "No metrics data"

            # Mark not found tickers as failed
            for ticker in tickers:
                if ticker not in result.succeeded and ticker not in result.failed:
                    result.failed[ticker] = "No metrics data"

            if on_progress:
                on_progress(len(tickers), len(tickers))

        except Exception as e:
            logger.error(f"Naver bulk fetch failed: {e}")
            for ticker in tickers:
                if ticker not in result.succeeded:
                    result.failed[ticker] = str(e)

        return result

    async def close(self) -> None:
        """No resources to clean up."""
        pass


@dataclass
class KISSource(BaseDataSource):
    """KIS (Korea Investment & Securities) API source.

    Provides accurate fundamental metrics from official source.
    Requires API credentials.
    """

    app_key: str | None = None
    app_secret: str | None = None
    paper_trading: bool = False

    def __post_init__(self) -> None:
        super().__init__(name="kis", market="KR")

        # Load from settings if not provided
        if not self.app_key or not self.app_secret:
            settings = get_settings()
            self.app_key = settings.kis_app_key
            self.app_secret = settings.kis_app_secret
            self.paper_trading = settings.kis_paper_trading

    @property
    def is_available(self) -> bool:
        """Check if KIS API is configured."""
        return bool(self.app_key and self.app_secret)

    async def fetch_prices(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """KIS source is primarily for metrics.

        Use FDRSource for prices.
        """
        result = FetchResult()
        for ticker in tickers:
            result.failed[ticker] = "Use FDRSource for prices"
        return result

    async def fetch_history(
        self,
        tickers: list[str],
        days: int = 300,
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """KIS source is primarily for metrics.

        Use FDRSource for history.
        """
        result = FetchResult()
        for ticker in tickers:
            result.failed[ticker] = "Use FDRSource for history"
        return result

    async def fetch_metrics(
        self,
        tickers: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """Fetch fundamental metrics from KIS API."""
        from common.kis_client import KISClient

        result = FetchResult()

        if not self.is_available:
            logger.warning("KIS API not configured")
            for ticker in tickers:
                result.failed[ticker] = "KIS API not configured"
            return result

        try:
            async with KISClient(
                app_key=self.app_key,
                app_secret=self.app_secret,
                paper_trading=self.paper_trading,
            ) as client:
                kis_data = await client.fetch_bulk_fundamentals(tickers)

            for ticker, data in kis_data.items():
                if data:
                    result.succeeded[ticker] = TickerData(
                        ticker=ticker,
                        metrics=data,
                    )
                else:
                    result.failed[ticker] = "No metrics data"

            if on_progress:
                on_progress(len(tickers), len(tickers))

        except Exception as e:
            logger.error(f"KIS bulk fetch failed: {e}")
            for ticker in tickers:
                if ticker not in result.succeeded:
                    result.failed[ticker] = str(e)

        return result

    async def close(self) -> None:
        """No resources to clean up."""
        pass
