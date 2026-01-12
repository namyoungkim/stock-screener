"""Supabase storage backend."""

import logging
from dataclasses import dataclass, field
from typing import Any

from supabase import Client, create_client

from .base import BaseStorage, SaveResult

logger = logging.getLogger(__name__)


@dataclass
class SupabaseStorage(BaseStorage):
    """Supabase storage backend.

    Saves data directly to Supabase PostgreSQL database.
    Uses upsert operations for idempotent writes.
    """

    supabase_url: str
    supabase_key: str
    _client: Client | None = field(default=None, init=False, repr=False)
    _company_id_cache: dict[str, dict[str, str]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        super().__init__("supabase")

    @property
    def client(self) -> Client:
        """Lazy initialization of Supabase client."""
        if self._client is None:
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    def save_companies(self, records: list[dict], market: str) -> SaveResult:
        """Save company records via upsert."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            # Prepare records for upsert
            upsert_records = []
            for record in records:
                upsert_records.append({
                    "ticker": str(record["ticker"]),
                    "name": record.get("name", ""),
                    "market": record.get("market", market),
                    "sector": record.get("sector"),
                    "industry": record.get("industry"),
                })

            # Batch upsert
            result = (
                self.client.table("companies")
                .upsert(upsert_records, on_conflict="ticker,market")
                .execute()
            )

            saved = len(result.data) if result.data else 0
            logger.info(f"Upserted {saved} companies to Supabase")
            return SaveResult(saved=saved)

        except Exception as e:
            logger.error(f"Failed to save companies to Supabase: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def save_metrics(self, records: list[dict], market: str) -> SaveResult:
        """Save metrics records via upsert."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            # Get company_id mapping
            company_ids = self.get_company_id_mapping(market)

            # Prepare records with company_id
            upsert_records = []
            skipped = 0
            for record in records:
                ticker = str(record["ticker"])
                company_id = company_ids.get(ticker)

                if not company_id:
                    logger.warning(f"No company_id for {ticker}, skipping metrics")
                    skipped += 1
                    continue

                # Remove None values to minimize payload
                metrics_record = {
                    k: v for k, v in record.items()
                    if v is not None and k != "ticker"
                }
                metrics_record["company_id"] = company_id
                upsert_records.append(metrics_record)

            if not upsert_records:
                return SaveResult(saved=0, skipped=skipped)

            # Batch upsert in chunks
            saved = 0
            chunk_size = 1000
            for i in range(0, len(upsert_records), chunk_size):
                chunk = upsert_records[i : i + chunk_size]
                result = (
                    self.client.table("metrics")
                    .upsert(chunk, on_conflict="company_id")
                    .execute()
                )
                saved += len(result.data) if result.data else 0

            logger.info(f"Upserted {saved} metrics to Supabase")
            return SaveResult(saved=saved, skipped=skipped)

        except Exception as e:
            logger.error(f"Failed to save metrics to Supabase: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def save_prices(self, records: list[dict], market: str) -> SaveResult:
        """Save price records via upsert."""
        if not records:
            return SaveResult(saved=0, skipped=0)

        try:
            # Get company_id mapping
            company_ids = self.get_company_id_mapping(market)

            # Prepare records with company_id
            upsert_records = []
            skipped = 0
            for record in records:
                ticker = str(record["ticker"])
                company_id = company_ids.get(ticker)

                if not company_id:
                    logger.warning(f"No company_id for {ticker}, skipping price")
                    skipped += 1
                    continue

                price_record = {
                    "company_id": company_id,
                    "date": record["date"],
                    "open": record.get("open"),
                    "high": record.get("high"),
                    "low": record.get("low"),
                    "close": record.get("close"),
                    "volume": record.get("volume"),
                }
                # Remove None values
                price_record = {k: v for k, v in price_record.items() if v is not None}
                upsert_records.append(price_record)

            if not upsert_records:
                return SaveResult(saved=0, skipped=skipped)

            # Batch upsert in chunks
            saved = 0
            chunk_size = 1000
            for i in range(0, len(upsert_records), chunk_size):
                chunk = upsert_records[i : i + chunk_size]
                result = (
                    self.client.table("prices")
                    .upsert(chunk, on_conflict="company_id,date")
                    .execute()
                )
                saved += len(result.data) if result.data else 0

            logger.info(f"Upserted {saved} prices to Supabase")
            return SaveResult(saved=saved, skipped=skipped)

        except Exception as e:
            logger.error(f"Failed to save prices to Supabase: {e}")
            return SaveResult(saved=0, errors=[str(e)])

    def load_completed_tickers(self, market: str) -> set[str]:
        """Load tickers that have metrics saved (for resume).

        Note: This is expensive for Supabase. Use CSV for resume tracking.
        """
        # For Supabase, we don't typically use this for resume
        # Resume tracking should use ProgressTracker with file-based storage
        return set()

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        """Get mapping of ticker to company_id for a market."""
        cache_key = market.upper()

        # Check cache first (cache is invalidated on save_companies)
        if cache_key in self._company_id_cache:
            return dict(self._company_id_cache[cache_key])

        try:
            # Fetch all companies for the market
            mapping = {}
            offset = 0
            page_size = 1000

            while True:
                result = (
                    self.client.table("companies")
                    .select("id, ticker")
                    .eq("market", market)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )

                if not result.data:
                    break

                for row in result.data:
                    mapping[row["ticker"]] = row["id"]

                if len(result.data) < page_size:
                    break
                offset += page_size

            # Also fetch KR with different market suffixes (KOSPI, KOSDAQ)
            if market.upper() == "KR":
                for kr_market in ["KOSPI", "KOSDAQ"]:
                    offset = 0
                    while True:
                        result = (
                            self.client.table("companies")
                            .select("id, ticker")
                            .eq("market", kr_market)
                            .range(offset, offset + page_size - 1)
                            .execute()
                        )

                        if not result.data:
                            break

                        for row in result.data:
                            mapping[row["ticker"]] = row["id"]

                        if len(result.data) < page_size:
                            break
                        offset += page_size

            self._company_id_cache[cache_key] = mapping
            logger.debug(f"Loaded {len(mapping)} company IDs for {market}")
            return mapping

        except Exception as e:
            logger.error(f"Failed to load company ID mapping: {e}")
            return {}

    def invalidate_company_cache(self, market: str) -> None:
        """Invalidate cached company ID mapping after save."""
        cache_key = market.upper()
        if cache_key in self._company_id_cache:
            del self._company_id_cache[cache_key]


@dataclass
class CompositeStorage(BaseStorage):
    """Composite storage that writes to multiple backends.

    Typically used to write to both CSV and Supabase.
    """

    storages: list[BaseStorage]

    def __post_init__(self) -> None:
        names = [s.name for s in self.storages]
        super().__init__(f"composite({','.join(names)})")

    def save_companies(self, records: list[dict], market: str) -> SaveResult:
        """Save to all backends, return merged result."""
        result = SaveResult()
        for storage in self.storages:
            storage_result = storage.save_companies(records, market)
            result = result.merge(storage_result)
        return result

    def save_metrics(self, records: list[dict], market: str) -> SaveResult:
        """Save to all backends, return merged result."""
        result = SaveResult()
        for storage in self.storages:
            storage_result = storage.save_metrics(records, market)
            result = result.merge(storage_result)
        return result

    def save_prices(self, records: list[dict], market: str) -> SaveResult:
        """Save to all backends, return merged result."""
        result = SaveResult()
        for storage in self.storages:
            storage_result = storage.save_prices(records, market)
            result = result.merge(storage_result)
        return result

    def load_completed_tickers(self, market: str) -> set[str]:
        """Load from first storage that returns results."""
        for storage in self.storages:
            result = storage.load_completed_tickers(market)
            if result:
                return result
        return set()

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        """Get from first storage that returns results."""
        for storage in self.storages:
            result = storage.get_company_id_mapping(market)
            if result:
                return result
        return {}

    def finalize(self, market: str | None = None) -> None:
        """Delegate finalize to all storages that support it."""
        for storage in self.storages:
            if hasattr(storage, "finalize"):
                getattr(storage, "finalize")(market)  # noqa: B009

    def set_trading_date(self, market: str, date_str: str) -> None:
        """Delegate set_trading_date to all storages that support it."""
        for storage in self.storages:
            if hasattr(storage, "set_trading_date"):
                getattr(storage, "set_trading_date")(market, date_str)  # noqa: B009
