"""FinanceDataReader source for Korean stocks.

FDR (FinanceDataReader) wraps Naver Finance to provide:
- Current prices (latest OHLCV)
- Historical OHLCV data (300 days)
- Index data for Beta calculation (KOSPI, KOSDAQ)

Note: FDR doesn't provide fundamental metrics.
Use NaverSource or KIS API for metrics.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd

from core.errors import DataNotFoundError, TimeoutError, classify_exception
from core.types import (
    BatchFetchResult,
    FetchResult,
    HistoryData,
    PriceData,
)
from observability.logger import get_logger, log_context

if TYPE_CHECKING:
    from kr.config import KRConfig

logger = get_logger(__name__)


@dataclass
class FDRSource:
    """FinanceDataReader data source for Korean stocks.

    Provides price and history data for Korean stocks.
    Uses ThreadPoolExecutor for concurrent fetching.
    """

    config: KRConfig
    _executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize ThreadPoolExecutor."""
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

    async def fetch_prices(
        self,
        tickers: list[str],
    ) -> BatchFetchResult[PriceData]:
        """Fetch latest prices for multiple tickers.

        Actually fetches recent history (5 days) and extracts the latest price.

        Args:
            tickers: List of KRX ticker codes (e.g., ["005930", "000660"])

        Returns:
            BatchFetchResult containing PriceData for each ticker
        """
        # FDR doesn't have a separate "latest price" API
        # We fetch short history and extract the latest
        history_result = await self.fetch_history(tickers, days=5)

        # Convert HistoryData to PriceData
        price_results: list[FetchResult[PriceData]] = []

        for result in history_result.results:
            if result.is_success and result.data is not None:
                price_data = self._extract_price_from_history(result.data)
                if price_data:
                    price_results.append(
                        FetchResult(
                            ticker=result.ticker,
                            data=price_data,
                            latency_ms=result.latency_ms,
                            source="fdr",
                        )
                    )
                else:
                    price_results.append(
                        FetchResult(
                            ticker=result.ticker,
                            error=DataNotFoundError(
                                "Cannot extract price from history",
                                ticker=result.ticker,
                            ),
                            latency_ms=result.latency_ms,
                            source="fdr",
                        )
                    )
            else:
                price_results.append(
                    FetchResult(
                        ticker=result.ticker,
                        error=result.error,
                        latency_ms=result.latency_ms,
                        source="fdr",
                    )
                )

        return BatchFetchResult(
            results=price_results,
            total_latency_ms=history_result.total_latency_ms,
            source="fdr",
        )

    async def fetch_history(
        self,
        tickers: list[str],
        days: int | None = None,
    ) -> BatchFetchResult[HistoryData]:
        """Fetch OHLCV history for multiple tickers.

        Args:
            tickers: List of KRX ticker codes
            days: Number of days of history (default: from config)

        Returns:
            BatchFetchResult containing HistoryData for each ticker
        """
        import FinanceDataReader as fdr

        if days is None:
            days = self.config.history_days

        results: list[FetchResult[HistoryData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="fdr")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Process in batches
        batch_size = self.config.history_batch_size

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_start = time.monotonic()

            with log_context(
                source="fdr",
                phase="history",
                batch_index=i // batch_size,
                batch_size=len(batch),
            ):
                # Submit all tasks to executor
                futures = {}
                assert self._executor is not None, "_executor not initialized"

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
                    fetch_start = time.monotonic()
                    try:
                        df = future.result(timeout=self.config.fdr_timeout)
                        latency = (time.monotonic() - fetch_start) * 1000

                        if df is not None and not df.empty:
                            results.append(
                                FetchResult(
                                    ticker=ticker,
                                    data=HistoryData(ticker=ticker, data=df),
                                    latency_ms=latency,
                                    source="fdr",
                                )
                            )
                        else:
                            results.append(
                                FetchResult(
                                    ticker=ticker,
                                    error=DataNotFoundError(
                                        "No history data",
                                        ticker=ticker,
                                    ),
                                    latency_ms=latency,
                                    source="fdr",
                                )
                            )

                    except FuturesTimeoutError:
                        latency = (time.monotonic() - fetch_start) * 1000
                        logger.warning(
                            "Timeout fetching history",
                            extra={"ticker": ticker, "timeout": self.config.fdr_timeout},
                        )
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=TimeoutError(
                                    f"Timeout after {self.config.fdr_timeout}s",
                                    timeout=self.config.fdr_timeout,
                                    ticker=ticker,
                                ),
                                latency_ms=latency,
                                source="fdr",
                            )
                        )

                    except Exception as e:
                        latency = (time.monotonic() - fetch_start) * 1000
                        logger.debug(
                            f"Failed to fetch history for {ticker}: {e}",
                            extra={"ticker": ticker},
                        )
                        results.append(
                            FetchResult(
                                ticker=ticker,
                                error=classify_exception(e, source="fdr"),
                                latency_ms=latency,
                                source="fdr",
                            )
                        )

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

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="fdr",
        )

    async def fetch_index_history(
        self,
        index_code: str = "KS11",
        days: int | None = None,
    ) -> pd.DataFrame | None:
        """Fetch index history for Beta calculation.

        Args:
            index_code: Index code (KS11=KOSPI, KQ11=KOSDAQ)
            days: Number of days of history

        Returns:
            DataFrame with index OHLCV or None if failed
        """
        import FinanceDataReader as fdr

        if days is None:
            days = self.config.history_days

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Try multiple index codes in case one fails
        index_codes = [index_code]
        if index_code == "KS11":
            index_codes = ["^KS11", "KS11"]  # Try Yahoo format first
        elif index_code == "KQ11":
            index_codes = ["^KQ11", "KQ11"]

        assert self._executor is not None, "_executor not initialized"

        for code in index_codes:
            try:
                loop = asyncio.get_event_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        lambda c=code: fdr.DataReader(
                            c,
                            start_date.isoformat(),
                            end_date.isoformat(),
                        ),
                    ),
                    timeout=self.config.fdr_timeout,
                )

                if df is not None and not df.empty:
                    df.columns = [c.title() for c in df.columns]
                    logger.debug(f"Successfully fetched index {code}")
                    return df

            except asyncio.TimeoutError:
                logger.debug(f"Timeout fetching index {code}")
                continue
            except Exception as e:
                logger.debug(f"Failed to fetch index {code}: {e}")
                continue

        logger.warning(f"Failed to fetch index {index_code} with all fallback codes")
        return None

    def _fetch_single_history(
        self,
        fdr,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """Fetch history for a single ticker (runs in thread).

        Args:
            fdr: FinanceDataReader module
            ticker: KRX ticker code
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV or None if failed
        """
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

    def _extract_price_from_history(
        self,
        history: HistoryData,
    ) -> PriceData | None:
        """Extract latest price data from history.

        Args:
            history: HistoryData containing OHLCV DataFrame

        Returns:
            PriceData for the most recent day or None
        """
        df = history.data
        if df is None or df.empty:
            return None

        try:
            last_row = df.iloc[-1]
            trading_date = df.index[-1]

            if hasattr(trading_date, "date"):
                date_val = trading_date.date()
            else:
                date_val = date.fromisoformat(str(trading_date)[:10])

            # Calculate change percent if we have previous day
            change_percent = None
            if len(df) > 1:
                prev_close = df.iloc[-2]["Close"]
                if prev_close and prev_close > 0:
                    change_percent = (
                        (float(last_row["Close"]) - float(prev_close)) / float(prev_close)
                    ) * 100

            return PriceData(
                ticker=history.ticker,
                date=date_val,
                open=float(last_row["Open"]),
                high=float(last_row["High"]),
                low=float(last_row["Low"]),
                close=float(last_row["Close"]),
                volume=int(last_row["Volume"]),
                change_percent=change_percent,
            )

        except Exception as e:
            logger.debug(f"Failed to extract price: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
