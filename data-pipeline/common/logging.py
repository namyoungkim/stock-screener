"""Logging configuration for data pipeline."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_dir: Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    Args:
        name: Logger name
        level: Logging level (default: INFO)
        log_dir: Directory for log files (optional)
        console: Whether to add console handler (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class CollectionProgress:
    """Track collection progress with success/fail counts."""

    def __init__(self, total: int, logger: logging.Logger, desc: str = "Collecting"):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            logger: Logger instance for progress messages
            desc: Description for progress messages
        """
        self.total = total
        self.logger = logger
        self.desc = desc
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = datetime.now()

    def update(self, success: bool = True, skipped: bool = False) -> None:
        """Update progress counters."""
        if skipped:
            self.skipped += 1
        elif success:
            self.success += 1
        else:
            self.failed += 1

    @property
    def processed(self) -> int:
        """Total processed items."""
        return self.success + self.failed + self.skipped

    @property
    def progress_percent(self) -> float:
        """Progress percentage."""
        if self.total == 0:
            return 100.0
        return (self.processed / self.total) * 100

    def log_progress(self, interval: int = 100) -> None:
        """Log progress at specified intervals."""
        if self.processed > 0 and self.processed % interval == 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            rate = self.processed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.processed) / rate if rate > 0 else 0

            self.logger.info(
                f"{self.desc}: {self.processed}/{self.total} "
                f"({self.progress_percent:.1f}%) - "
                f"Success: {self.success}, Failed: {self.failed}, Skipped: {self.skipped} - "
                f"ETA: {eta:.0f}s"
            )

    def log_summary(self) -> None:
        """Log final summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if self.total == 0:
            self.logger.info(
                f"\n{'='*60}\n"
                f"{self.desc} Summary:\n"
                f"  Total: 0 (no data collected)\n"
                f"  Time: {elapsed:.1f}s\n"
                f"{'='*60}"
            )
            return

        self.logger.info(
            f"\n{'='*60}\n"
            f"{self.desc} Summary:\n"
            f"  Total: {self.total}\n"
            f"  Success: {self.success} ({self.success/self.total*100:.1f}%)\n"
            f"  Failed: {self.failed} ({self.failed/self.total*100:.1f}%)\n"
            f"  Skipped: {self.skipped} ({self.skipped/self.total*100:.1f}%)\n"
            f"  Time: {elapsed:.1f}s\n"
            f"{'='*60}"
        )

    def get_stats(self) -> dict:
        """Get statistics as dictionary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "elapsed_seconds": round(elapsed, 1),
            "success_rate": round(self.success / self.total * 100, 1) if self.total > 0 else 0,
        }
