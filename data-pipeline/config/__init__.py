"""Configuration module for data pipeline."""

from .settings import Settings, get_settings
from .constants import (
    # Directories
    DATA_DIR,
    COMPANIES_DIR,
    # Batch sizes
    DEFAULT_BATCH_SIZE,
    DEFAULT_HISTORY_BATCH_SIZE,
    # Delays
    DEFAULT_BASE_DELAY,
    DEFAULT_JITTER,
    # Timeouts
    DEFAULT_REQUEST_TIMEOUT,
    # Rate limit
    MAX_RETRIES,
    MAX_CONSECUTIVE_FAILURES,
)

__all__ = [
    "Settings",
    "get_settings",
    "DATA_DIR",
    "COMPANIES_DIR",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_HISTORY_BATCH_SIZE",
    "DEFAULT_BASE_DELAY",
    "DEFAULT_JITTER",
    "DEFAULT_REQUEST_TIMEOUT",
    "MAX_RETRIES",
    "MAX_CONSECUTIVE_FAILURES",
]
