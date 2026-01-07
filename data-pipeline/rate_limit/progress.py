"""Progress tracking for resume functionality."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

logger = logging.getLogger(__name__)


@dataclass
class ProgressTracker:
    """Track collection progress for resume functionality.

    Maintains a set of completed tickers and persists them to a file
    so that collection can be resumed after interruption.

    File format: One ticker per line, sorted alphabetically.
    """

    market: str
    data_dir: Path
    _completed: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        """Load existing progress from file."""
        self._load()

    @property
    def progress_file(self) -> Path:
        """Path to the progress file."""
        return self.data_dir / f"{self.market.lower()}_progress.txt"

    @property
    def completed_count(self) -> int:
        """Number of completed tickers."""
        return len(self._completed)

    def _load(self) -> None:
        """Load progress from file."""
        if not self.progress_file.exists():
            return

        try:
            with open(self.progress_file) as f:
                self._completed = {
                    line.strip() for line in f if line.strip() and not line.startswith("#")
                }
            logger.info(f"Loaded {len(self._completed)} completed tickers from {self.progress_file}")
        except OSError as e:
            logger.warning(f"Failed to load progress file: {e}")
            self._completed = set()

    def mark_completed(self, ticker: str) -> None:
        """Mark a ticker as completed."""
        self._completed.add(ticker)

    def mark_batch_completed(self, tickers: list[str]) -> None:
        """Mark multiple tickers as completed."""
        self._completed.update(tickers)

    def is_completed(self, ticker: str) -> bool:
        """Check if a ticker has been completed."""
        return ticker in self._completed

    def get_remaining(self, all_tickers: list[str]) -> list[str]:
        """Get tickers that haven't been completed yet.

        Args:
            all_tickers: Full list of tickers to process

        Returns:
            List of tickers not in completed set (preserving order)
        """
        return [t for t in all_tickers if t not in self._completed]

    def save(self) -> None:
        """Save progress to file atomically.

        Uses write-to-temp-then-rename pattern for atomic writes.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self.progress_file.with_suffix(".tmp")

        try:
            with open(tmp_file, "w") as f:
                f.write(f"# Progress for {self.market} market\n")
                f.write(f"# {len(self._completed)} tickers completed\n")
                for ticker in sorted(self._completed):
                    f.write(f"{ticker}\n")

            # Atomic rename
            tmp_file.rename(self.progress_file)
            logger.debug(f"Saved progress: {len(self._completed)} tickers")
        except OSError as e:
            logger.error(f"Failed to save progress: {e}")
            if tmp_file.exists():
                tmp_file.unlink()
            raise

    def clear(self) -> None:
        """Clear all progress (for fresh start)."""
        self._completed.clear()
        if self.progress_file.exists():
            self.progress_file.unlink()
            logger.info(f"Cleared progress file: {self.progress_file}")

    def __contains__(self, ticker: str) -> bool:
        """Support 'in' operator."""
        return self.is_completed(ticker)

    def __len__(self) -> int:
        """Support len()."""
        return self.completed_count


@dataclass
class CollectionProgress:
    """Track overall collection progress with statistics.

    This is separate from ProgressTracker which handles persistence.
    CollectionProgress is for in-memory tracking and reporting.
    """

    total: int
    description: str = "Processing"
    _completed: int = field(default=0, init=False)
    _failed: int = field(default=0, init=False)
    _skipped: int = field(default=0, init=False)

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def failed(self) -> int:
        return self._failed

    @property
    def skipped(self) -> int:
        return self._skipped

    @property
    def processed(self) -> int:
        """Total items processed (completed + failed + skipped)."""
        return self._completed + self._failed + self._skipped

    @property
    def remaining(self) -> int:
        """Items remaining to process."""
        return max(0, self.total - self.processed)

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.processed == 0:
            return 0.0
        return (self._completed / self.processed) * 100

    def increment_completed(self, count: int = 1) -> None:
        self._completed += count

    def increment_failed(self, count: int = 1) -> None:
        self._failed += count

    def increment_skipped(self, count: int = 1) -> None:
        self._skipped += count

    def format_status(self) -> str:
        """Format current status as string."""
        return (
            f"{self.description}: {self.processed}/{self.total} "
            f"(completed={self._completed}, failed={self._failed}, skipped={self._skipped})"
        )
