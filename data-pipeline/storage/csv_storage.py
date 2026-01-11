"""CSV file storage backend."""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from .base import BaseStorage, SaveResult, VersionedPath

logger = logging.getLogger(__name__)


@dataclass
class CSVStorage(BaseStorage):
    """CSV file storage backend.

    Saves data to versioned CSV files in the data directory.
    Structure: data/{market}/{date}/v{version}/{type}.csv

    Note: The date in the path is the trading date, not the collection date.
    Use set_trading_date() to set the trading date before saving data.
    """

    data_dir: Path
    companies_dir: Path | None = None
    _versioned_paths: dict[str, VersionedPath] = field(
        default_factory=dict, init=False, repr=False
    )
    _trading_dates: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        super().__init__("csv")
        if self.companies_dir is None:
            self.companies_dir = self.data_dir / "companies"
        self.companies_dir.mkdir(parents=True, exist_ok=True)

    def set_trading_date(self, market: str, trading_date: str) -> None:
        """Set the trading date for a market.

        This should be called before saving data to ensure the correct
        directory structure is created based on the actual trading date,
        not the collection date.

        Args:
            market: Market identifier ('US' or 'KR')
            trading_date: Trading date in YYYY-MM-DD format
        """
        market_key = market.lower()
        self._trading_dates[market_key] = trading_date
        logger.info(f"Set trading date for {market}: {trading_date}")

    def _get_versioned_path(self, market: str) -> VersionedPath:
        """Get or create versioned path for a market."""
        market_key = market.lower()
        if market_key not in self._versioned_paths:
            # Use trading date if set, otherwise fall back to today
            date_str = self._trading_dates.get(market_key, date.today().isoformat())
            vp = VersionedPath.get_next_version(self.data_dir, market_key, date_str)
            vp.ensure_dirs()
            self._versioned_paths[market_key] = vp
        return self._versioned_paths[market_key]

    def _get_csv_path(self, market: str, data_type: str) -> Path:
        """Get path for a CSV file."""
        vp = self._get_versioned_path(market)
        return vp.version_dir / f"{data_type}.csv"

    def _get_companies_path(self, market: str) -> Path:
        """Get path for companies CSV file (not versioned)."""
        assert self.companies_dir is not None, "companies_dir not initialized"
        return self.companies_dir / f"{market.lower()}_companies.csv"

    def save_companies(self, records: list[dict], market: str) -> SaveResult:
        """Save company records to CSV."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            df = pd.DataFrame(records)
            filepath = self._get_companies_path(market)

            # Merge with existing data
            if filepath.exists():
                existing = pd.read_csv(filepath, dtype={"ticker": str})
                df = pd.concat([existing, df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )

            # Ensure ticker is string and sort
            df["ticker"] = df["ticker"].astype(str)
            df = df.sort_values("ticker").reset_index(drop=True)
            df.to_csv(filepath, index=False)

            logger.info(f"Saved {len(records)} companies to {filepath}")
            return SaveResult(saved=len(records))

        except Exception as e:
            logger.error(f"Failed to save companies: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def save_metrics(self, records: list[dict], market: str) -> SaveResult:
        """Save metrics records to CSV."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            df = pd.DataFrame(records)
            filepath = self._get_csv_path(market, "metrics")

            # Merge with existing data
            if filepath.exists():
                existing = pd.read_csv(filepath, dtype={"ticker": str})
                df = pd.concat([existing, df]).drop_duplicates(
                    subset=["ticker"], keep="last"
                )

            # Ensure ticker is string and sort
            df["ticker"] = df["ticker"].astype(str)
            df = df.sort_values("ticker").reset_index(drop=True)
            df.to_csv(filepath, index=False)

            logger.info(f"Saved {len(records)} metrics to {filepath}")
            return SaveResult(saved=len(records))

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def save_prices(self, records: list[dict], market: str) -> SaveResult:
        """Save price records to CSV."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            df = pd.DataFrame(records)
            filepath = self._get_csv_path(market, "prices")

            # Merge with existing data
            if filepath.exists():
                existing = pd.read_csv(filepath, dtype={"ticker": str})
                df = pd.concat([existing, df]).drop_duplicates(
                    subset=["ticker", "date"], keep="last"
                )

            # Ensure ticker is string and sort
            df["ticker"] = df["ticker"].astype(str)
            df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
            df.to_csv(filepath, index=False)

            logger.info(f"Saved {len(records)} prices to {filepath}")
            return SaveResult(saved=len(records))

        except Exception as e:
            logger.error(f"Failed to save prices: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def load_completed_tickers(self, market: str) -> set[str]:
        """Load tickers that have metrics saved (for resume)."""
        filepath = self._get_csv_path(market, "metrics")
        if not filepath.exists():
            return set()

        try:
            df = pd.read_csv(filepath, usecols=["ticker"], dtype={"ticker": str})  # type: ignore[call-overload]
            return set(df["ticker"].astype(str))
        except Exception as e:
            logger.warning(f"Failed to load completed tickers: {e}")
            return set()

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        """CSV storage doesn't need company ID mapping - return empty dict."""
        return {}

    def finalize(self, market: str | None = None) -> None:
        """Update symlinks after collection is complete.

        Args:
            market: If provided, only update symlinks for this market.
                    If None, update symlinks for all collected markets.
        """
        markets = [market.lower()] if market else list(self._versioned_paths.keys())

        for m in markets:
            if m in self._versioned_paths:
                vp = self._versioned_paths[m]
                vp.update_symlinks()
                logger.info(f"Updated symlinks to {vp.version_dir}")

    def load_metrics_df(self, market: str) -> pd.DataFrame | None:
        """Load metrics as DataFrame."""
        filepath = self._get_csv_path(market, "metrics")
        if not filepath.exists():
            return None
        return pd.read_csv(filepath, dtype={"ticker": str})

    def load_prices_df(self, market: str) -> pd.DataFrame | None:
        """Load prices as DataFrame."""
        filepath = self._get_csv_path(market, "prices")
        if not filepath.exists():
            return None
        return pd.read_csv(filepath, dtype={"ticker": str})

    def load_companies_df(self, market: str) -> pd.DataFrame | None:
        """Load companies as DataFrame."""
        filepath = self._get_companies_path(market)
        if not filepath.exists():
            return None
        return pd.read_csv(filepath, dtype={"ticker": str})
