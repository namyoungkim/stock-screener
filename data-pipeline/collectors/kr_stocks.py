"""
Korean Stock Data Collector

Collects financial data for Korean stocks using OpenDartReader.
"""

import os
from typing import TYPE_CHECKING

import OpenDartReader  # type: ignore[import-untyped]
import pandas as pd
from dotenv import load_dotenv

if TYPE_CHECKING:
    from OpenDartReader.dart import OpenDartReader as OpenDartReaderType

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")


def get_dart_reader() -> "OpenDartReaderType":
    """Get OpenDartReader instance."""
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY not set in environment variables")
    return OpenDartReader(DART_API_KEY)  # type: ignore[call-non-callable]


def get_krx_tickers() -> pd.DataFrame:
    """Get KRX (KOSPI + KOSDAQ) tickers."""
    # This requires pykrx or manual download from KRX
    # For now, return empty DataFrame
    # TODO: Implement KRX ticker fetching
    return pd.DataFrame()


def get_financial_statements(
    dart: "OpenDartReaderType", corp_code: str, year: int
) -> dict | None:
    """Get financial statements from DART."""
    try:
        # Get consolidated financial statements
        fs = dart.finstate(corp_code, year)

        if fs is None or fs.empty:
            return None

        # Extract key metrics
        # Note: Column names may vary, need to adjust based on actual data
        return {
            "corp_code": corp_code,
            "year": year,
            "revenue": None,  # Extract from fs
            "operating_income": None,
            "net_income": None,
            "total_assets": None,
            "total_liabilities": None,
            "equity": None,
        }
    except Exception as e:
        print(f"Error fetching financials for {corp_code}: {e}")
        return None


if __name__ == "__main__":
    # Test DART API
    if DART_API_KEY:
        dart = get_dart_reader()

        # Samsung Electronics
        test_code = "005930"
        print(f"\n--- Testing with Samsung ({test_code}) ---")

        try:
            fs = dart.finstate(test_code, 2023)
            print(
                f"Financial Statement shape: {fs.shape if fs is not None else 'None'}"
            )
            if fs is not None:
                print(fs.head())
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("DART_API_KEY not set. Please set it in .env file.")
