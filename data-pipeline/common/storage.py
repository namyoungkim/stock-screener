"""Storage utilities for Supabase and CSV operations.

This module provides a unified interface for:
- Supabase upsert operations (companies, metrics, prices)
- CSV file operations (save, load completed tickers)
"""

import logging
import math
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from supabase import Client, create_client

from .config import DATA_DIR

load_dotenv()

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

    return create_client(url, key)


def safe_float(value: Any, max_abs: float | None = None) -> float | None:
    """
    Convert value to JSON-safe float (handles inf/nan).

    Args:
        value: The value to convert
        max_abs: Optional maximum absolute value (returns None if exceeded)

    Returns:
        Float value or None if invalid
    """
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    try:
        result = float(value)
        if max_abs is not None and abs(result) >= max_abs:
            return None
        return result
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> int | None:
    """Convert value to int (handles nan)."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class StorageManager:
    """Manages data storage to Supabase and CSV files."""

    def __init__(
        self,
        client: Client | None = None,
        data_dir: Path | None = None,
        market_prefix: str = "us",
    ):
        """
        Initialize storage manager.

        Args:
            client: Supabase client (optional, for DB operations)
            data_dir: Root data directory (default: project data/)
            market_prefix: Prefix for CSV files ("us" or "kr")
        """
        self.client = client
        self.data_dir = data_dir or DATA_DIR
        self.prices_dir = self.data_dir / "prices"
        self.financials_dir = self.data_dir / "financials"
        self.market_prefix = market_prefix

        # Ensure directories exist
        self.prices_dir.mkdir(parents=True, exist_ok=True)
        self.financials_dir.mkdir(parents=True, exist_ok=True)

    def upsert_company(
        self,
        ticker: str,
        name: str,
        market: str,
        sector: str | None = None,
        industry: str | None = None,
        currency: str = "USD",
    ) -> str | None:
        """
        Insert or update company in Supabase.

        Args:
            ticker: Stock ticker symbol
            name: Company name
            market: Market identifier ("US", "KOSPI", "KOSDAQ")
            sector: Company sector
            industry: Company industry
            currency: Trading currency

        Returns:
            Company ID (UUID) or None if failed
        """
        if not self.client:
            return None

        try:
            data = {
                "ticker": ticker,
                "name": name,
                "market": market,
                "sector": sector,
                "industry": industry,
                "currency": currency,
                "is_active": True,
            }

            result = (
                self.client.table("companies")
                .upsert(data, on_conflict="ticker,market")
                .execute()
            )

            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error upserting company {ticker}: {e}")
            return None

    def upsert_metrics(
        self,
        company_id: str,
        metrics: dict,
        data_source: str = "yfinance",
        metrics_date: str | None = None,
    ) -> bool:
        """
        Insert or update metrics in Supabase.

        Args:
            company_id: Company UUID from companies table
            metrics: Dictionary of metric values
            data_source: Source of the data ("yfinance", "yfinance+pykrx")
            metrics_date: Date for metrics (default: today)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            today = metrics_date or date.today().isoformat()

            # Build data dict with only non-None values
            data: dict[str, Any] = {
                "company_id": company_id,
                "date": today,
                "data_source": data_source,
            }

            # Metric fields to include
            metric_fields = [
                "pe_ratio",
                "pb_ratio",
                "ps_ratio",
                "ev_ebitda",
                "roe",
                "roa",
                "debt_equity",
                "current_ratio",
                "gross_margin",
                "net_margin",
                "dividend_yield",
                "eps",
                "book_value_per_share",
                "graham_number",
                "fifty_two_week_high",
                "fifty_two_week_low",
                "fifty_day_average",
                "two_hundred_day_average",
                "peg_ratio",
                "beta",
                "rsi",
                "volume_change",
                "macd",
                "macd_signal",
                "macd_histogram",
                "bb_upper",
                "bb_middle",
                "bb_lower",
                "bb_percent",
                "mfi",
            ]

            for field in metric_fields:
                if field in metrics:
                    value = safe_float(metrics[field])
                    if value is not None:
                        data[field] = value

            self.client.table("metrics").upsert(
                data, on_conflict="company_id,date"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error upserting metrics for company {company_id}: {e}")
            return False

    def upsert_price(
        self,
        company_id: str,
        price_data: dict,
        market_cap: int | None = None,
        price_date: str | None = None,
    ) -> bool:
        """
        Insert or update price in Supabase.

        Args:
            company_id: Company UUID from companies table
            price_data: Dictionary with open, high, low, close, volume
            market_cap: Market capitalization
            price_date: Date for price (default: today)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            today = price_date or date.today().isoformat()

            data: dict[str, Any] = {
                "company_id": company_id,
                "date": today,
            }

            # Add price fields
            for field in ["open", "high", "low", "close"]:
                if field in price_data:
                    value = safe_float(price_data[field])
                    if value is not None:
                        data[field] = value

            if "volume" in price_data:
                data["volume"] = safe_int(price_data["volume"])

            if market_cap is not None:
                data["market_cap"] = safe_int(market_cap)

            self.client.table("prices").upsert(
                data, on_conflict="company_id,date"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error upserting price for company {company_id}: {e}")
            return False

    def save_to_csv(
        self,
        companies: list[dict],
        metrics: list[dict],
        prices: list[dict],
        is_test: bool = False,
    ) -> None:
        """
        Save collected data to CSV files.

        Args:
            companies: List of company dictionaries
            metrics: List of metrics dictionaries
            prices: List of price dictionaries
            is_test: If True, append "_test" to filenames
        """
        today = date.today().strftime("%Y%m%d")
        suffix = "_test" if is_test else ""
        prefix = self.market_prefix

        # Save companies (merge with existing)
        if companies:
            companies_df = pd.DataFrame(companies)
            companies_file = self.data_dir / f"{prefix}_companies{suffix}.csv"

            if not is_test and companies_file.exists():
                existing = pd.read_csv(companies_file)
                combined = pd.concat([existing, companies_df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )
                combined.to_csv(companies_file, index=False)
            else:
                companies_df.to_csv(companies_file, index=False)

            logger.info(f"Saved {len(companies)} companies to {companies_file}")

        # Save metrics with date
        if metrics:
            metrics_df = pd.DataFrame(metrics)
            metrics_file = self.financials_dir / f"{prefix}_metrics_{today}{suffix}.csv"
            metrics_df.to_csv(metrics_file, index=False)
            logger.info(f"Saved {len(metrics)} metrics to {metrics_file}")

        # Save prices with date
        if prices:
            prices_df = pd.DataFrame(prices)
            prices_file = self.prices_dir / f"{prefix}_prices_{today}{suffix}.csv"
            prices_df.to_csv(prices_file, index=False)
            logger.info(f"Saved {len(prices)} prices to {prices_file}")

    def load_completed_tickers(self, target_date: str | None = None) -> set[str]:
        """
        Load tickers that have already been collected (for resume functionality).

        Args:
            target_date: Date string (YYYYMMDD format). Default: today.

        Returns:
            Set of ticker symbols that have been collected
        """
        target = target_date or date.today().strftime("%Y%m%d")
        prefix = self.market_prefix

        # Check metrics file for the target date
        metrics_file = self.financials_dir / f"{prefix}_metrics_{target}.csv"

        if not metrics_file.exists():
            return set()

        try:
            df = pd.read_csv(metrics_file)
            if "ticker" in df.columns:
                return set(df["ticker"].astype(str).tolist())
            return set()
        except Exception as e:
            logger.warning(f"Error loading completed tickers from {metrics_file}: {e}")
            return set()

    def get_company_id_mapping(
        self, market: str | None = None
    ) -> dict[tuple[str, str], str]:
        """
        Get mapping of (ticker, market) -> company_id from Supabase.

        Args:
            market: Optional market filter ("US", "KOSPI", "KOSDAQ")

        Returns:
            Dictionary mapping (ticker, market) tuples to company IDs
        """
        if not self.client:
            return {}

        try:
            query = self.client.table("companies").select("id, ticker, market")

            if market:
                query = query.eq("market", market)

            # Paginate to get all records
            all_companies: list[dict] = []
            offset = 0
            page_size = 1000

            while True:
                result = query.range(offset, offset + page_size - 1).execute()
                if not result.data:
                    break
                all_companies.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size

            return {(r["ticker"], r["market"]): r["id"] for r in all_companies}
        except Exception as e:
            logger.error(f"Error fetching company ID mapping: {e}")
            return {}
