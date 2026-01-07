"""
CSV to Supabase Loader

Reads CSV files from data/ directory and upserts to Supabase.
Supports incremental updates and full reloads.

Directory structure:
    data/
    ├── us/                      # US market data
    │   ├── 2026-01-08/v1/       # Versioned collection data
    │   │   ├── metrics.csv
    │   │   └── prices.csv
    │   └── latest -> 2026-01-08/v1/
    ├── kr/                      # KR market data
    │   ├── 2026-01-08/v1/
    │   │   ├── metrics.csv
    │   │   └── prices.csv
    │   └── latest -> 2026-01-08/v1/
    └── companies/               # Master company data
        ├── us_companies.csv
        └── kr_companies.csv

Usage:
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --us-only
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --kr-only
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 2026-01-03
    uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 2026-01-03 --version v1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from supabase import Client

from common.utils import get_supabase_client, safe_float, safe_float_series, safe_int

# Data directory paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
COMPANIES_DIR = DATA_DIR / "companies"

# Batch size for Supabase upsert (Supabase supports up to 1000)
BATCH_SIZE = 1000


def find_data_directory(
    market: str,
    target_date: str | None = None,
    version: str | None = None,
) -> Path | None:
    """
    Find the appropriate data directory for metrics/prices.

    Args:
        market: Market identifier ('us' or 'kr')
        target_date: Date in YYYY-MM-DD format (optional)
        version: Version like 'v1', 'v2' (optional)

    Returns:
        Path to the data directory or None if not found
    """
    market_dir = DATA_DIR / market.lower()
    if not market_dir.exists():
        return None

    if target_date:
        date_dir = market_dir / target_date
        if not date_dir.exists():
            return None
        if version:
            version_dir = date_dir / version
            return version_dir if version_dir.exists() else None
        # Use 'current' symlink or latest version
        current = date_dir / "current"
        if current.is_symlink():
            return current.resolve()
        versions = sorted(date_dir.glob("v*"))
        return versions[-1] if versions else None

    # Default: use 'latest' symlink in market directory
    latest = market_dir / "latest"
    if latest.is_symlink():
        return latest.resolve()

    # Fallback: find most recent date directory
    date_dirs = sorted(
        [d for d in market_dir.iterdir() if d.is_dir() and d.name[0].isdigit()],
        reverse=True,
    )
    for date_dir in date_dirs:
        versions = sorted(date_dir.glob("v*"))
        if versions:
            return versions[-1]

    return None


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

    # Read US companies (vectorized)
    if us_csv and us_csv.exists():
        print(f"  Reading {us_csv.name}...")
        us_df = pd.read_csv(us_csv)
        us_df["ticker"] = us_df["ticker"].astype(str)
        us_df["market"] = "US"
        us_df["is_active"] = True
        us_df["currency"] = us_df["currency"].fillna("USD") if "currency" in us_df.columns else "USD"

        # Ensure optional columns exist
        if "sector" not in us_df.columns:
            us_df["sector"] = None
        else:
            us_df["sector"] = us_df["sector"].where(pd.notna(us_df["sector"]), None)
        if "industry" not in us_df.columns:
            us_df["industry"] = None
        else:
            us_df["industry"] = us_df["industry"].where(pd.notna(us_df["industry"]), None)

        us_records = us_df[["ticker", "name", "market", "sector", "industry", "currency", "is_active"]].to_dict("records")
        companies_to_upsert.extend(us_records)

    # Read KR companies (vectorized)
    if kr_csv and kr_csv.exists():
        print(f"  Reading {kr_csv.name}...")
        kr_df = pd.read_csv(kr_csv)
        kr_df["ticker"] = kr_df["ticker"].astype(str)
        kr_df["currency"] = kr_df["currency"].fillna("KRW") if "currency" in kr_df.columns else "KRW"
        kr_df["is_active"] = True

        # Normalize market values to match market_type enum (US, KOSPI, KOSDAQ)
        # - KOSDAQ GLOBAL → KOSDAQ (it's a subdivision of KOSDAQ)
        # - KONEX → skip (startup market, not in target universe)
        kr_df["market"] = kr_df["market"].replace({"KOSDAQ GLOBAL": "KOSDAQ"})
        kr_df = kr_df[kr_df["market"].isin(["KOSPI", "KOSDAQ"])]

        # Ensure required columns exist and replace NaN with None (for JSON serialization)
        # Also truncate long values to fit varchar(100) constraint
        if "sector" not in kr_df.columns:
            kr_df["sector"] = None
        else:
            kr_df["sector"] = kr_df["sector"].where(pd.notna(kr_df["sector"]), None)
            kr_df["sector"] = kr_df["sector"].apply(lambda x: x[:100] if isinstance(x, str) and len(x) > 100 else x)
        if "industry" not in kr_df.columns:
            kr_df["industry"] = None
        else:
            kr_df["industry"] = kr_df["industry"].where(pd.notna(kr_df["industry"]), None)
            kr_df["industry"] = kr_df["industry"].apply(lambda x: x[:100] if isinstance(x, str) and len(x) > 100 else x)

        kr_records = kr_df[["ticker", "name", "market", "sector", "industry", "currency", "is_active"]].to_dict("records")
        companies_to_upsert.extend(kr_records)

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
    trading_date: str | None = None,
) -> int:
    """
    Load metrics from CSV files to Supabase.

    Returns:
        Number of metrics records upserted.
    """
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
        "macd": "macd",
        "macd_signal": "macd_signal",
        "macd_histogram": "macd_histogram",
        "bb_upper": "bb_upper",
        "bb_middle": "bb_middle",
        "bb_lower": "bb_lower",
        "bb_percent": "bb_percent",
        "mfi": "mfi",
        # Value metrics
        "eps": "eps",
        "book_value_per_share": "book_value_per_share",
        "graham_number": "graham_number",
        # Skipped: forward_pe
    }

    # Max absolute values based on Supabase NUMERIC precision
    # After migration 002: price columns are NUMERIC(16, 4), ratios are NUMERIC(12, 4)
    COLUMN_MAX = {
        # Valuation ratios - NUMERIC(12, 4) max = 10^8
        "pe_ratio": 1e7,
        "pb_ratio": 1e7,
        "ps_ratio": 1e7,
        "ev_ebitda": 1e7,
        "peg_ratio": 1e4,
        # Profitability ratios - NUMERIC(8, 4) max = 10^4
        "roe": 1e3,
        "roa": 1e3,
        "gross_margin": 1e3,
        "net_margin": 1e3,
        # Financial health - NUMERIC(12, 4) max = 10^8
        "debt_equity": 1e7,
        "current_ratio": 1e7,
        # Other ratios
        "dividend_yield": 1e3,
        "beta": 1e3,
        # Technical indicators
        "rsi": 1e2,  # RSI is 0-100
        "mfi": 1e2,  # MFI is 0-100
        "volume_change": 1e4,  # % change
        "bb_percent": 1e3,  # %B typically 0-100 but can exceed
        # Price-based columns - NUMERIC(16, 4) max = 10^12
        "macd": 1e11,
        "macd_signal": 1e11,
        "macd_histogram": 1e11,
        "fifty_two_week_high": 1e11,
        "fifty_two_week_low": 1e11,
        "fifty_day_average": 1e11,
        "two_hundred_day_average": 1e11,
        "bb_upper": 1e11,
        "bb_middle": 1e11,
        "bb_lower": 1e11,
        # Value metrics - NUMERIC(16, 4) for price-based
        "eps": 1e7,
        "book_value_per_share": 1e11,
        "graham_number": 1e11,
    }

    metrics_to_upsert: list[dict] = []

    def process_metrics_df(
        df: pd.DataFrame,
        market: str,
        data_source: str,
        is_kr: bool = False,
        metrics_date: str | None = None,
    ) -> list[dict]:
        """Process metrics DataFrame to records (vectorized)."""
        df = df.copy()
        df["ticker"] = df["ticker"].astype(str)

        # Add date column if missing (extract from directory path or use provided)
        if "date" not in df.columns:
            if metrics_date:
                df["date"] = metrics_date
            else:
                raise ValueError("Metrics CSV missing 'date' column and no trading_date provided")

        # Add company_id column (vectorized lookup)
        if is_kr:
            # KR: try primary market first, then fallback
            df["_market"] = df.get("market", pd.Series(["KOSPI"] * len(df)))
            # Create lookup keys
            primary_keys = list(zip(df["ticker"], df["_market"]))
            fallback_market = df["_market"].map(lambda m: "KOSDAQ" if m == "KOSPI" else "KOSPI")
            fallback_keys = list(zip(df["ticker"], fallback_market))
            # Vectorized lookup with fallback
            df["company_id"] = [
                ticker_to_id.get(pk) or ticker_to_id.get(fk)
                for pk, fk in zip(primary_keys, fallback_keys)
            ]
        else:
            # US: vectorized lookup using list comprehension (faster than map for dict)
            df["company_id"] = [ticker_to_id.get((t, market)) for t in df["ticker"]]

        # Filter rows with valid company_id
        df = df[df["company_id"].notna()]
        if df.empty:
            return []

        # Apply safe_float_series (vectorized) to metric columns with max_abs limits
        for csv_col, db_col in COLUMN_MAP.items():
            if csv_col in df.columns:
                max_abs = COLUMN_MAX.get(db_col)
                df[db_col] = safe_float_series(df[csv_col], max_abs=max_abs)

        # Build final columns
        result_cols = ["company_id", "date"] + [
            db_col for db_col in COLUMN_MAP.values() if db_col in df.columns
        ]
        df["data_source"] = data_source

        # Convert to records, dropping None values per row
        records = []
        for record in df[result_cols + ["data_source"]].to_dict("records"):
            # Remove None values from each record
            clean_record = {k: v for k, v in record.items() if v is not None and pd.notna(v)}
            if "company_id" in clean_record and "date" in clean_record:
                records.append(clean_record)

        return records

    # Read US metrics (vectorized)
    if us_metrics_csv and us_metrics_csv.exists():
        print(f"  Reading {us_metrics_csv.name}...")
        us_df = pd.read_csv(us_metrics_csv)
        us_records = process_metrics_df(us_df, "US", "yfinance", is_kr=False, metrics_date=trading_date)
        metrics_to_upsert.extend(us_records)

    # Read KR metrics (vectorized)
    if kr_metrics_csv and kr_metrics_csv.exists():
        print(f"  Reading {kr_metrics_csv.name}...")
        kr_df = pd.read_csv(kr_metrics_csv)
        kr_records = process_metrics_df(kr_df, "KOSPI", "yfinance+fdr", is_kr=True, metrics_date=trading_date)
        metrics_to_upsert.extend(kr_records)

    # Batch upsert
    if metrics_to_upsert:
        print(f"  Upserting {len(metrics_to_upsert)} metrics...")
        for i in tqdm(range(0, len(metrics_to_upsert), BATCH_SIZE), desc="  Metrics"):
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

    def process_prices_df(df: pd.DataFrame, is_kr: bool = False) -> list[dict]:
        """Process prices DataFrame to records (vectorized)."""
        df = df.copy()
        df["ticker"] = df["ticker"].astype(str)

        # Add company_id column
        if is_kr:
            # KR: try KOSPI first, then KOSDAQ
            df["company_id"] = df["ticker"].map(
                lambda t: ticker_to_id.get((t, "KOSPI")) or ticker_to_id.get((t, "KOSDAQ"))
            )
        else:
            # US: simple lookup
            df["company_id"] = df["ticker"].map(lambda t: ticker_to_id.get((t, "US")))

        # Filter rows with valid company_id
        df = df[df["company_id"].notna()]
        if df.empty:
            return []

        # Apply safe_float/safe_int to price columns
        price_cols = ["open", "high", "low", "close", "market_cap"]
        for col in price_cols:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)

        if "volume" in df.columns:
            df["volume"] = df["volume"].apply(safe_int)

        # Build result columns (only include columns that exist)
        result_cols = ["company_id", "date"]
        for col in ["open", "high", "low", "close", "volume", "market_cap"]:
            if col in df.columns:
                result_cols.append(col)

        # Convert to records, dropping None values per row
        records = []
        for record in df[result_cols].to_dict("records"):
            # Remove None values from each record
            clean_record = {k: v for k, v in record.items() if v is not None and pd.notna(v)}
            if "company_id" in clean_record and "date" in clean_record:
                records.append(clean_record)

        return records

    prices_to_upsert: list[dict] = []

    # Read US prices (vectorized)
    if us_prices_csv and us_prices_csv.exists():
        print(f"  Reading {us_prices_csv.name}...")
        us_df = pd.read_csv(us_prices_csv)
        us_records = process_prices_df(us_df, is_kr=False)
        prices_to_upsert.extend(us_records)

    # Read KR prices (vectorized)
    if kr_prices_csv and kr_prices_csv.exists():
        print(f"  Reading {kr_prices_csv.name}...")
        kr_df = pd.read_csv(kr_prices_csv)
        kr_records = process_prices_df(kr_df, is_kr=True)
        prices_to_upsert.extend(kr_records)

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
    version: str | None = None,
) -> dict:
    """
    Main function to load CSV data to Supabase.

    Args:
        us_only: Only load US data
        kr_only: Only load KR data
        target_date: Specific date to load (YYYY-MM-DD format). If None, uses latest.
        version: Specific version to load (e.g., 'v1', 'v2'). If None, uses latest.

    Returns:
        Summary statistics.
    """
    print("=" * 60)
    print("CSV to Supabase Loader")
    print("=" * 60)

    client = get_supabase_client()

    # Find data directories for each market
    us_data_dir = None if kr_only else find_data_directory("us", target_date, version)
    kr_data_dir = None if us_only else find_data_directory("kr", target_date, version)

    if not us_data_dir and not kr_only:
        print(f"WARNING: No US data directory found for date={target_date}, version={version}")
    if not kr_data_dir and not us_only:
        print(f"WARNING: No KR data directory found for date={target_date}, version={version}")

    if not us_data_dir and not kr_data_dir:
        print("ERROR: No data directories found. Make sure data has been collected first.")
        return {"companies": 0, "metrics": 0, "prices": 0}

    if us_data_dir:
        print(f"Using US data directory: {us_data_dir}")
    if kr_data_dir:
        print(f"Using KR data directory: {kr_data_dir}")

    # Companies are in fixed location
    us_companies_csv = None if kr_only else COMPANIES_DIR / "us_companies.csv"
    kr_companies_csv = None if us_only else COMPANIES_DIR / "kr_companies.csv"

    # Metrics and prices from versioned market directories (no market prefix in filename)
    us_metrics_csv = (us_data_dir / "metrics.csv") if us_data_dir else None
    kr_metrics_csv = (kr_data_dir / "metrics.csv") if kr_data_dir else None
    us_prices_csv = (us_data_dir / "prices.csv") if us_data_dir else None
    kr_prices_csv = (kr_data_dir / "prices.csv") if kr_data_dir else None

    # Extract trading date from directory path (e.g., data/us/2026-01-08/v5 → 2026-01-08)
    # Use US date if available, otherwise KR date
    trading_date = None
    if us_data_dir:
        trading_date = us_data_dir.parent.name
    elif kr_data_dir:
        trading_date = kr_data_dir.parent.name

    # Phase 1: Load companies and get ID mapping
    print("\nPhase 1: Loading companies...")
    ticker_to_id = load_companies(client, us_companies_csv, kr_companies_csv)
    print(f"  Loaded {len(ticker_to_id)} company mappings")

    # Phase 2: Load metrics
    print("\nPhase 2: Loading metrics...")
    metrics_count = load_metrics(client, ticker_to_id, us_metrics_csv, kr_metrics_csv, trading_date=trading_date)
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

    # Parse --date YYYY-MM-DD
    target_date = None
    if "--date" in args:
        idx = args.index("--date")
        if idx + 1 < len(args):
            target_date = args[idx + 1]

    # Parse --version vN
    version = None
    if "--version" in args:
        idx = args.index("--version")
        if idx + 1 < len(args):
            version = args[idx + 1]

    result = main(
        us_only=us_only,
        kr_only=kr_only,
        target_date=target_date,
        version=version,
    )
    print(f"\nSummary: {result}")
