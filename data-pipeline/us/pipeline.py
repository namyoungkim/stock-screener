"""US stock data collection pipeline.

Rate-limit-aware pipeline optimized for yfinance data source.

Pipeline flow:
1. Fetch prices from yfinance (batch)
2. Fetch history from yfinance (batch)
3. Fetch metrics from yfinance (with circuit breaker)
4. Calculate technical indicators
5. Merge and return results
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from common.indicators import (
    calculate_all_technicals,
    calculate_beta,
    calculate_graham_number,
)
from core.errors import CircuitOpenError, RateLimitError
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

from .config import USConfig
from .resilience import CircuitBreaker, RateLimiter, RetryExecutor
from .sources import YFinanceSource

logger = get_logger(__name__)


@dataclass
class USPipeline:
    """US stock data collection pipeline.

    Optimized for US market characteristics:
    - Rate limiting concerns (yfinance is heavily rate limited)
    - Circuit breaker for cascade failure prevention
    - Resume support for interrupted collections
    """

    config: USConfig = field(default_factory=USConfig)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    # Sources and resilience (initialized lazily)
    _yfinance: YFinanceSource | None = field(default=None, init=False, repr=False)
    _circuit_breaker: CircuitBreaker | None = field(default=None, init=False, repr=False)
    _rate_limiter: RateLimiter | None = field(default=None, init=False, repr=False)
    _retry: RetryExecutor | None = field(default=None, init=False, repr=False)

    @property
    def yfinance(self) -> YFinanceSource:
        """Get yfinance source (lazy initialization)."""
        if self._yfinance is None:
            self._yfinance = YFinanceSource(config=self.config)
        return self._yfinance

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get circuit breaker (lazy initialization)."""
        if self._circuit_breaker is None:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.circuit_failure_threshold,
                recovery_timeout=self.config.circuit_recovery_timeout,
                success_threshold=self.config.circuit_success_threshold,
            )
        return self._circuit_breaker

    @property
    def rate_limiter(self) -> RateLimiter:
        """Get rate limiter (lazy initialization)."""
        if self._rate_limiter is None:
            self._rate_limiter = RateLimiter(
                rate=self.config.rate_limit_per_second,
                burst=self.config.rate_limit_burst,
            )
        return self._rate_limiter

    @property
    def retry(self) -> RetryExecutor:
        """Get retry executor (lazy initialization)."""
        if self._retry is None:
            self._retry = RetryExecutor(
                max_retries=self.config.max_retries,
                base_delay=self.config.retry_base_delay,
                max_delay=self.config.retry_max_delay,
                multiplier=self.config.retry_multiplier,
                jitter=self.config.retry_jitter,
            )
        return self._retry

    async def run(
        self,
        tickers: list[str],
        resume: bool = False,
    ) -> tuple[CollectionResult, list[dict[str, Any]]]:
        """Run the US collection pipeline.

        Args:
            tickers: List of US ticker symbols
            resume: Resume from last checkpoint if True

        Returns:
            Tuple of (CollectionResult, list of merged data dicts)
        """
        result = CollectionResult(
            market=Market.US,
            started_at=datetime.now(),
            total_tickers=len(tickers),
        )

        merged_data: list[dict[str, Any]] = []

        # Resume support
        if resume:
            completed = self._load_progress()
            tickers = [t for t in tickers if t not in completed]
            logger.info(
                f"Resuming collection. {len(completed)} already completed, {len(tickers)} remaining"
            )
            result.total_tickers = len(tickers) + len(completed)

        with log_context(market="us"):
            with self.metrics.collection("us", total=len(tickers)) as m:
                try:
                    # Phase 1: Fetch prices
                    result.phase = CollectionPhase.PRICES
                    logger.info(
                        "Starting price collection",
                        extra={"total_tickers": len(tickers)},
                    )

                    with self.metrics.phase("prices"):
                        price_result = await self.yfinance.fetch_prices(tickers)

                    logger.info(
                        "Price collection completed",
                        extra={
                            "success": price_result.success_count,
                            "failed": price_result.failed_count,
                        },
                    )

                    # Phase 2: Fetch history
                    result.phase = CollectionPhase.HISTORY
                    logger.info("Starting history collection")

                    with self.metrics.phase("history"):
                        history_result = await self.yfinance.fetch_history(tickers)

                    logger.info(
                        "History collection completed",
                        extra={
                            "success": history_result.success_count,
                            "failed": history_result.failed_count,
                        },
                    )

                    # Fetch S&P 500 index for Beta calculation
                    logger.info("Fetching S&P 500 index for Beta calculation")
                    sp500_history = await self.yfinance.fetch_index_history("^GSPC")

                    # Phase 3: Fetch metrics (with circuit breaker)
                    result.phase = CollectionPhase.METRICS
                    logger.info("Starting metrics collection (rate limited)")

                    with self.metrics.phase("metrics"):
                        metrics_result = await self._fetch_metrics_with_resilience(
                            tickers, m
                        )

                    logger.info(
                        "Metrics collection completed",
                        extra={
                            "success": metrics_result.success_count,
                            "failed": metrics_result.failed_count,
                        },
                    )

                    # Check for circuit breaker trip
                    if self.circuit_breaker.is_open:
                        result.circuit_breaker_tripped = True
                        logger.warning("Circuit breaker is open - some metrics may be missing")

                    # Phase 4: Calculate technical indicators
                    result.phase = CollectionPhase.TECHNICALS
                    logger.info("Calculating technical indicators")

                    with self.metrics.phase("technicals"):
                        technicals = self._calculate_technicals(
                            history_result, sp500_history
                        )

                    # Phase 5: Merge all data
                    result.phase = CollectionPhase.SAVE
                    logger.info("Merging data")

                    merged_data = self._merge_all_data(
                        price_result,
                        history_result,
                        metrics_result,
                        technicals,
                    )

                    # Save progress
                    completed_tickers = [d["ticker"] for d in merged_data]
                    self._save_progress(completed_tickers)

                    # Count results
                    result.successful = len(merged_data)
                    result.failed = len(tickers) - result.successful
                    result.phase = CollectionPhase.COMPLETE

                    m.record_success(result.successful)
                    m.record_failure(result.failed)

                    logger.info(
                        "US collection completed",
                        extra={
                            "successful": result.successful,
                            "failed": result.failed,
                            "success_rate": f"{result.success_rate:.1f}%",
                        },
                    )

                except CircuitOpenError as e:
                    result.phase = CollectionPhase.FAILED
                    result.circuit_breaker_tripped = True
                    result.errors.append(str(e))
                    logger.error(f"Circuit breaker open: {e}")
                    raise

                except RateLimitError as e:
                    result.phase = CollectionPhase.FAILED
                    result.rate_limit_hit = True
                    result.errors.append(str(e))
                    logger.error(f"Rate limit hit: {e}")
                    raise

                except Exception as e:
                    result.phase = CollectionPhase.FAILED
                    result.errors.append(str(e))
                    logger.error(f"US collection failed: {e}")
                    raise

                finally:
                    result.ended_at = datetime.now()
                    await self._cleanup()

        return result, merged_data

    async def _fetch_metrics_with_resilience(
        self,
        tickers: list[str],
        metrics_collector: Any,
    ) -> BatchFetchResult[MetricsData]:
        """Fetch metrics with circuit breaker and rate limiter.

        Args:
            tickers: List of tickers
            metrics_collector: Metrics collector for tracking

        Returns:
            BatchFetchResult with metrics
        """
        # Use circuit breaker to wrap metrics fetching
        try:
            async with self.circuit_breaker:
                # Rate limit before making requests
                await self.rate_limiter.acquire(len(tickers))

                # Use retry executor
                result = await self.retry.execute(
                    self.yfinance.fetch_metrics,
                    tickers,
                )

                # Check for rate limit errors in results
                rate_limit_count = sum(
                    1
                    for r in result.failed
                    if isinstance(r.error, RateLimitError)
                )

                if rate_limit_count > 0:
                    metrics_collector.record_rate_limit()
                    logger.warning(
                        f"Rate limit errors in metrics: {rate_limit_count}"
                    )

                return result

        except CircuitOpenError:
            # Circuit is open - return empty result
            metrics_collector.record_circuit_breaker_trip()
            return BatchFetchResult(results=[], source="yfinance")

    def _calculate_technicals(
        self,
        history_result: BatchFetchResult[HistoryData],
        sp500_history: pd.DataFrame | None,
    ) -> dict[str, TechnicalIndicators]:
        """Calculate technical indicators for all tickers.

        Args:
            history_result: History data from yfinance
            sp500_history: S&P 500 index history for Beta calculation

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
                if sp500_history is not None and not sp500_history.empty:
                    beta = calculate_beta(df, sp500_history)

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

                # Store beta temporarily
                technicals[ticker]._beta = beta  # type: ignore

            except Exception as e:
                logger.debug(f"Failed to calculate technicals for {ticker}: {e}")

        return technicals

    def _merge_all_data(
        self,
        price_result: BatchFetchResult[PriceData],
        history_result: BatchFetchResult[HistoryData],
        metrics_result: BatchFetchResult[MetricsData],
        technicals: dict[str, TechnicalIndicators],
    ) -> list[dict[str, Any]]:
        """Merge all data into final output format.

        Args:
            price_result: Price data from yfinance
            history_result: History data from yfinance
            metrics_result: Metrics from yfinance
            technicals: Calculated technical indicators

        Returns:
            List of merged data dicts ready for storage
        """
        merged: list[dict[str, Any]] = []

        # Build lookup dicts
        prices: dict[str, PriceData] = {}
        for result in price_result.succeeded:
            if result.data is not None:
                prices[result.ticker] = result.data

        metrics: dict[str, MetricsData] = {}
        for result in metrics_result.succeeded:
            if result.data is not None:
                metrics[result.ticker] = result.data

        # Merge for each ticker with price data
        for ticker, price in prices.items():
            data: dict[str, Any] = {
                "ticker": ticker,
                "date": price.date.isoformat(),
                "market": "US",
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
                    "forward_pe": m.forward_pe,
                    "pb_ratio": m.pb_ratio,
                    "ps_ratio": m.ps_ratio,
                    "peg_ratio": m.peg_ratio,
                    "ev_ebitda": m.ev_ebitda,
                    "roe": m.roe,
                    "roa": m.roa,
                    "gross_margin": m.gross_margin,
                    "net_margin": m.net_margin,
                    "debt_equity": m.debt_equity,
                    "current_ratio": m.current_ratio,
                    "eps": m.eps,
                    "bps": m.bps,
                    "dividend_yield": m.dividend_yield,
                    "market_cap": m.market_cap,
                    "beta": m.beta,
                    "fifty_two_week_high": m.fifty_two_week_high,
                    "fifty_two_week_low": m.fifty_two_week_low,
                    "ma_50": m.ma_50,
                    "ma_200": m.ma_200,
                })

                # Calculate Graham Number
                graham = calculate_graham_number(m.eps, m.bps)
                data["graham_number"] = graham

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

                # Override beta from technicals if available
                if hasattr(t, "_beta") and t._beta is not None:  # type: ignore
                    data["beta"] = t._beta  # type: ignore

            merged.append(data)

        return merged

    def _load_progress(self) -> set[str]:
        """Load completed tickers from progress file."""
        progress_file = self.config.progress_file
        if not progress_file.exists():
            return set()

        try:
            with open(progress_file) as f:
                return set(line.strip() for line in f if line.strip())
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")
            return set()

    def _save_progress(self, tickers: list[str]) -> None:
        """Save completed tickers to progress file."""
        progress_file = self.config.progress_file

        # Append to existing progress
        existing = self._load_progress()
        all_completed = existing | set(tickers)

        try:
            progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(progress_file, "w") as f:
                for ticker in sorted(all_completed):
                    f.write(f"{ticker}\n")
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")

    def clear_progress(self) -> None:
        """Clear progress file to start fresh."""
        if self.config.progress_file.exists():
            self.config.progress_file.unlink()
            logger.info("Progress file cleared")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._yfinance:
            await self._yfinance.close()


async def collect_us(
    tickers: list[str] | None = None,
    config: USConfig | None = None,
    resume: bool = False,
) -> tuple[CollectionResult, list[dict[str, Any]]]:
    """Convenience function to run US collection.

    Args:
        tickers: List of US ticker symbols (loads from config if None)
        config: Pipeline configuration (uses defaults if None)
        resume: Resume from last checkpoint if True

    Returns:
        Tuple of (CollectionResult, list of merged data dicts)
    """
    import csv

    if config is None:
        config = USConfig()

    if tickers is None:
        # Load tickers from CSV
        tickers = []
        if config.tickers_file.exists():
            with open(config.tickers_file) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ticker = row.get("ticker") or row.get("symbol")
                    if ticker:
                        tickers.append(ticker)

    pipeline = USPipeline(config=config)
    return await pipeline.run(tickers, resume=resume)
