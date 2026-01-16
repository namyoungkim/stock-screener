"""KR (Korea) stock data collection pipeline.

Simple pipeline optimized for FDR + Naver + KIS data sources.
No complex rate limiting needed - focus on timeout management.

Pipeline flow:
1. Fetch prices/history from FDR
2. Fetch metrics from KIS (primary) or Naver (fallback)
3. Calculate technical indicators (RSI, MACD, BB, etc.)
4. Calculate Beta using KOSPI index
5. Merge and return results
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

from common.indicators import (
    calculate_all_technicals,
    calculate_beta,
    calculate_graham_number,
    calculate_moving_averages,
)
from core.types import (
    BatchFetchResult,
    CollectionPhase,
    CollectionResult,
    HistoryData,
    Market,
    MetricsData,
    PriceData,
    TechnicalIndicators,
)
from observability.logger import get_logger, log_context
from observability.metrics import MetricsCollector

from .config import KRConfig
from .sources import FDRSource, KISSource, NaverSource

logger = get_logger(__name__)


@dataclass
class KRPipeline:
    """KR stock data collection pipeline.

    Optimized for Korean market characteristics:
    - No rate limiting concerns (FDR, Naver, KIS are forgiving)
    - Focus on timeout management
    - Simple sequential processing
    """

    config: KRConfig = field(default_factory=KRConfig)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    # Sources (initialized lazily)
    _fdr: FDRSource | None = field(default=None, init=False, repr=False)
    _kis: KISSource | None = field(default=None, init=False, repr=False)
    _naver: NaverSource | None = field(default=None, init=False, repr=False)

    @property
    def fdr(self) -> FDRSource:
        """Get FDR source (lazy initialization)."""
        if self._fdr is None:
            self._fdr = FDRSource(config=self.config)
        return self._fdr

    @property
    def kis(self) -> KISSource:
        """Get KIS source (lazy initialization)."""
        if self._kis is None:
            self._kis = KISSource(config=self.config)
        return self._kis

    @property
    def naver(self) -> NaverSource:
        """Get Naver source (lazy initialization)."""
        if self._naver is None:
            self._naver = NaverSource(config=self.config)
        return self._naver

    async def run(
        self,
        tickers: list[str],
    ) -> tuple[CollectionResult, list[dict[str, Any]]]:
        """Run the KR collection pipeline.

        Args:
            tickers: List of KRX ticker codes

        Returns:
            Tuple of (CollectionResult, list of merged data dicts)
        """
        result = CollectionResult(
            market=Market.KR,
            started_at=datetime.now(),
            total_tickers=len(tickers),
        )

        merged_data: list[dict[str, Any]] = []

        with log_context(market="kr"):
            with self.metrics.collection("kr", total=len(tickers)) as m:
                try:
                    # Phase 1: Fetch history from FDR
                    result.phase = CollectionPhase.HISTORY
                    logger.info(
                        "Starting history collection",
                        extra={"total_tickers": len(tickers)},
                    )

                    with self.metrics.phase("history"):
                        history_result = await self.fdr.fetch_history(tickers)

                    logger.info(
                        "History collection completed",
                        extra={
                            "success": history_result.success_count,
                            "failed": history_result.failed_count,
                        },
                    )

                    # Phase 2: Fetch index for Beta calculation
                    logger.info("Fetching KOSPI index for Beta calculation")
                    kospi_history = await self.fdr.fetch_index_history("KS11")

                    # Phase 3: Fetch metrics from KIS (primary) or Naver (fallback)
                    result.phase = CollectionPhase.METRICS
                    logger.info("Starting metrics collection")

                    with self.metrics.phase("metrics"):
                        if self.kis.is_available:
                            logger.info("Using KIS API for metrics (primary)")
                            metrics_result = await self.kis.fetch_metrics(tickers)

                            # Fallback to Naver for failed tickers
                            failed_tickers = [r.ticker for r in metrics_result.failed]
                            if failed_tickers:
                                logger.info(
                                    f"Falling back to Naver for {len(failed_tickers)} tickers"
                                )
                                naver_result = await self.naver.fetch_metrics(failed_tickers)

                                # Merge results
                                metrics_result = self._merge_metrics_results(
                                    metrics_result, naver_result
                                )
                        else:
                            logger.info("KIS API not available, using Naver only")
                            metrics_result = await self.naver.fetch_metrics(tickers)

                    logger.info(
                        "Metrics collection completed",
                        extra={
                            "success": metrics_result.success_count,
                            "failed": metrics_result.failed_count,
                        },
                    )

                    # Phase 4: Calculate technical indicators
                    result.phase = CollectionPhase.TECHNICALS
                    logger.info("Calculating technical indicators")

                    with self.metrics.phase("technicals"):
                        technicals = self._calculate_technicals(
                            history_result, kospi_history
                        )

                    # Phase 5: Merge all data
                    result.phase = CollectionPhase.SAVE
                    logger.info("Merging data")

                    merged_data = self._merge_all_data(
                        history_result,
                        metrics_result,
                        technicals,
                    )

                    # Count results
                    result.successful = len(merged_data)
                    result.failed = len(tickers) - result.successful
                    result.phase = CollectionPhase.COMPLETE

                    m.record_success(result.successful)
                    m.record_failure(result.failed)

                    logger.info(
                        "KR collection completed",
                        extra={
                            "successful": result.successful,
                            "failed": result.failed,
                            "success_rate": f"{result.success_rate:.1f}%",
                        },
                    )

                except Exception as e:
                    result.phase = CollectionPhase.FAILED
                    result.errors.append(str(e))
                    logger.error(f"KR collection failed: {e}")
                    raise

                finally:
                    result.ended_at = datetime.now()
                    await self._cleanup()

        return result, merged_data

    def _merge_metrics_results(
        self,
        primary: BatchFetchResult[MetricsData],
        fallback: BatchFetchResult[MetricsData],
    ) -> BatchFetchResult[MetricsData]:
        """Merge primary and fallback metrics results.

        Args:
            primary: Primary metrics result (e.g., from KIS)
            fallback: Fallback metrics result (e.g., from Naver)

        Returns:
            Merged BatchFetchResult
        """
        # Create a dict of successful results from primary
        merged_results = list(primary.succeeded)
        merged_tickers = {r.ticker for r in merged_results}

        # Add successful results from fallback (for tickers not in primary)
        for result in fallback.succeeded:
            if result.ticker not in merged_tickers:
                merged_results.append(result)
                merged_tickers.add(result.ticker)

        # Add failed results (only for tickers not in either succeeded set)
        for result in primary.failed:
            if result.ticker not in merged_tickers:
                # Check if fallback has this ticker
                fallback_result = next(
                    (r for r in fallback.results if r.ticker == result.ticker), None
                )
                if fallback_result and fallback_result.is_success:
                    merged_results.append(fallback_result)
                else:
                    merged_results.append(result)

        return BatchFetchResult(
            results=merged_results,
            total_latency_ms=primary.total_latency_ms + fallback.total_latency_ms,
            source="kis+naver",
        )

    def _calculate_technicals(
        self,
        history_result: BatchFetchResult[HistoryData],
        kospi_history: pd.DataFrame | None,
    ) -> dict[str, TechnicalIndicators]:
        """Calculate technical indicators for all tickers.

        Args:
            history_result: History data from FDR
            kospi_history: KOSPI index history for Beta calculation

        Returns:
            Dict mapping ticker to TechnicalIndicators
        """
        technicals: dict[str, TechnicalIndicators] = {}

        for result in history_result.succeeded:
            if result.data is None:
                continue

            ticker = result.ticker
            df = result.data.data

            try:
                # Calculate all technicals
                tech_dict = calculate_all_technicals(df)

                # Calculate Beta
                beta = None
                if kospi_history is not None and not kospi_history.empty:
                    beta = calculate_beta(df, kospi_history)

                # Get trading date from history
                trading_date = date.today()
                if not df.empty and hasattr(df.index[-1], "date"):
                    trading_date = df.index[-1].date()

                technicals[ticker] = TechnicalIndicators(
                    ticker=ticker,
                    date=trading_date,
                    rsi=tech_dict.get("rsi"),
                    mfi=tech_dict.get("mfi"),
                    macd=tech_dict.get("macd"),
                    macd_signal=tech_dict.get("macd_signal"),
                    macd_histogram=tech_dict.get("macd_histogram"),
                    bb_upper=tech_dict.get("bb_upper"),
                    bb_middle=tech_dict.get("bb_middle"),
                    bb_lower=tech_dict.get("bb_lower"),
                    bb_percent=tech_dict.get("bb_percent"),
                    volume_change=tech_dict.get("volume_change"),
                )

                # Store beta in metrics later (not in technicals)
                technicals[ticker]._beta = beta  # type: ignore

            except Exception as e:
                logger.debug(f"Failed to calculate technicals for {ticker}: {e}")

        return technicals

    def _merge_all_data(
        self,
        history_result: BatchFetchResult[HistoryData],
        metrics_result: BatchFetchResult[MetricsData],
        technicals: dict[str, TechnicalIndicators],
    ) -> list[dict[str, Any]]:
        """Merge all data into final output format.

        Args:
            history_result: History/price data from FDR
            metrics_result: Metrics from KIS/Naver
            technicals: Calculated technical indicators

        Returns:
            List of merged data dicts ready for storage
        """
        merged: list[dict[str, Any]] = []

        # Build lookup dicts
        prices: dict[str, PriceData] = {}
        for result in history_result.succeeded:
            if result.data is not None:
                df = result.data.data
                if not df.empty:
                    # Extract latest price
                    price = self._extract_price(result.ticker, df)
                    if price:
                        prices[result.ticker] = price

        metrics: dict[str, MetricsData] = {}
        for result in metrics_result.succeeded:
            if result.data is not None:
                metrics[result.ticker] = result.data

        # Calculate moving averages from history
        ma_data: dict[str, tuple[float | None, float | None]] = {}
        for result in history_result.succeeded:
            if result.data is not None:
                ma_50, ma_200 = calculate_moving_averages(result.data.data)
                ma_data[result.ticker] = (ma_50, ma_200)

        # Calculate 52-week high/low from history
        week52_data: dict[str, tuple[float | None, float | None]] = {}
        for result in history_result.succeeded:
            if result.data is not None:
                df = result.data.data
                if not df.empty and len(df) > 0:
                    # Use last 252 trading days (approximately 1 year)
                    year_data = df.tail(252)
                    high_52w = float(year_data["High"].max()) if "High" in year_data else None
                    low_52w = float(year_data["Low"].min()) if "Low" in year_data else None
                    week52_data[result.ticker] = (high_52w, low_52w)

        # Merge for each ticker with price data
        for ticker, price in prices.items():
            data: dict[str, Any] = {
                "ticker": ticker,
                "date": price.date.isoformat(),
                "market": "KR",
                # Price data
                "latest_price": price.close,
                "open": price.open,
                "high": price.high,
                "low": price.low,
                "volume": price.volume,
                "change_percent": price.change_percent,
            }

            # Add metrics
            if ticker in metrics:
                m = metrics[ticker]
                data.update({
                    "pe_ratio": m.pe_ratio,
                    "pb_ratio": m.pb_ratio,
                    "eps": m.eps,
                    "bps": m.bps,
                    "roe": m.roe,
                    "roa": m.roa,
                    "gross_margin": m.gross_margin,
                    "net_margin": m.net_margin,
                    "debt_equity": m.debt_equity,
                    "current_ratio": m.current_ratio,
                    "dividend_yield": m.dividend_yield,
                    "market_cap": m.market_cap,
                })

                # Calculate Graham Number
                graham = calculate_graham_number(m.eps, m.bps)
                data["graham_number"] = graham

            # Add 52-week high/low from history (prioritize calculated values)
            if ticker in week52_data:
                high_52w, low_52w = week52_data[ticker]
                data["fifty_two_week_high"] = high_52w
                data["fifty_two_week_low"] = low_52w

            # Add moving averages
            if ticker in ma_data:
                ma_50, ma_200 = ma_data[ticker]
                data["ma_50"] = ma_50
                data["ma_200"] = ma_200

            # Add technicals
            if ticker in technicals:
                t = technicals[ticker]
                data.update({
                    "rsi": t.rsi,
                    "mfi": t.mfi,
                    "macd": t.macd,
                    "macd_signal": t.macd_signal,
                    "macd_histogram": t.macd_histogram,
                    "bb_upper": t.bb_upper,
                    "bb_middle": t.bb_middle,
                    "bb_lower": t.bb_lower,
                    "bb_percent": t.bb_percent,
                    "volume_change": t.volume_change,
                })

                # Add beta (stored on technicals temporarily)
                if hasattr(t, "_beta"):
                    data["beta"] = t._beta  # type: ignore

            merged.append(data)

        return merged

    def _extract_price(self, ticker: str, df: pd.DataFrame) -> PriceData | None:
        """Extract latest price from history DataFrame."""
        if df.empty:
            return None

        try:
            last_row = df.iloc[-1]
            trading_date = df.index[-1]

            if hasattr(trading_date, "date"):
                date_val = trading_date.date()
            else:
                date_val = date.fromisoformat(str(trading_date)[:10])

            # Calculate change percent
            change_percent = None
            if len(df) > 1:
                prev_close = df.iloc[-2]["Close"]
                if prev_close and prev_close > 0:
                    change_percent = (
                        (float(last_row["Close"]) - float(prev_close))
                        / float(prev_close)
                    ) * 100

            return PriceData(
                ticker=ticker,
                date=date_val,
                open=float(last_row["Open"]),
                high=float(last_row["High"]),
                low=float(last_row["Low"]),
                close=float(last_row["Close"]),
                volume=int(last_row["Volume"]),
                change_percent=change_percent,
            )

        except Exception as e:
            logger.debug(f"Failed to extract price for {ticker}: {e}")
            return None

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._fdr:
            await self._fdr.close()
        if self._kis:
            await self._kis.close()
        if self._naver:
            await self._naver.close()


async def collect_kr(
    tickers: list[str] | None = None,
    config: KRConfig | None = None,
) -> tuple[CollectionResult, list[dict[str, Any]]]:
    """Convenience function to run KR collection.

    Args:
        tickers: List of KRX ticker codes (loads from config if None)
        config: Pipeline configuration (uses defaults if None)

    Returns:
        Tuple of (CollectionResult, list of merged data dicts)
    """
    import csv

    if config is None:
        config = KRConfig()

    if tickers is None:
        # Load tickers from CSV
        tickers = []
        if config.tickers_file.exists():
            with open(config.tickers_file) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ticker = row.get("ticker") or row.get("code")
                    if ticker:
                        tickers.append(ticker)

    pipeline = KRPipeline(config=config)
    return await pipeline.run(tickers)
