"""US stock collector using new architecture.

This is the new implementation using BaseCollector pattern.
Target: < 300 lines (vs 1,270 lines in legacy us_stocks.py)
"""

import ftplib
import io
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from config import Settings, get_settings
from processors.validators import MetricsValidator
from rate_limit import RateLimitStrategy
from sources import YFinanceSource, FetchResult
from storage import Storage, CSVStorage

from .base import BaseCollector

logger = logging.getLogger(__name__)


# NASDAQ FTP for full universe
NASDAQ_FTP_HOST = "ftp.nasdaqtrader.com"
NASDAQ_FTP_DIR = "symboldirectory"


def get_all_us_tickers() -> dict[str, list[str]]:
    """Fetch all US tickers from NASDAQ FTP.

    Returns:
        Dict mapping ticker to list of index memberships (empty for most)
    """
    tickers = {}

    try:
        ftp = ftplib.FTP(NASDAQ_FTP_HOST, timeout=30)
        ftp.login()
        ftp.cwd(NASDAQ_FTP_DIR)

        # Fetch NASDAQ-listed symbols
        nasdaq_data = io.BytesIO()
        ftp.retrbinary("RETR nasdaqlisted.txt", nasdaq_data.write)
        nasdaq_data.seek(0)

        for line in nasdaq_data.read().decode("utf-8").splitlines()[1:]:
            if "|" in line:
                parts = line.split("|")
                ticker = parts[0].strip()
                if ticker and not ticker.startswith("File"):
                    # Skip test symbols
                    if parts[6].strip() == "Y":  # Test Issue
                        continue
                    tickers[ticker] = []

        # Fetch other-listed symbols (NYSE, etc.)
        other_data = io.BytesIO()
        ftp.retrbinary("RETR otherlisted.txt", other_data.write)
        other_data.seek(0)

        for line in other_data.read().decode("utf-8").splitlines()[1:]:
            if "|" in line:
                parts = line.split("|")
                ticker = parts[0].strip()
                if ticker and not ticker.startswith("File"):
                    # Skip test symbols
                    if parts[5].strip() == "Y":  # Test Issue
                        continue
                    tickers[ticker] = []

        ftp.quit()
        logger.info(f"Loaded {len(tickers)} US tickers from NASDAQ FTP")

    except Exception as e:
        logger.error(f"Failed to fetch tickers from NASDAQ FTP: {e}")

    return tickers


@dataclass
class NewUSCollector(BaseCollector):
    """US stock collector.

    Uses YFinanceSource for all data fetching.
    Inherits common workflow from BaseCollector.
    """

    def __init__(
        self,
        storage: Storage | None = None,
        rate_limit_strategy: RateLimitStrategy | None = None,
        validator: MetricsValidator | None = None,
        settings: Settings | None = None,
        quiet: bool = False,
        save_db: bool = True,
        save_csv: bool = True,
    ):
        """Initialize US collector.

        Args:
            storage: Storage backend (default: CSV or Composite based on flags)
            rate_limit_strategy: Rate limit handling strategy
            validator: Metrics validator
            settings: Application settings
            quiet: Suppress progress output
            save_db: Save to Supabase
            save_csv: Save to CSV
        """
        settings = settings or get_settings()

        # Create storage if not provided
        if storage is None:
            from storage import CSVStorage, SupabaseStorage, CompositeStorage

            storages = []
            if save_csv:
                storages.append(CSVStorage(data_dir=settings.data_dir))
            if save_db and settings.has_supabase:
                storages.append(SupabaseStorage(
                    supabase_url=settings.supabase_url,
                    supabase_key=settings.supabase_key,
                ))
            storage = CompositeStorage(storages=storages) if len(storages) > 1 else storages[0]

        # Create data source
        data_source = YFinanceSource(
            batch_size=settings.batch_size,
            base_delay=settings.base_delay,
        )

        super().__init__(
            market="US",
            data_source=data_source,
            storage=storage,
            rate_limit_strategy=rate_limit_strategy,
            validator=validator,
            settings=settings,
            quiet=quiet,
        )

        # US-specific data
        self._ticker_membership: dict[str, list[str]] = {}

    def get_tickers(self) -> list[str]:
        """Get US ticker universe from NASDAQ FTP."""
        self._ticker_membership = get_all_us_tickers()
        tickers = list(self._ticker_membership.keys())
        self.logger.info(f"Loaded {len(tickers)} US tickers")
        return tickers

    async def fetch_prices_phase(
        self, tickers: list[str]
    ) -> tuple[dict[str, dict], list[str]]:
        """Fetch latest prices using YFinance."""
        result = await self.source.fetch_prices(tickers)

        prices = {}
        valid_tickers = []
        for ticker, data in result.succeeded.items():
            if data.prices:
                prices[ticker] = data.prices
                valid_tickers.append(ticker)

        self.logger.info(
            f"Prices: {len(valid_tickers)} valid, {result.failure_count} failed"
        )
        return prices, valid_tickers

    async def fetch_metrics_phase(
        self,
        tickers: list[str],
        history: dict[str, pd.DataFrame],
    ) -> dict[str, dict]:
        """Fetch fundamental metrics using YFinance."""
        result = await self.source.fetch_metrics(tickers)

        metrics = {}
        for ticker, data in result.succeeded.items():
            if data.metrics:
                metrics[ticker] = data.metrics

        self.logger.info(
            f"Metrics: {len(metrics)} valid, {result.failure_count} failed"
        )
        return metrics

    def build_company_record(self, ticker: str, data: dict) -> dict:
        """Build company record from collected data."""
        return {
            "ticker": ticker,
            "name": data.get("name", ticker),
            "market": "US",
            "sector": data.get("sector"),
            "industry": data.get("industry"),
        }

    def build_metrics_record(
        self,
        ticker: str,
        metrics: dict,
        technicals: dict,
        price_data: dict,
    ) -> dict:
        """Build metrics record from collected data."""
        from common.indicators import calculate_graham_number

        record = {
            "ticker": ticker,
            # Valuation
            "pe_ratio": metrics.get("pe_ratio"),
            "forward_pe": metrics.get("forward_pe"),
            "pb_ratio": metrics.get("pb_ratio"),
            "ps_ratio": metrics.get("ps_ratio"),
            "peg_ratio": metrics.get("peg_ratio"),
            "ev_ebitda": metrics.get("ev_ebitda"),
            # Profitability
            "roe": metrics.get("roe"),
            "roa": metrics.get("roa"),
            "gross_margin": metrics.get("gross_margin"),
            "net_margin": metrics.get("net_margin"),
            "operating_margin": metrics.get("operating_margin"),
            # Financial health
            "debt_equity": metrics.get("debt_equity"),
            "current_ratio": metrics.get("current_ratio"),
            "quick_ratio": metrics.get("quick_ratio"),
            # Dividend
            "dividend_yield": metrics.get("dividend_yield"),
            "payout_ratio": metrics.get("payout_ratio"),
            # Per share
            "eps": metrics.get("eps"),
            "book_value_per_share": metrics.get("book_value_per_share"),
            # Price levels
            "fifty_two_week_high": metrics.get("fifty_two_week_high"),
            "fifty_two_week_low": metrics.get("fifty_two_week_low"),
            "fifty_day_average": metrics.get("fifty_day_average"),
            "two_hundred_day_average": metrics.get("two_hundred_day_average"),
            # Market data
            "market_cap": metrics.get("market_cap"),
            "beta": metrics.get("beta"),
            "latest_price": price_data.get("close"),
            # Technical indicators
            **technicals,
        }

        # Calculate Graham Number
        eps = metrics.get("eps")
        bvps = metrics.get("book_value_per_share")
        if eps and bvps:
            graham = calculate_graham_number(eps, bvps)
            if graham:
                record["graham_number"] = graham

        return record

    def build_price_record(self, ticker: str, price_data: dict) -> dict:
        """Build price record from collected data."""
        if not price_data:
            return {}

        return {
            "ticker": ticker,
            "date": price_data.get("date", date.today().isoformat()),
            "open": price_data.get("open"),
            "high": price_data.get("high"),
            "low": price_data.get("low"),
            "close": price_data.get("close"),
            "volume": price_data.get("volume"),
        }


# Factory function for easy instantiation
def create_us_collector(
    save_db: bool = True,
    save_csv: bool = True,
    quiet: bool = False,
) -> NewUSCollector:
    """Create a US collector with default settings."""
    return NewUSCollector(
        save_db=save_db,
        save_csv=save_csv,
        quiet=quiet,
    )
