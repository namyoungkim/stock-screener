"""Common configuration for data pipeline."""

from pathlib import Path

# Data directories
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
FINANCIALS_DIR = DATA_DIR / "financials"

# Batch sizes
BATCH_SIZE_HISTORY = 500  # For bulk history download (yf.download)
BATCH_SIZE_INFO = 50  # For stock info batch (yf.Tickers)
BATCH_SIZE_KR_YFINANCE = 30  # For KR yfinance metrics

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0

# Rate limiting
DELAY_BETWEEN_BATCHES = 1.0  # seconds
DELAY_AFTER_ERROR = 2.0  # seconds

# Validation thresholds (used in validators.py)
VALIDATION_THRESHOLDS = {
    "pe_ratio": {"min": -1000, "max": 10000},
    "pb_ratio": {"min": 0, "max": 500},
    "ps_ratio": {"min": 0, "max": 500},
    "roe": {"min": -10, "max": 10},  # -1000% to 1000%
    "roa": {"min": -10, "max": 10},
    "rsi": {"min": 0, "max": 100},
    "mfi": {"min": 0, "max": 100},
    "debt_equity": {"min": 0, "max": 1000},
    "current_ratio": {"min": 0, "max": 1000},
    "dividend_yield": {"min": 0, "max": 1},  # 0% to 100%
    "beta": {"min": -10, "max": 10},
    "bb_percent": {"min": -100, "max": 200},  # Can go outside 0-100
}
