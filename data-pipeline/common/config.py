"""Common configuration for data pipeline."""

from pathlib import Path

# Data directories
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
FINANCIALS_DIR = DATA_DIR / "financials"
