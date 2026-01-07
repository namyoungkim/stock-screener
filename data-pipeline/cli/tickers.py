"""Ticker universe management.

Functions for fetching and updating ticker lists from official sources:
- US: NASDAQ FTP (nasdaqlisted.txt, otherlisted.txt)
- KR: FDR KRX-DESC (FinanceDataReader)
"""

import ftplib
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config import get_settings

logger = logging.getLogger(__name__)

# NASDAQ FTP settings
NASDAQ_FTP_HOST = "ftp.nasdaqtrader.com"
NASDAQ_FTP_DIR = "symboldirectory"


@dataclass
class TickerUpdateResult:
    """Result of ticker update operation."""

    total: int = 0
    added: list[str] | None = None
    removed: list[str] | None = None
    updated: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        self.added = self.added or []
        self.removed = self.removed or []
        self.errors = self.errors or []


def fetch_us_tickers() -> pd.DataFrame:
    """Fetch all US tickers from NASDAQ FTP.

    Returns:
        DataFrame with columns: ticker, name, market, exchange, is_etf
    """
    records = []

    try:
        ftp = ftplib.FTP(NASDAQ_FTP_HOST, timeout=30)
        ftp.login()
        ftp.cwd(NASDAQ_FTP_DIR)

        # Fetch NASDAQ-listed symbols
        nasdaq_data = io.BytesIO()
        ftp.retrbinary("RETR nasdaqlisted.txt", nasdaq_data.write)
        nasdaq_data.seek(0)

        for line in nasdaq_data.read().decode("utf-8").splitlines()[1:]:
            if "|" not in line:
                continue
            parts = line.split("|")
            ticker = parts[0].strip()
            if not ticker or ticker.startswith("File"):
                continue
            # Skip test symbols
            if len(parts) > 3 and parts[3].strip() == "Y":
                continue

            records.append({
                "ticker": ticker,
                "name": parts[1].strip() if len(parts) > 1 else "",
                "market": "NASDAQ",
                "exchange": "NASDAQ",
                "is_etf": parts[6].strip() == "Y" if len(parts) > 6 else False,
            })

        # Fetch other-listed symbols (NYSE, etc.)
        other_data = io.BytesIO()
        ftp.retrbinary("RETR otherlisted.txt", other_data.write)
        other_data.seek(0)

        exchange_map = {
            "N": "NYSE",
            "P": "NYSE ARCA",
            "Z": "BATS",
            "V": "IEX",
            "A": "NYSE MKT",
        }

        for line in other_data.read().decode("utf-8").splitlines()[1:]:
            if "|" not in line:
                continue
            parts = line.split("|")
            ticker = parts[0].strip()
            if not ticker or ticker.startswith("File"):
                continue
            # Skip test symbols
            if len(parts) > 6 and parts[6].strip() == "Y":
                continue

            exchange_code = parts[2].strip() if len(parts) > 2 else ""
            exchange = exchange_map.get(exchange_code, exchange_code)

            records.append({
                "ticker": ticker,
                "name": parts[1].strip() if len(parts) > 1 else "",
                "market": "US",
                "exchange": exchange,
                "is_etf": parts[4].strip() == "Y" if len(parts) > 4 else False,
            })

        ftp.quit()
        logger.info(f"Fetched {len(records)} US tickers from NASDAQ FTP")

    except Exception as e:
        logger.error(f"Failed to fetch US tickers: {e}")
        raise

    return pd.DataFrame(records)


def fetch_kr_tickers() -> pd.DataFrame:
    """Fetch all KR tickers from FDR (KRX-DESC).

    Returns:
        DataFrame with columns: ticker, name, market, sector, industry
    """
    import FinanceDataReader as fdr

    try:
        df = fdr.StockListing("KRX-DESC")

        if df.empty:
            raise RuntimeError("FDR returned empty ticker list")

        # Rename and select columns
        result = pd.DataFrame({
            "ticker": df["Code"],
            "name": df["Name"],
            "market": df["Market"],
            "sector": df.get("Sector", ""),
            "industry": df.get("Industry", ""),
        })

        # Filter out non-standard tickers (ETFs, ETNs, etc.)
        # Standard KR tickers are 6 digits
        result = result[result["ticker"].str.match(r"^\d{6}$")]

        logger.info(f"Fetched {len(result)} KR tickers from FDR")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch KR tickers: {e}")
        raise


def update_tickers(market: str, dry_run: bool = False) -> TickerUpdateResult:
    """Update ticker list for specified market.

    Args:
        market: "us" or "kr"
        dry_run: If True, don't write changes, just report

    Returns:
        TickerUpdateResult with statistics
    """
    settings = get_settings()
    result = TickerUpdateResult()

    market = market.lower()
    if market not in ("us", "kr"):
        result.errors.append(f"Invalid market: {market}")
        return result

    # Determine file path
    csv_path = settings.companies_dir / f"{market}_companies.csv"

    # Fetch new tickers
    try:
        if market == "us":
            new_df = fetch_us_tickers()
        else:
            new_df = fetch_kr_tickers()
    except Exception as e:
        result.errors.append(str(e))
        return result

    result.total = len(new_df)

    # Load existing tickers if file exists
    if csv_path.exists():
        existing_df = pd.read_csv(csv_path, dtype={"ticker": str})
        existing_tickers = set(existing_df["ticker"].tolist())
        new_tickers = set(new_df["ticker"].tolist())

        result.added = sorted(new_tickers - existing_tickers)
        result.removed = sorted(existing_tickers - new_tickers)
    else:
        result.added = sorted(new_df["ticker"].tolist())

    # Save if not dry run
    if not dry_run:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(csv_path, index=False)
        result.updated = len(new_df)
        logger.info(f"Saved {len(new_df)} tickers to {csv_path}")

    return result
