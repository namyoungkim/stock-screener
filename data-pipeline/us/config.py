"""Configuration for US pipeline.

Rate limit focused configuration for US stock data collection.
All settings tuned for yfinance source and Yahoo Finance rate limits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class USConfig:
    """US pipeline configuration.

    Optimized for yfinance with rate limit handling:
    - Token Bucket rate limiter
    - Circuit Breaker for cascade failure prevention
    - Exponential backoff with jitter
    """

    # === Timeouts (seconds) ===
    # yf.download() for prices/history
    download_timeout: float = 120.0
    # yf.Ticker().info for metrics (most sensitive)
    info_timeout: float = 30.0
    # Batch-level timeout
    batch_timeout: float = 300.0

    # === Batch sizes ===
    # Price batch size (yf.download is forgiving)
    price_batch_size: int = 100
    # History batch size
    history_batch_size: int = 100
    # Metrics batch size (info calls are rate limited)
    metrics_batch_size: int = 20
    # Concurrent workers for ThreadPoolExecutor
    max_workers: int = 6

    # === Batch delays ===
    # Base delay between batches (seconds)
    batch_delay: float = 1.5
    # Random jitter added to delay (seconds)
    batch_jitter: float = 0.5

    # === Rate Limiter (Token Bucket) ===
    # Requests per second
    rate_limit_per_second: float = 5.0
    # Maximum burst size
    rate_limit_burst: int = 10

    # === Circuit Breaker ===
    # Consecutive failures before opening
    circuit_failure_threshold: int = 5
    # Seconds to wait in OPEN state before testing
    circuit_recovery_timeout: float = 300.0
    # Successful calls needed to close from HALF_OPEN
    circuit_success_threshold: int = 3

    # === Retry (Exponential Backoff) ===
    max_retries: int = 3
    # Base wait time (seconds)
    retry_base_delay: float = 2.0
    # Maximum wait time (seconds)
    retry_max_delay: float = 300.0
    # Backoff multiplier
    retry_multiplier: float = 2.0
    # Jitter factor (0.0 to 1.0)
    retry_jitter: float = 0.1

    # === Paths ===
    data_dir: Path = field(default_factory=lambda: Path("data/us"))
    tickers_file: Path = field(
        default_factory=lambda: Path("data/companies/us_companies.csv")
    )
    progress_file: Path = field(default_factory=lambda: Path("data/us_progress.txt"))

    # === History ===
    history_days: int = 300  # ~10 months for technical indicators

    @classmethod
    def from_env(cls) -> USConfig:
        """Create config with environment variable overrides."""
        return cls(
            download_timeout=float(os.environ.get("US_DOWNLOAD_TIMEOUT", "120.0")),
            info_timeout=float(os.environ.get("US_INFO_TIMEOUT", "30.0")),
            price_batch_size=int(os.environ.get("US_PRICE_BATCH_SIZE", "100")),
            history_batch_size=int(os.environ.get("US_HISTORY_BATCH_SIZE", "100")),
            metrics_batch_size=int(os.environ.get("US_METRICS_BATCH_SIZE", "20")),
            max_workers=int(os.environ.get("US_MAX_WORKERS", "6")),
            batch_delay=float(os.environ.get("US_BATCH_DELAY", "1.5")),
            batch_jitter=float(os.environ.get("US_BATCH_JITTER", "0.5")),
            max_retries=int(os.environ.get("US_MAX_RETRIES", "3")),
        )

    def __post_init__(self) -> None:
        """Validate configuration."""
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "tickers_file", Path(self.tickers_file))
        object.__setattr__(self, "progress_file", Path(self.progress_file))
