"""Korean stock collector using new architecture.

This is the new implementation using BaseCollector pattern.
Target: < 300 lines (vs 1,267 lines in legacy kr_stocks.py)

Data sources:
- FDR: Prices and history (via Naver Finance)
- KIS API: Fundamentals (primary, if available)
- Naver scraper: Fundamentals (fallback)
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from config import Settings, get_settings
from processors.validators import MetricsValidator
from rate_limit import RateLimitStrategy
from sources import FDRSource, NaverSource, KISSource, FetchResult
from storage import Storage, CSVStorage

from .base import BaseCollector

logger = logging.getLogger(__name__)


def load_kr_tickers(companies_file: Path) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Load Korean tickers from companies CSV.

    Returns:
        Tuple of (ticker_list, ticker_to_name, ticker_to_market)
    """
    tickers = []
    ticker_names = {}
    ticker_markets = {}

    try:
        df = pd.read_csv(companies_file, dtype={"ticker": str})
        for _, row in df.iterrows():
            ticker = str(row["ticker"]).strip()
            tickers.append(ticker)
            ticker_names[ticker] = row.get("name", ticker)
            ticker_markets[ticker] = row.get("market", "KOSPI")

        logger.info(f"Loaded {len(tickers)} KR tickers from {companies_file}")

    except Exception as e:
        logger.error(f"Failed to load KR tickers: {e}")

    return tickers, ticker_names, ticker_markets


@dataclass
class NewKRCollector(BaseCollector):
    """Korean stock collector.

    Uses FDRSource for prices/history and KIS/Naver for metrics.
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
        """Initialize KR collector."""
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

        # Create data sources
        self._fdr_source = FDRSource(batch_size=100)
        self._kis_source = KISSource()
        self._naver_source = NaverSource(concurrency=10)

        super().__init__(
            market="KR",
            data_source=self._fdr_source,  # Primary source for prices/history
            storage=storage,
            rate_limit_strategy=rate_limit_strategy,
            validator=validator,
            settings=settings,
            quiet=quiet,
        )

        # KR-specific data
        self._ticker_names: dict[str, str] = {}
        self._ticker_markets: dict[str, str] = {}
        self._kospi_history: pd.DataFrame | None = None

    def get_tickers(self) -> list[str]:
        """Get KR ticker universe from companies CSV."""
        companies_file = self.settings.companies_dir / "kr_companies.csv"

        tickers, names, markets = load_kr_tickers(companies_file)
        self._ticker_names = names
        self._ticker_markets = markets

        self.logger.info(f"Loaded {len(tickers)} KR tickers")
        return tickers

    async def fetch_prices_phase(
        self, tickers: list[str]
    ) -> tuple[dict[str, dict], list[str]]:
        """Fetch latest prices using FDR."""
        result = await self._fdr_source.fetch_prices(tickers)

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

    async def fetch_history_phase(
        self, tickers: list[str]
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV history using FDR."""
        result = await self._fdr_source.fetch_history(tickers, days=300)

        history = {}
        for ticker, data in result.succeeded.items():
            if data.history is not None and not data.history.empty:
                history[ticker] = data.history

        # Also fetch KOSPI index for Beta calculation
        self._kospi_history = await self._fdr_source.fetch_index_history("KS11", days=300)

        self.logger.info(f"History: {len(history)} tickers")
        return history

    async def fetch_metrics_phase(
        self,
        tickers: list[str],
        history: dict[str, pd.DataFrame],
    ) -> dict[str, dict]:
        """Fetch fundamental metrics using Naver (base) and KIS (supplement).

        Strategy:
        1. Naver first: EPS, BPS, PER, PBR (good coverage)
        2. KIS supplement: 52-week high/low, more accurate PER/PBR
        3. Merge: KIS overwrites Naver for overlapping fields
        """
        metrics = {}

        # Step 1: Naver for base data (EPS, BPS, etc.)
        self.logger.info(f"Fetching {len(tickers)} tickers from Naver...")
        naver_result = await self._naver_source.fetch_metrics(tickers)
        for ticker, data in naver_result.succeeded.items():
            if data.metrics:
                metrics[ticker] = data.metrics

        # Step 2: KIS for supplemental data (52-week high/low)
        if self._kis_source.is_available:
            self.logger.info("Supplementing with KIS API (52-week high/low)...")
            kis_result = await self._kis_source.fetch_metrics(tickers)
            for ticker, data in kis_result.succeeded.items():
                if data.metrics:
                    if ticker in metrics:
                        # Merge: KIS overwrites Naver, but only for non-None values
                        for key, value in data.metrics.items():
                            if value is not None:
                                metrics[ticker][key] = value
                    else:
                        metrics[ticker] = data.metrics

        self.logger.info(f"Metrics: {len(metrics)} tickers")
        return metrics

    def calculate_technicals_phase(
        self, history: dict[str, pd.DataFrame]
    ) -> dict[str, dict]:
        """Calculate technical indicators including Beta vs KOSPI."""
        # First get standard technicals from base class
        technicals = super().calculate_technicals_phase(history)

        # Add Beta calculation using KOSPI index
        if self._kospi_history is not None and not self._kospi_history.empty:
            from common.indicators import calculate_beta

            for ticker, df in history.items():
                if ticker in technicals and df is not None and not df.empty:
                    beta = calculate_beta(df, self._kospi_history)
                    if beta is not None:
                        technicals[ticker]["beta"] = beta

        return technicals

    def build_company_record(self, ticker: str, data: dict) -> dict:
        """Build company record from collected data."""
        return {
            "ticker": ticker,
            "name": self._ticker_names.get(ticker, data.get("name", ticker)),
            "market": self._ticker_markets.get(ticker, "KOSPI"),
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
            # Valuation (from KIS or Naver)
            "pe_ratio": metrics.get("per") or metrics.get("pe_ratio"),
            "pb_ratio": metrics.get("pbr") or metrics.get("pb_ratio"),
            # Profitability
            "roe": metrics.get("roe"),
            "roa": metrics.get("roa"),
            # Dividend
            "dividend_yield": metrics.get("dividend_yield"),
            # Per share
            "eps": metrics.get("eps"),
            "book_value_per_share": metrics.get("bps") or metrics.get("book_value_per_share"),
            # Price levels (KIS uses high_52w/low_52w, map to standard names)
            "fifty_two_week_high": metrics.get("fifty_two_week_high") or metrics.get("high_52w"),
            "fifty_two_week_low": metrics.get("fifty_two_week_low") or metrics.get("low_52w"),
            # Market data
            "market_cap": metrics.get("market_cap"),
            "latest_price": price_data.get("close"),
            # Technical indicators
            **technicals,
        }

        # Calculate Graham Number
        eps = record.get("eps")
        bvps = record.get("book_value_per_share")
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
def create_kr_collector(
    save_db: bool = True,
    save_csv: bool = True,
    quiet: bool = False,
) -> NewKRCollector:
    """Create a KR collector with default settings."""
    return NewKRCollector(
        save_db=save_db,
        save_csv=save_csv,
        quiet=quiet,
    )
