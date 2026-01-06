"""Pytest fixtures for data pipeline tests."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Generate 50 days of realistic OHLCV data for testing.

    Creates a DataFrame with Open, High, Low, Close, Volume columns
    that mimics real stock price movements.
    """
    np.random.seed(42)  # For reproducibility
    n_days = 50
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq="B")

    # Start with base price and add random walk
    base_price = 100.0
    returns = np.random.normal(0.001, 0.02, n_days)  # Daily returns
    close_prices = base_price * np.cumprod(1 + returns)

    # Generate OHLC from close
    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.01, n_days)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.01, n_days)))
    open_prices = (close_prices + np.roll(close_prices, 1)) / 2
    open_prices[0] = base_price

    # Volume with some variation
    base_volume = 1_000_000
    volumes = base_volume * (1 + np.random.normal(0, 0.3, n_days))
    volumes = np.abs(volumes).astype(int)

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


@pytest.fixture
def common_dates() -> pd.DatetimeIndex:
    """Generate common date range for stock and market DataFrames."""
    # Use fixed end date to ensure consistency between fixtures
    end_date = datetime(2025, 1, 1)
    return pd.date_range(end=end_date, periods=300, freq="B")


@pytest.fixture
def sample_long_df(common_dates) -> pd.DataFrame:
    """Generate 300 days of OHLCV data for MA200 and Beta tests."""
    np.random.seed(42)
    n_days = len(common_dates)

    base_price = 100.0
    returns = np.random.normal(0.001, 0.02, n_days)
    close_prices = base_price * np.cumprod(1 + returns)

    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.01, n_days)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.01, n_days)))
    open_prices = (close_prices + np.roll(close_prices, 1)) / 2
    open_prices[0] = base_price

    base_volume = 1_000_000
    volumes = np.abs(base_volume * (1 + np.random.normal(0, 0.3, n_days))).astype(int)

    return pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": volumes,
        },
        index=common_dates,
    )


@pytest.fixture
def sample_market_df(common_dates) -> pd.DataFrame:
    """Generate 300 days of market index data for Beta calculation."""
    np.random.seed(123)  # Different seed for market
    n_days = len(common_dates)

    base_price = 3000.0  # Market index level
    returns = np.random.normal(0.0005, 0.01, n_days)  # Less volatile than stocks
    close_prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame(
        {
            "Close": close_prices,
        },
        index=common_dates,
    )


@pytest.fixture
def sample_short_df() -> pd.DataFrame:
    """Generate 5 days of data (insufficient for most indicators)."""
    dates = pd.date_range(end=datetime.now(), periods=5, freq="B")

    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 101, 103],
            "High": [101, 102, 103, 102, 104],
            "Low": [99, 100, 101, 100, 102],
            "Close": [100.5, 101.5, 102.5, 101.5, 103.5],
            "Volume": [1000000, 1100000, 900000, 1200000, 1000000],
        },
        index=dates,
    )


@pytest.fixture
def sample_empty_df() -> pd.DataFrame:
    """Empty DataFrame for edge case testing."""
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


@pytest.fixture
def sample_uptrend_df() -> pd.DataFrame:
    """Generate data with clear uptrend (for RSI > 50 testing)."""
    n_days = 30
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq="B")

    # Consistent uptrend
    close_prices = np.linspace(100, 130, n_days)  # 30% increase
    high_prices = close_prices * 1.01
    low_prices = close_prices * 0.99
    open_prices = close_prices * 0.995

    return pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": [1000000] * n_days,
        },
        index=dates,
    )


@pytest.fixture
def sample_downtrend_df() -> pd.DataFrame:
    """Generate data with clear downtrend (for RSI < 50 testing)."""
    n_days = 30
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq="B")

    # Consistent downtrend
    close_prices = np.linspace(130, 100, n_days)  # 23% decrease
    high_prices = close_prices * 1.01
    low_prices = close_prices * 0.99
    open_prices = close_prices * 1.005

    return pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": [1000000] * n_days,
        },
        index=dates,
    )
