"""
CSV to Supabase Loader

Reads CSV files from data/ directory and upserts to Supabase.
Supports incremental updates and full reloads.

Usage:
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --us-only
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --kr-only
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 20251227
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client
from tqdm import tqdm


def safe_float(value: float | None) -> float | None:
    """Convert value to JSON-safe float (handles inf/nan)."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return float(value)


def safe_int(value: int | float | None) -> int | None:
    """Convert value to int (handles nan)."""
    if value is None or pd.isna(value):
        return None
    return int(value)

load_dotenv()

# Data directory paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
FINANCIALS_DIR = DATA_DIR / "financials"

# Batch size for Supabase upsert (limit ~1000)
BATCH_SIZE = 500


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)


def find_latest_csv(directory: Path, prefix: str) -> Path | None:
    """Find the most recent CSV file matching prefix."""
    pattern = f"{prefix}_*.csv"
    files = sorted(directory.glob(pattern), reverse=True)
    return files[0] if files else None


def load_companies(
    client: Client,
    us_csv: Path | None = None,
    kr_csv: Path | None = None,
) -> dict[tuple[str, str], str]:
    """
    Load companies from CSV files to Supabase.

    Returns:
        Mapping of (ticker, market) -> company_id
    """
    companies_to_upsert: list[dict] = []

    # Read US companies
    if us_csv and us_csv.exists():
        print(f"  Reading {us_csv.name}...")
        us_df = pd.read_csv(us_csv)
        for _, row in us_df.iterrows():
            companies_to_upsert.append(
                {
                    "ticker": str(row["ticker"]),
                    "name": row["name"],
                    "market": "US",
                    "sector": row.get("sector")
                    if pd.notna(row.get("sector"))
                    else None,
                    "industry": row.get("industry")
                    if pd.notna(row.get("industry"))
                    else None,
                    "currency": row.get("currency", "USD"),
                    "is_active": True,
                }
            )

    # Read KR companies
    if kr_csv and kr_csv.exists():
        print(f"  Reading {kr_csv.name}...")
        kr_df = pd.read_csv(kr_csv)
        for _, row in kr_df.iterrows():
            companies_to_upsert.append(
                {
                    "ticker": str(row["ticker"]),  # KR tickers are numeric
                    "name": row["name"],
                    "market": row["market"],  # "KOSPI" or "KOSDAQ"
                    "currency": row.get("currency", "KRW"),
                    "is_active": True,
                }
            )

    # Batch upsert
    if companies_to_upsert:
        print(f"  Upserting {len(companies_to_upsert)} companies...")
        for i in tqdm(
            range(0, len(companies_to_upsert), BATCH_SIZE), desc="  Companies"
        ):
            batch = companies_to_upsert[i : i + BATCH_SIZE]
            client.table("companies").upsert(
                batch, on_conflict="ticker,market"
            ).execute()

    # Fetch all company IDs for mapping (with pagination)
    print("  Fetching company ID mappings...")
    all_companies: list[dict] = []
    offset = 0
    page_size = 1000

    while True:
        result = (
            client.table("companies")
            .select("id, ticker, market")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_companies.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    return {(r["ticker"], r["market"]): r["id"] for r in all_companies}


def load_metrics(
    client: Client,
    ticker_to_id: dict[tuple[str, str], str],
    us_metrics_csv: Path | None = None,
    kr_metrics_csv: Path | None = None,
) -> int:
    """
    Load metrics from CSV files to Supabase.

    Returns:
        Number of metrics records upserted.
    """
    metrics_to_upsert: list[dict] = []

    # CSV column -> Supabase column mapping (only columns in schema)
    COLUMN_MAP = {
        "pe_ratio": "pe_ratio",
        "pb_ratio": "pb_ratio",
        "ps_ratio": "ps_ratio",
        "ev_ebitda": "ev_ebitda",
        "roe": "roe",
        "roa": "roa",
        "debt_equity": "debt_equity",
        "current_ratio": "current_ratio",
        "gross_margin": "gross_margin",
        "net_margin": "net_margin",
        "dividend_yield": "dividend_yield",
        "fifty_two_week_high": "fifty_two_week_high",
        "fifty_two_week_low": "fifty_two_week_low",
        "beta": "beta",
        "fifty_day_average": "fifty_day_average",
        "two_hundred_day_average": "two_hundred_day_average",
        "peg_ratio": "peg_ratio",
        "rsi": "rsi",
        "volume_change": "volume_change",
        # Skipped: forward_pe
    }

    # Read US metrics
    if us_metrics_csv and us_metrics_csv.exists():
        print(f"  Reading {us_metrics_csv.name}...")
        us_df = pd.read_csv(us_metrics_csv)
        for _, row in us_df.iterrows():
            ticker = str(row["ticker"])
            company_id = ticker_to_id.get((ticker, "US"))
            if not company_id:
                continue

            metric: dict = {
                "company_id": company_id,
                "date": row["date"],
                "data_source": "yfinance",
            }
            for csv_col, db_col in COLUMN_MAP.items():
                if csv_col in row.index:
                    val = safe_float(row[csv_col])
                    if val is not None:
                        metric[db_col] = val

            metrics_to_upsert.append(metric)

    # Read KR metrics
    if kr_metrics_csv and kr_metrics_csv.exists():
        print(f"  Reading {kr_metrics_csv.name}...")
        kr_df = pd.read_csv(kr_metrics_csv)
        for _, row in kr_df.iterrows():
            ticker = str(row["ticker"])
            market = row.get("market", "KOSPI")
            company_id = ticker_to_id.get((ticker, market))
            if not company_id:
                # Try other market
                other_market = "KOSDAQ" if market == "KOSPI" else "KOSPI"
                company_id = ticker_to_id.get((ticker, other_market))
            if not company_id:
                continue

            metric = {
                "company_id": company_id,
                "date": row["date"],
                "data_source": "yfinance+dart",
            }
            for csv_col, db_col in COLUMN_MAP.items():
                if csv_col in row.index:
                    val = safe_float(row[csv_col])
                    if val is not None:
                        metric[db_col] = val

            metrics_to_upsert.append(metric)

    # Batch upsert
    if metrics_to_upsert:
        print(f"  Upserting {len(metrics_to_upsert)} metrics...")
        for i in tqdm(
            range(0, len(metrics_to_upsert), BATCH_SIZE), desc="  Metrics"
        ):
            batch = metrics_to_upsert[i : i + BATCH_SIZE]
            client.table("metrics").upsert(
                batch, on_conflict="company_id,date"
            ).execute()

    return len(metrics_to_upsert)


def load_prices(
    client: Client,
    ticker_to_id: dict[tuple[str, str], str],
    us_prices_csv: Path | None = None,
    kr_prices_csv: Path | None = None,
) -> int:
    """
    Load prices from CSV files to Supabase.

    Returns:
        Number of price records upserted.
    """
    prices_to_upsert: list[dict] = []

    # Read US prices
    if us_prices_csv and us_prices_csv.exists():
        print(f"  Reading {us_prices_csv.name}...")
        us_df = pd.read_csv(us_prices_csv)
        for _, row in us_df.iterrows():
            ticker = str(row["ticker"])
            company_id = ticker_to_id.get((ticker, "US"))
            if not company_id:
                continue

            prices_to_upsert.append(
                {
                    "company_id": company_id,
                    "date": row["date"],
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "close": safe_float(row.get("close")),
                    "volume": safe_int(row.get("volume")),
                    "market_cap": safe_float(row.get("market_cap")),
                }
            )

    # Read KR prices
    if kr_prices_csv and kr_prices_csv.exists():
        print(f"  Reading {kr_prices_csv.name}...")
        kr_df = pd.read_csv(kr_prices_csv)
        for _, row in kr_df.iterrows():
            ticker = str(row["ticker"])
            # Try both markets since prices CSV may not have market column
            company_id = ticker_to_id.get((ticker, "KOSPI")) or ticker_to_id.get(
                (ticker, "KOSDAQ")
            )
            if not company_id:
                continue

            prices_to_upsert.append(
                {
                    "company_id": company_id,
                    "date": row["date"],
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "close": safe_float(row.get("close")),
                    "volume": safe_int(row.get("volume")),
                    "market_cap": safe_float(row.get("market_cap")),
                }
            )

    # Batch upsert
    if prices_to_upsert:
        print(f"  Upserting {len(prices_to_upsert)} prices...")
        for i in tqdm(range(0, len(prices_to_upsert), BATCH_SIZE), desc="  Prices"):
            batch = prices_to_upsert[i : i + BATCH_SIZE]
            client.table("prices").upsert(
                batch, on_conflict="company_id,date"
            ).execute()

    return len(prices_to_upsert)


def main(
    us_only: bool = False,
    kr_only: bool = False,
    target_date: str | None = None,
) -> dict:
    """
    Main function to load CSV data to Supabase.

    Args:
        us_only: Only load US data
        kr_only: Only load KR data
        target_date: Specific date to load (YYYYMMDD format). If None, uses latest.

    Returns:
        Summary statistics.
    """
    print("=" * 60)
    print("CSV to Supabase Loader")
    print("=" * 60)

    client = get_supabase_client()

    # Determine files to load
    us_companies_csv = None if kr_only else DATA_DIR / "us_companies.csv"
    kr_companies_csv = None if us_only else DATA_DIR / "kr_companies.csv"

    if target_date:
        us_metrics_csv = (
            FINANCIALS_DIR / f"us_metrics_{target_date}.csv" if not kr_only else None
        )
        kr_metrics_csv = (
            FINANCIALS_DIR / f"kr_metrics_{target_date}.csv" if not us_only else None
        )
        us_prices_csv = (
            PRICES_DIR / f"us_prices_{target_date}.csv" if not kr_only else None
        )
        kr_prices_csv = (
            PRICES_DIR / f"kr_prices_{target_date}.csv" if not us_only else None
        )
    else:
        us_metrics_csv = (
            find_latest_csv(FINANCIALS_DIR, "us_metrics") if not kr_only else None
        )
        kr_metrics_csv = (
            find_latest_csv(FINANCIALS_DIR, "kr_metrics") if not us_only else None
        )
        us_prices_csv = (
            find_latest_csv(PRICES_DIR, "us_prices") if not kr_only else None
        )
        kr_prices_csv = (
            find_latest_csv(PRICES_DIR, "kr_prices") if not us_only else None
        )

    # Phase 1: Load companies and get ID mapping
    print("\nPhase 1: Loading companies...")
    ticker_to_id = load_companies(client, us_companies_csv, kr_companies_csv)
    print(f"  Loaded {len(ticker_to_id)} company mappings")

    # Phase 2: Load metrics
    print("\nPhase 2: Loading metrics...")
    metrics_count = load_metrics(client, ticker_to_id, us_metrics_csv, kr_metrics_csv)
    print(f"  Loaded {metrics_count} metrics records")

    # Phase 3: Load prices
    print("\nPhase 3: Loading prices...")
    prices_count = load_prices(client, ticker_to_id, us_prices_csv, kr_prices_csv)
    print(f"  Loaded {prices_count} price records")

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)

    return {
        "companies": len(ticker_to_id),
        "metrics": metrics_count,
        "prices": prices_count,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    us_only = "--us-only" in args
    kr_only = "--kr-only" in args

    # Parse --date YYYYMMDD
    target_date = None
    if "--date" in args:
        idx = args.index("--date")
        if idx + 1 < len(args):
            target_date = args[idx + 1]

    result = main(us_only=us_only, kr_only=kr_only, target_date=target_date)
    print(f"\nSummary: {result}")
