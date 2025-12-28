"""Base collector class for stock data collection.

This module provides the abstract base class that US and KR collectors inherit from.
It handles common functionality like:
- Progress tracking
- Error handling and retry logic
- Resume from failed collections
- Data validation
- Storage to Supabase and CSV
"""

import logging
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

import pandas as pd
from common.config import DATA_DIR
from common.indicators import calculate_all_technicals, calculate_graham_number
from common.logging import CollectionProgress, setup_logger
from common.retry import RetryQueue
from common.storage import StorageManager, get_supabase_client
from processors.validators import MetricsValidator


class BaseCollector(ABC):
    """Abstract base class for stock data collectors."""

    # Subclasses should set these
    MARKET: str = ""  # "US", "KOSPI", "KOSDAQ"
    MARKET_PREFIX: str = ""  # "us" or "kr"
    DATA_SOURCE: str = "yfinance"

    def __init__(
        self,
        save_db: bool = True,
        save_csv: bool = True,
        log_level: int = logging.INFO,
        log_dir: Path | None = None,
    ):
        """
        Initialize the collector.

        Args:
            save_db: Whether to save to Supabase
            save_csv: Whether to save to CSV files
            log_level: Logging level
            log_dir: Directory for log files (optional)
        """
        self.save_db = save_db
        self.save_csv = save_csv

        # Setup logger
        self.logger = setup_logger(
            self.__class__.__name__,
            level=log_level,
            log_dir=log_dir,
        )

        # Initialize components
        self.client = get_supabase_client() if save_db else None
        self.storage = StorageManager(
            client=self.client,
            data_dir=DATA_DIR,
            market_prefix=self.MARKET_PREFIX,
        )
        self.validator = MetricsValidator()
        self.retry_queue = RetryQueue()

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """
        Get list of ticker symbols to collect.

        Returns:
            List of ticker symbols
        """
        pass

    @abstractmethod
    def fetch_stock_info(self, ticker: str) -> dict | None:
        """
        Fetch stock information for a single ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with stock info or None if failed
        """
        pass

    @abstractmethod
    def fetch_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """
        Fetch price data for multiple tickers in batch.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker to price data
        """
        pass

    @abstractmethod
    def fetch_history_bulk(
        self,
        tickers: list[str],
        period: str = "3mo",
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple tickers in bulk.

        Args:
            tickers: List of ticker symbols
            period: Historical period (e.g., "3mo", "1y")

        Returns:
            Dictionary mapping ticker to DataFrame with OHLCV data
        """
        pass

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        batch_size: int = 50,
        is_test: bool = False,
    ) -> dict:
        """
        Main collection method.

        Args:
            tickers: List of tickers to collect (None = use get_tickers())
            resume: If True, skip already collected tickers
            batch_size: Number of tickers per batch
            is_test: If True, append "_test" to CSV filenames

        Returns:
            Dictionary with collection statistics
        """
        # Get tickers if not provided
        if tickers is None:
            tickers = self.get_tickers()
            self.logger.info(f"Found {len(tickers)} tickers to collect")

        # Resume: skip already collected tickers
        if resume:
            completed = self.storage.load_completed_tickers()
            original_count = len(tickers)
            tickers = [t for t in tickers if t not in completed]
            self.logger.info(
                f"Resume mode: Skipping {original_count - len(tickers)} already collected tickers. "
                f"{len(tickers)} remaining."
            )

        if not tickers:
            self.logger.info("No tickers to collect")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        # Phase 1: Fetch prices to validate tickers
        self.logger.info("Phase 1: Fetching prices for all tickers...")
        prices_all = self.fetch_prices_batch(tickers)
        valid_tickers = list(prices_all.keys())
        self.logger.info(
            f"Found {len(valid_tickers)} tickers with valid prices "
            f"(out of {len(tickers)})"
        )

        # Phase 2: Bulk download history for technical indicators
        self.logger.info("Phase 2: Downloading history for technical indicators...")
        history_data = self.fetch_history_bulk(valid_tickers, period="3mo")
        self.logger.info(f"Downloaded history for {len(history_data)} tickers")

        # Phase 3: Fetch stock info and process
        self.logger.info("Phase 3: Fetching stock info and processing...")
        progress = CollectionProgress(
            total=len(valid_tickers),
            logger=self.logger,
            desc="Collecting",
        )

        all_companies: list[dict] = []
        all_metrics: list[dict] = []
        all_prices: list[dict] = []

        for ticker in valid_tickers:
            try:
                # Fetch stock info
                stock_info = self.fetch_stock_info(ticker)
                if not stock_info or not stock_info.get("name"):
                    progress.update(skipped=True)
                    continue

                # Calculate technical indicators
                hist = history_data.get(ticker)
                if hist is not None and not hist.empty:
                    technicals = calculate_all_technicals(hist)
                    stock_info.update(technicals)

                # Calculate Graham Number if we have EPS and BVPS
                eps = stock_info.get("eps")
                bvps = stock_info.get("book_value_per_share")
                if eps and bvps:
                    stock_info["graham_number"] = calculate_graham_number(eps, bvps)

                # Validate metrics
                validated = self.validator.validate(stock_info, ticker)

                # Save to database
                if self.save_db and self.client:
                    company_id = self.storage.upsert_company(
                        ticker=ticker,
                        name=validated.get("name", ""),
                        market=self.MARKET,
                        sector=validated.get("sector"),
                        industry=validated.get("industry"),
                        currency=validated.get("currency", "USD"),
                    )
                    if company_id:
                        self.storage.upsert_metrics(
                            company_id=company_id,
                            metrics=validated,
                            data_source=self.DATA_SOURCE,
                        )
                        if ticker in prices_all:
                            self.storage.upsert_price(
                                company_id=company_id,
                                price_data=prices_all[ticker],
                                market_cap=validated.get("market_cap"),
                            )

                # Collect for CSV
                if self.save_csv:
                    all_companies.append(self._build_company_record(ticker, validated))
                    all_metrics.append(self._build_metrics_record(ticker, validated))
                    if ticker in prices_all:
                        all_prices.append(
                            self._build_price_record(ticker, prices_all[ticker], validated)
                        )

                progress.update(success=True)

            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                self.retry_queue.add_failed(ticker, str(e))
                progress.update(success=False)

            progress.log_progress(interval=100)

        # Save to CSV
        if self.save_csv:
            self.storage.save_to_csv(
                companies=all_companies,
                metrics=all_metrics,
                prices=all_prices,
                is_test=is_test,
            )

        # Log summary
        progress.log_summary()

        # Log validation summary
        validation_summary = self.validator.get_summary()
        if validation_summary["with_warnings"] > 0:
            self.logger.warning(f"Validation summary: {validation_summary}")

        # Save failed items
        if self.retry_queue.count > 0:
            failed_file = DATA_DIR / f"{self.MARKET_PREFIX}_failed_tickers.json"
            self.retry_queue.save_path = failed_file
            self.retry_queue.save_to_file()

        return progress.get_stats()

    def _build_company_record(self, ticker: str, data: dict) -> dict:
        """Build company record for CSV."""
        return {
            "ticker": ticker,
            "name": data.get("name"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "currency": data.get("currency", "USD"),
        }

    def _build_metrics_record(self, ticker: str, data: dict) -> dict:
        """Build metrics record for CSV."""
        today = date.today().isoformat()
        return {
            "ticker": ticker,
            "date": today,
            "pe_ratio": data.get("pe_ratio"),
            "pb_ratio": data.get("pb_ratio"),
            "ps_ratio": data.get("ps_ratio"),
            "ev_ebitda": data.get("ev_ebitda"),
            "roe": data.get("roe"),
            "roa": data.get("roa"),
            "debt_equity": data.get("debt_equity"),
            "current_ratio": data.get("current_ratio"),
            "gross_margin": data.get("gross_margin"),
            "net_margin": data.get("net_margin"),
            "dividend_yield": data.get("dividend_yield"),
            "eps": data.get("eps"),
            "book_value_per_share": data.get("book_value_per_share"),
            "graham_number": data.get("graham_number"),
            "fifty_two_week_high": data.get("fifty_two_week_high"),
            "fifty_two_week_low": data.get("fifty_two_week_low"),
            "fifty_day_average": data.get("fifty_day_average"),
            "two_hundred_day_average": data.get("two_hundred_day_average"),
            "peg_ratio": data.get("peg_ratio"),
            "beta": data.get("beta"),
            "rsi": data.get("rsi"),
            "volume_change": data.get("volume_change"),
            "macd": data.get("macd"),
            "macd_signal": data.get("macd_signal"),
            "macd_histogram": data.get("macd_histogram"),
            "bb_upper": data.get("bb_upper"),
            "bb_middle": data.get("bb_middle"),
            "bb_lower": data.get("bb_lower"),
            "bb_percent": data.get("bb_percent"),
            "mfi": data.get("mfi"),
        }

    def _build_price_record(
        self,
        ticker: str,
        price_data: dict,
        stock_data: dict,
    ) -> dict:
        """Build price record for CSV."""
        return {
            "ticker": ticker,
            "date": price_data.get("date", date.today().isoformat()),
            "open": price_data.get("open"),
            "high": price_data.get("high"),
            "low": price_data.get("low"),
            "close": price_data.get("close"),
            "volume": price_data.get("volume"),
            "market_cap": stock_data.get("market_cap"),
        }
