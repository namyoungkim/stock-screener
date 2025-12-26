"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_stock_data() -> dict:
    """Sample stock data for testing."""
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "market_cap": 3000000000000,
        "pe_ratio": 28.5,
        "pb_ratio": 45.2,
        "roe": 0.147,
        "debt_equity": 1.81,
    }
