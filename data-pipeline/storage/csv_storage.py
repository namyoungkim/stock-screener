"""CSV file storage backend."""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .base import BaseStorage, SaveResult, VersionedPath

logger = logging.getLogger(__name__)


@dataclass
class CSVStorage(BaseStorage):
    """CSV file storage backend.

    Saves data to versioned CSV files in the data directory.
    Structure: data/{date}/v{version}/{market}_{type}.csv
    """

    data_dir: Path
    companies_dir: Path | None = None
    _versioned_path: VersionedPath | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__("csv")
        if self.companies_dir is None:
            self.companies_dir = self.data_dir / "companies"
        self.companies_dir.mkdir(parents=True, exist_ok=True)

    @property
    def versioned_path(self) -> VersionedPath:
        """Get or create versioned path for current run."""
        if self._versioned_path is None:
            today = date.today().isoformat()
            self._versioned_path = VersionedPath.get_next_version(self.data_dir, today)
            self._versioned_path.ensure_dirs()
        return self._versioned_path

    def _get_csv_path(self, market: str, data_type: str) -> Path:
        """Get path for a CSV file."""
        return self.versioned_path.version_dir / f"{market.lower()}_{data_type}.csv"

    def _get_companies_path(self, market: str) -> Path:
        """Get path for companies CSV file (not versioned)."""
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
            df = pd.read_csv(filepath, usecols=["ticker"], dtype={"ticker": str})
            return set(df["ticker"].astype(str))
        except Exception as e:
            logger.warning(f"Failed to load completed tickers: {e}")
            return set()

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        """CSV storage doesn't need company ID mapping - return empty dict."""
        return {}

    def finalize(self) -> None:
        """Update symlinks after collection is complete."""
        if self._versioned_path is not None:
            self._versioned_path.update_symlinks()
            logger.info(f"Updated symlinks to {self._versioned_path.version_dir}")

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
