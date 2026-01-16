"""Configuration for KR pipeline.

Simple, focused configuration for Korean stock data collection.
All timeouts and batch sizes are tuned for FDR/Naver/KIS sources.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class KRConfig:
    """KR pipeline configuration.

    Optimized for:
    - FDR (FinanceDataReader): Price and history data
    - Naver Finance: Fundamental metrics (web scraping)
    - KIS API: Supplementary data (optional)
    """

    # === Timeouts (seconds) ===
    # FDR needs longer timeout for 300-day history
    fdr_timeout: float = 10.0
    # Naver scraping is usually fast
    naver_timeout: float = 5.0
    # KIS API
    kis_timeout: float = 10.0
    # Batch-level timeout (for entire batch of requests)
    batch_timeout: float = 120.0

    # === Batch sizes ===
    # History fetch: larger batches are fine for FDR
    history_batch_size: int = 100
    # Naver metrics: moderate batches for web scraping
    metrics_batch_size: int = 50
    # Concurrent workers for FDR history fetch
    max_workers: int = 8

    # === Retry settings (simple) ===
    max_retries: int = 2
    retry_delay: float = 1.0

    # === Paths ===
    data_dir: Path = field(default_factory=lambda: Path("data/kr"))
    tickers_file: Path = field(
        default_factory=lambda: Path("data/companies/kr_companies.csv")
    )

    # === History ===
    history_days: int = 365  # ~12 months for 52-week high/low and technical indicators

    # === KIS API (optional) ===
    kis_app_key: str | None = field(
        default_factory=lambda: os.environ.get("KIS_APP_KEY")
    )
    kis_app_secret: str | None = field(
        default_factory=lambda: os.environ.get("KIS_APP_SECRET")
    )

    @property
    def kis_available(self) -> bool:
        """Check if KIS API credentials are available."""
        return bool(self.kis_app_key and self.kis_app_secret)

    @classmethod
    def from_env(cls) -> KRConfig:
        """Create config with environment variable overrides."""
        return cls(
            fdr_timeout=float(os.environ.get("KR_FDR_TIMEOUT", "10.0")),
            naver_timeout=float(os.environ.get("KR_NAVER_TIMEOUT", "5.0")),
            kis_timeout=float(os.environ.get("KR_KIS_TIMEOUT", "10.0")),
            history_batch_size=int(os.environ.get("KR_HISTORY_BATCH_SIZE", "100")),
            metrics_batch_size=int(os.environ.get("KR_METRICS_BATCH_SIZE", "50")),
            max_workers=int(os.environ.get("KR_MAX_WORKERS", "8")),
            max_retries=int(os.environ.get("KR_MAX_RETRIES", "2")),
        )

    def __post_init__(self) -> None:
        """Validate configuration."""
        # Ensure directories exist
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "tickers_file", Path(self.tickers_file))
