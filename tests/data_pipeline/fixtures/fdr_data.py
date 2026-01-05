"""FDR (FinanceDataReader) mock data fixtures.

These fixtures provide mock data for FDR.DataReader calls.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def create_mock_ohlcv_df(
    ticker: str = "005930",
    days: int = 50,
    base_price: float = 70000,
    seed: int = 42,
) -> pd.DataFrame:
    """Create mock OHLCV DataFrame simulating FDR.DataReader output.

    Args:
        ticker: Stock ticker (for seed variation)
        days: Number of days of data
        base_price: Starting price
        seed: Random seed for reproducibility

    Returns:
        DataFrame with Open, High, Low, Close, Volume, Change columns
    """
    np.random.seed(seed + hash(ticker) % 1000)
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")

    returns = np.random.normal(0.001, 0.02, days)
    close_prices = base_price * np.cumprod(1 + returns)

    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.01, days)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.01, days)))
    open_prices = (close_prices + np.roll(close_prices, 1)) / 2
    open_prices[0] = base_price

    volumes = np.abs(1_000_000 * (1 + np.random.normal(0, 0.3, days))).astype(int)
    changes = np.diff(close_prices, prepend=close_prices[0]) / np.roll(close_prices, 1)
    changes[0] = 0

    return pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": volumes,
            "Change": changes,
        },
        index=dates,
    )


def create_mock_kospi_df(days: int = 300) -> pd.DataFrame:
    """Create mock KOSPI index DataFrame.

    Args:
        days: Number of days of data

    Returns:
        DataFrame with KOSPI OHLCV data
    """
    np.random.seed(123)
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")

    base_price = 2500
    returns = np.random.normal(0.0005, 0.01, days)
    close_prices = base_price * np.cumprod(1 + returns)

    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.005, days)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.005, days)))
    open_prices = (close_prices + np.roll(close_prices, 1)) / 2
    open_prices[0] = base_price

    volumes = np.abs(500_000_000 * (1 + np.random.normal(0, 0.2, days))).astype(int)

    return pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": volumes,
        },
        index=dates,
    )


# Sample ticker data for testing
SAMPLE_KR_TICKERS = [
    {"ticker": "005930", "name": "삼성전자", "market": "KOSPI"},
    {"ticker": "000660", "name": "SK하이닉스", "market": "KOSPI"},
    {"ticker": "035720", "name": "카카오", "market": "KOSPI"},
    {"ticker": "035420", "name": "NAVER", "market": "KOSPI"},
    {"ticker": "051910", "name": "LG화학", "market": "KOSPI"},
]

# Sample companies CSV content
SAMPLE_KR_COMPANIES_CSV = """ticker,name,market,sector,currency
005930,삼성전자,KOSPI,반도체,KRW
000660,SK하이닉스,KOSPI,반도체,KRW
035720,카카오,KOSPI,IT서비스,KRW
035420,NAVER,KOSPI,IT서비스,KRW
051910,LG화학,KOSPI,화학,KRW
"""

# Sample price data
SAMPLE_PRICE_DATA = {
    "005930": {"date": "2025-01-03", "close": 78500, "volume": 12345678},
    "000660": {"date": "2025-01-03", "close": 185000, "volume": 2345678},
    "035720": {"date": "2025-01-03", "close": 45000, "volume": 3456789},
}

# Sample KIS API fundamentals data
SAMPLE_KIS_FUNDAMENTALS = {
    "005930": {
        "pe_ratio": 12.34,
        "pb_ratio": 1.45,
        "eps": 6361,
        "book_value_per_share": 54138,
        "fifty_two_week_high": 85000,
        "fifty_two_week_low": 65000,
        "market_cap": 468500000000000,  # in 원
    },
    "000660": {
        "pe_ratio": 8.5,
        "pb_ratio": 1.2,
        "eps": 21765,
        "book_value_per_share": 154167,
        "fifty_two_week_high": 200000,
        "fifty_two_week_low": 120000,
        "market_cap": 134500000000000,
    },
}

# Sample Naver Finance fundamentals data
SAMPLE_NAVER_FUNDAMENTALS = {
    "005930": {
        "pe_ratio": 12.34,
        "pb_ratio": 1.45,
        "eps": 6361.0,
        "book_value_per_share": 54138.0,
        "roe": 0.147,
        "roa": 0.085,
        "debt_equity": 35.5,
        "market_cap": 468500000000000,
    },
    "000660": {
        "pe_ratio": 8.5,
        "pb_ratio": 1.2,
        "eps": 21765.0,
        "book_value_per_share": 154167.0,
        "roe": 0.18,
        "roa": 0.095,
    },
    "035720": {
        "pe_ratio": 25.3,
        "pb_ratio": 2.8,
        "eps": 1780.0,
        "book_value_per_share": 16071.0,
    },
}
