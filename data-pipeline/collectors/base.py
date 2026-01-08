"""Base collector with template method pattern."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

import pandas as pd

from config import Settings, get_settings
from processors.validators import MetricsValidator
from rate_limit import (
    AdaptiveRateLimitStrategy,
    BatchResult,
    ProgressTracker,
    RateLimitStrategy,
)
from sources import DataSource, FetchResult
from storage import CSVStorage, Storage

logger = logging.getLogger(__name__)


class CollectionPhase(Enum):
    """Phases of the collection process."""

    INIT = "init"
    FETCH_PRICES = "fetch_prices"
    FETCH_HISTORY = "fetch_history"
    FETCH_METRICS = "fetch_metrics"
    CALCULATE_TECHNICALS = "calculate_technicals"
    VALIDATE = "validate"
    SAVE = "save"
    QUALITY_CHECK = "quality_check"
    COMPLETE = "complete"


@dataclass
class CollectionResult:
    """Result of a collection operation."""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    missing_tickers: list[str] = field(default_factory=list)
    phase: CollectionPhase = CollectionPhase.COMPLETE
    errors: list[str] = field(default_factory=list)
    rate_limit_hit: bool = False

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100

    @property
    def is_complete(self) -> bool:
        """Check if collection completed successfully."""
        return self.phase == CollectionPhase.COMPLETE and not self.rate_limit_hit


class BaseCollector(ABC):
    """Base collector with template method pattern.

    This class provides the common collection workflow that all collectors follow.
    Subclasses implement the abstract methods to provide market-specific logic.

    The collection workflow (template method):
    1. get_tickers() - Get ticker universe
    2. fetch_prices_phase() - Fetch latest prices (determines valid tickers)
    3. fetch_history_phase() - Fetch OHLCV history
    4. fetch_metrics_phase() - Fetch fundamental metrics
    5. calculate_technicals_phase() - Calculate technical indicators
    6. validate_phase() - Validate and clean data
    7. save_phase() - Save to storage
    8. quality_check_phase() - Check data quality
    """

    def __init__(
        self,
        market: str,
        data_source: DataSource,
        storage: Storage,
        rate_limit_strategy: RateLimitStrategy | None = None,
        validator: MetricsValidator | None = None,
        settings: Settings | None = None,
        quiet: bool = False,
    ):
        """Initialize collector.

        Args:
            market: Market identifier ('US' or 'KR')
            data_source: Data source for fetching data
            storage: Storage backend for saving data
            rate_limit_strategy: Strategy for handling rate limits
            validator: Metrics validator for data validation
            settings: Application settings
            quiet: Suppress progress output
        """
        self.market = market.upper()
        self.source = data_source
        self.storage = storage
        self.rate_limit = rate_limit_strategy or AdaptiveRateLimitStrategy()
        self.validator = validator or MetricsValidator()
        self.settings = settings or get_settings()
        self.quiet = quiet

        self.logger = logging.getLogger(f"{__name__}.{self.market}")

        # Progress tracking
        self._progress_tracker: ProgressTracker | None = None

    @property
    def progress_tracker(self) -> ProgressTracker:
        """Lazy initialization of progress tracker."""
        if self._progress_tracker is None:
            self._progress_tracker = ProgressTracker(
                market=self.market,
                data_dir=self.settings.data_dir,
            )
        return self._progress_tracker

    # ==================== Abstract Methods ====================
    # These must be implemented by subclasses

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Get ticker universe for this market.

        Returns:
            List of ticker symbols to collect
        """
        ...

    @abstractmethod
    async def fetch_prices_phase(
        self, tickers: list[str]
    ) -> tuple[dict[str, dict], list[str]]:
        """Fetch latest prices for tickers.

        Args:
            tickers: List of tickers to fetch

        Returns:
            Tuple of (prices dict, valid tickers list)
            - prices: {ticker: {close, open, high, low, volume, date}}
            - valid_tickers: tickers that have valid price data
        """
        ...

    @abstractmethod
    async def fetch_metrics_phase(
        self,
        tickers: list[str],
        history: dict[str, pd.DataFrame],
    ) -> dict[str, dict]:
        """Fetch fundamental metrics for tickers.

        Args:
            tickers: List of tickers to fetch
            history: OHLCV history (may be used for some metrics)

        Returns:
            Dict mapping ticker to metrics dict
        """
        ...

    @abstractmethod
    def build_company_record(self, ticker: str, data: dict) -> dict:
        """Build company record from collected data.

        Args:
            ticker: Ticker symbol
            data: Collected data for the ticker

        Returns:
            Company record dict for storage
        """
        ...

    @abstractmethod
    def build_metrics_record(
        self,
        ticker: str,
        metrics: dict,
        technicals: dict,
        price_data: dict,
    ) -> dict:
        """Build metrics record from collected data.

        Args:
            ticker: Ticker symbol
            metrics: Fundamental metrics
            technicals: Technical indicators
            price_data: Price data

        Returns:
            Metrics record dict for storage
        """
        ...

    @abstractmethod
    def build_price_record(self, ticker: str, price_data: dict) -> dict:
        """Build price record from collected data.

        Args:
            ticker: Ticker symbol
            price_data: Price data

        Returns:
            Price record dict for storage
        """
        ...

    # ==================== Common Methods ====================
    # These provide default implementations that can be overridden

    async def fetch_history_phase(
        self, tickers: list[str]
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV history for tickers.

        Default implementation uses the data source's fetch_history method.
        Override if market-specific logic is needed.

        Args:
            tickers: List of tickers to fetch

        Returns:
            Dict mapping ticker to DataFrame with OHLCV data
        """
        result = await self.source.fetch_history(tickers)
        return {
            ticker: data.history
            for ticker, data in result.succeeded.items()
            if data.history is not None
        }

    def calculate_technicals_phase(
        self, history: dict[str, pd.DataFrame]
    ) -> dict[str, dict]:
        """Calculate technical indicators from history.

        Default implementation calculates RSI, MACD, Bollinger Bands, etc.

        Args:
            history: OHLCV history for each ticker

        Returns:
            Dict mapping ticker to technical indicators dict
        """
        from common.indicators import (
            calculate_beta,
            calculate_bollinger_bands,
            calculate_macd,
            calculate_mfi,
            calculate_moving_averages,
            calculate_rsi,
            calculate_volume_change,
        )

        technicals = {}
        for ticker, df in history.items():
            if df is None or df.empty:
                continue

            try:
                tech = {}

                # RSI
                rsi = calculate_rsi(df)
                if rsi is not None:
                    tech["rsi"] = rsi

                # MFI
                mfi = calculate_mfi(df)
                if mfi is not None:
                    tech["mfi"] = mfi

                # MACD
                macd_data = calculate_macd(df)
                if macd_data:
                    tech.update(macd_data)

                # Bollinger Bands
                bb_data = calculate_bollinger_bands(df)
                if bb_data:
                    tech.update(bb_data)

                # Volume Change
                vol_change = calculate_volume_change(df)
                if vol_change is not None:
                    tech["volume_change"] = vol_change

                # Moving Averages (returns tuple)
                ma_short, ma_long = calculate_moving_averages(df)
                if ma_short is not None:
                    tech["fifty_day_average"] = ma_short
                if ma_long is not None:
                    tech["two_hundred_day_average"] = ma_long

                technicals[ticker] = tech

            except Exception as e:
                self.logger.warning(f"Failed to calculate technicals for {ticker}: {e}")

        return technicals

    def validate_phase(self, metrics: dict[str, dict]) -> dict[str, dict]:
        """Validate metrics and filter invalid values.

        Args:
            metrics: Raw metrics dict

        Returns:
            Validated metrics dict
        """
        validated = {}
        for ticker, data in metrics.items():
            result = self.validator.validate(data, ticker)
            validated[ticker] = result
        return validated

    # ==================== Template Method ====================

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        auto_retry: bool = True,
        max_retry_missing: int = 100,
    ) -> CollectionResult:
        """Main collection workflow (template method).

        This is the entry point for collection. It orchestrates the phases
        defined by the abstract and common methods.

        Args:
            tickers: Optional specific tickers to collect (defaults to full universe)
            resume: Resume from previous progress
            auto_retry: Automatically retry missing tickers
            max_retry_missing: Max missing tickers for auto-retry

        Returns:
            CollectionResult with collection statistics
        """
        return asyncio.run(
            self._collect_async(
                tickers=tickers,
                resume=resume,
                auto_retry=auto_retry,
                max_retry_missing=max_retry_missing,
            )
        )

    async def _collect_async(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        auto_retry: bool = True,
        max_retry_missing: int = 100,
    ) -> CollectionResult:
        """Async implementation of collect."""
        result = CollectionResult()

        try:
            # Phase 0: Get tickers
            self._log_phase(CollectionPhase.INIT)
            all_tickers = tickers or self.get_tickers()
            result.total = len(all_tickers)

            if resume:
                remaining = self.progress_tracker.get_remaining(all_tickers)
                self.logger.info(
                    f"Resuming: {len(remaining)}/{len(all_tickers)} remaining"
                )
                all_tickers = remaining

            if not all_tickers:
                self.logger.info("No tickers to collect")
                return result

            # Phase 1: Fetch prices
            self._log_phase(CollectionPhase.FETCH_PRICES)
            prices, valid_tickers = await self.fetch_prices_phase(all_tickers)
            self.logger.info(f"Valid tickers after price fetch: {len(valid_tickers)}")

            if not valid_tickers:
                self.logger.warning("No valid tickers after price fetch")
                result.missing_tickers = all_tickers
                return result

            # Phase 2: Fetch history
            self._log_phase(CollectionPhase.FETCH_HISTORY)
            history = await self.fetch_history_phase(valid_tickers)
            self.logger.info(f"History fetched for {len(history)} tickers")

            # Phase 3: Fetch metrics
            self._log_phase(CollectionPhase.FETCH_METRICS)
            metrics = await self.fetch_metrics_phase(valid_tickers, history)
            self.logger.info(f"Metrics fetched for {len(metrics)} tickers")

            # Phase 4: Calculate technicals
            self._log_phase(CollectionPhase.CALCULATE_TECHNICALS)
            technicals = self.calculate_technicals_phase(history)
            self.logger.info(f"Technicals calculated for {len(technicals)} tickers")

            # Phase 5: Validate
            self._log_phase(CollectionPhase.VALIDATE)
            validated_metrics = self.validate_phase(metrics)

            # Phase 6: Save
            self._log_phase(CollectionPhase.SAVE)
            save_result = await self._save_all(
                valid_tickers, prices, validated_metrics, technicals
            )
            result.success = save_result["saved"]
            result.failed = save_result["failed"]

            # Mark completed
            self.progress_tracker.mark_batch_completed(valid_tickers)
            self.progress_tracker.save()

            # Phase 7: Quality check
            self._log_phase(CollectionPhase.QUALITY_CHECK)
            result.missing_tickers = self._check_quality(all_tickers, valid_tickers)

            # Auto-retry missing tickers
            if auto_retry and 0 < len(result.missing_tickers) <= max_retry_missing:
                self.logger.info(
                    f"Auto-retrying {len(result.missing_tickers)} missing tickers"
                )
                retry_result = await self._collect_async(
                    tickers=result.missing_tickers,
                    resume=False,
                    auto_retry=False,
                )
                result.success += retry_result.success
                result.missing_tickers = retry_result.missing_tickers

            result.phase = CollectionPhase.COMPLETE

        except Exception as e:
            self.logger.error(f"Collection failed: {e}", exc_info=True)
            result.errors.append(str(e))
            if "rate limit" in str(e).lower():
                result.rate_limit_hit = True

        return result

    def _extract_trading_date(self, prices: dict[str, dict]) -> str | None:
        """Extract trading date from prices data.

        Args:
            prices: Dict mapping ticker to price data

        Returns:
            Trading date string (YYYY-MM-DD) or None if not found
        """
        for ticker, price_data in prices.items():
            if price_data and "date" in price_data:
                return price_data["date"]
        return None

    async def _save_all(
        self,
        tickers: list[str],
        prices: dict[str, dict],
        metrics: dict[str, dict],
        technicals: dict[str, dict],
    ) -> dict[str, int]:
        """Save all collected data."""
        # Set trading date for CSV storage before saving
        # This ensures directory is named by trading date, not collection date
        if isinstance(self.storage, CSVStorage):
            trading_date = self._extract_trading_date(prices)
            if trading_date:
                self.storage.set_trading_date(self.market, trading_date)
            else:
                self.logger.warning(
                    "Could not extract trading date from prices, "
                    "using today's date as fallback"
                )

        companies = []
        metrics_records = []
        price_records = []

        for ticker in tickers:
            price_data = prices.get(ticker, {})
            metric_data = metrics.get(ticker, {})
            tech_data = technicals.get(ticker, {})

            # Build records
            company = self.build_company_record(ticker, {**metric_data, **price_data})
            companies.append(company)

            metrics_rec = self.build_metrics_record(
                ticker, metric_data, tech_data, price_data
            )
            metrics_records.append(metrics_rec)

            price_rec = self.build_price_record(ticker, price_data)
            if price_rec:
                price_records.append(price_rec)

        # Save to storage
        saved = 0
        failed = 0

        result = self.storage.save_companies(companies, self.market)
        saved += result.saved
        failed += len(result.errors)

        result = self.storage.save_metrics(metrics_records, self.market)
        saved += result.saved
        failed += len(result.errors)

        result = self.storage.save_prices(price_records, self.market)
        saved += result.saved
        failed += len(result.errors)

        # Finalize CSV storage (update symlinks)
        if isinstance(self.storage, CSVStorage):
            self.storage.finalize(self.market)

        return {"saved": saved, "failed": failed}

    def _check_quality(
        self, all_tickers: list[str], collected_tickers: list[str]
    ) -> list[str]:
        """Check quality and return missing tickers."""
        collected_set = set(collected_tickers)
        missing = [t for t in all_tickers if t not in collected_set]
        coverage = len(collected_tickers) / len(all_tickers) * 100

        self.logger.info(f"Coverage: {coverage:.1f}% ({len(collected_tickers)}/{len(all_tickers)})")
        if missing:
            self.logger.info(f"Missing {len(missing)} tickers")

        return missing

    def _log_phase(self, phase: CollectionPhase) -> None:
        """Log phase transition."""
        if not self.quiet:
            self.logger.info(f"=== Phase: {phase.value} ===")
