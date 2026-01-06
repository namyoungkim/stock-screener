"""Storage utilities for Supabase and CSV operations.

This module provides a unified interface for:
- Supabase upsert operations (companies, metrics, prices)
- CSV file operations (save, load completed tickers)
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from supabase import Client

from .config import COMPANIES_DIR, DATA_DIR, DATE_FORMAT
from .utils import get_supabase_client, safe_float, safe_int

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["StorageManager", "get_supabase_client", "safe_float", "safe_int"]


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
        self.companies_dir = COMPANIES_DIR
        self.market_prefix = market_prefix

        # Version directory tracking
        self._current_date_dir: Path | None = None
        self._current_version_dir: Path | None = None

        # Ensure companies directory exists
        self.companies_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_version_dir(
        self, target_date: date | None = None, force_new: bool = False
    ) -> Path:
        """
        Get or create a version directory for the target date.

        By default, reuses the latest existing version for the same date.
        Use force_new=True to create a new version explicitly.

        Args:
            target_date: Target date (default: today)
            force_new: If True, always create a new version (v2, v3, ...)

        Returns:
            Path to the version directory (e.g., data/2026-01-03/v1/)
        """
        # If already set (during this session), return it
        if self._current_version_dir:
            return self._current_version_dir

        target = target_date or date.today()
        date_str = target.strftime(DATE_FORMAT)
        date_dir = self.data_dir / date_str

        # Check for existing versions
        if date_dir.exists():
            existing = sorted(date_dir.glob("v*"))
            if existing:
                if force_new:
                    # Create new version
                    last_v = existing[-1].name
                    next_v = int(last_v[1:]) + 1
                    version_dir = date_dir / f"v{next_v}"
                    version_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created new version directory: {version_dir}")
                else:
                    # Reuse latest version
                    version_dir = existing[-1]
                    logger.info(f"Using existing version directory: {version_dir}")
            else:
                # No versions yet, create v1
                version_dir = date_dir / "v1"
                version_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created version directory: {version_dir}")
        else:
            # Date directory doesn't exist, create v1
            version_dir = date_dir / "v1"
            version_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created version directory: {version_dir}")

        self._current_version_dir = version_dir
        self._current_date_dir = date_dir
        return version_dir

    def resume_version_dir(self, target_date: date | None = None) -> Path:
        """
        Resume to the latest version directory for the target date.

        Note: This is now equivalent to get_or_create_version_dir() since
        the default behavior is to reuse existing versions.

        Args:
            target_date: Target date (default: today)

        Returns:
            Path to the version directory
        """
        return self.get_or_create_version_dir(target_date, force_new=False)

    def update_symlinks(self) -> None:
        """Update current and latest symlinks after successful collection."""
        if not self._current_version_dir or not self._current_date_dir:
            logger.warning("No version directory set, skipping symlink update")
            return

        # Update date/current symlink
        current_link = self._current_date_dir / "current"
        if current_link.is_symlink() or current_link.exists():
            current_link.unlink()
        current_link.symlink_to(self._current_version_dir.name)
        logger.info(f"Updated symlink: {current_link} -> {self._current_version_dir.name}")

        # Update data/latest symlink
        latest_link = self.data_dir / "latest"
        if latest_link.is_symlink() or latest_link.exists():
            latest_link.unlink()
        # Use relative path for portability
        relative_path = self._current_version_dir.relative_to(self.data_dir)
        latest_link.symlink_to(relative_path)
        logger.info(f"Updated symlink: {latest_link} -> {relative_path}")

    def get_current_version_dir(self) -> Path | None:
        """Get the current version directory if set."""
        return self._current_version_dir

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
            data_source: Source of the data ("yfinance", "yfinance+fdr")
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
                "price_to_52w_high_pct",
                "ma_trend",
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

        New structure:
        - companies -> data/companies/{prefix}_companies.csv
        - metrics -> data/YYYY-MM-DD/vN/{prefix}_metrics.csv
        - prices -> data/YYYY-MM-DD/vN/{prefix}_prices.csv

        Args:
            companies: List of company dictionaries
            metrics: List of metrics dictionaries
            prices: List of price dictionaries
            is_test: If True, append "_test" to filenames
        """
        suffix = "_test" if is_test else ""
        prefix = self.market_prefix

        # Get version directory (creates if needed)
        version_dir = self.get_or_create_version_dir()

        # Save companies to companies/ directory (merge with existing)
        if companies:
            companies_df = pd.DataFrame(companies)
            companies_file = self.companies_dir / f"{prefix}_companies{suffix}.csv"

            if not is_test and companies_file.exists():
                existing = pd.read_csv(companies_file)
                combined = pd.concat([existing, companies_df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )
                combined.to_csv(companies_file, index=False)
            else:
                companies_df.to_csv(companies_file, index=False)

            logger.info(f"Saved {len(companies)} companies to {companies_file}")

        # Save metrics to version directory (merge for resume)
        if metrics:
            metrics_df = pd.DataFrame(metrics)
            metrics_file = version_dir / f"{prefix}_metrics{suffix}.csv"

            if not is_test and metrics_file.exists():
                existing = pd.read_csv(metrics_file)
                combined = pd.concat([existing, metrics_df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )
                combined["ticker"] = combined["ticker"].astype(str)
                combined = combined.sort_values("ticker").reset_index(drop=True)
                combined.to_csv(metrics_file, index=False)
                logger.info(
                    f"Merged {len(metrics)} metrics into {metrics_file} "
                    f"(total: {len(combined)})"
                )
            else:
                metrics_df.to_csv(metrics_file, index=False)
                logger.info(f"Saved {len(metrics)} metrics to {metrics_file}")

        # Save prices to version directory (merge for resume)
        if prices:
            prices_df = pd.DataFrame(prices)
            prices_file = version_dir / f"{prefix}_prices{suffix}.csv"

            if not is_test and prices_file.exists():
                existing = pd.read_csv(prices_file)
                combined = pd.concat([existing, prices_df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )
                combined["ticker"] = combined["ticker"].astype(str)
                combined = combined.sort_values("ticker").reset_index(drop=True)
                combined.to_csv(prices_file, index=False)
                logger.info(
                    f"Merged {len(prices)} prices into {prices_file} "
                    f"(total: {len(combined)})"
                )
            else:
                prices_df.to_csv(prices_file, index=False)
                logger.info(f"Saved {len(prices)} prices to {prices_file}")

    def load_completed_tickers(self, target_date: str | None = None) -> set[str]:
        """
        Load tickers that have already been collected (for resume functionality).

        Reads from the current version directory.

        Args:
            target_date: Date string (YYYY-MM-DD format). Default: today.

        Returns:
            Set of ticker symbols that have been collected
        """
        prefix = self.market_prefix

        # Use current version directory if set
        version_dir = self._current_version_dir
        if not version_dir:
            # Try to find latest version for the target date
            target = target_date or date.today().strftime(DATE_FORMAT)
            date_dir = self.data_dir / target
            if date_dir.exists():
                existing = sorted(date_dir.glob("v*"))
                if existing:
                    version_dir = existing[-1]

        if not version_dir or not version_dir.exists():
            return set()

        metrics_file = version_dir / f"{prefix}_metrics.csv"

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

    # ============================================================
    # Batch Upsert Methods (100x faster than individual upserts)
    # ============================================================

    def upsert_companies_batch(
        self,
        records: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Batch upsert companies to Supabase.

        Args:
            records: List of company dictionaries with keys:
                     ticker, name, market, sector, industry, currency
            batch_size: Number of records per API call

        Returns:
            Number of records upserted
        """
        if not self.client or not records:
            return 0

        count = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                self.client.table("companies").upsert(
                    batch, on_conflict="ticker,market"
                ).execute()
                count += len(batch)
            except Exception as e:
                logger.error(f"Error batch upserting companies: {e}")

        return count

    def upsert_metrics_batch(
        self,
        records: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Batch upsert metrics to Supabase.

        Args:
            records: List of metrics dictionaries with keys:
                     company_id, date, data_source, and metric fields
            batch_size: Number of records per API call

        Returns:
            Number of records upserted
        """
        if not self.client or not records:
            return 0

        count = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                self.client.table("metrics").upsert(
                    batch, on_conflict="company_id,date"
                ).execute()
                count += len(batch)
            except Exception as e:
                logger.error(f"Error batch upserting metrics: {e}")

        return count

    def upsert_prices_batch(
        self,
        records: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Batch upsert prices to Supabase.

        Args:
            records: List of price dictionaries with keys:
                     company_id, date, open, high, low, close, volume, market_cap
            batch_size: Number of records per API call

        Returns:
            Number of records upserted
        """
        if not self.client or not records:
            return 0

        count = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                self.client.table("prices").upsert(
                    batch, on_conflict="company_id,date"
                ).execute()
                count += len(batch)
            except Exception as e:
                logger.error(f"Error batch upserting prices: {e}")

        return count

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
