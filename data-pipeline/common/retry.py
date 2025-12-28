"""Retry utilities with exponential backoff."""

import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_exceptions: tuple = (Exception,)

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt using exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay += random.uniform(0, 1)

        return delay


def with_retry(config: RetryConfig | None = None):
    """
    Decorator to add retry logic with exponential backoff.

    Args:
        config: RetryConfig instance (uses defaults if None)

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(RetryConfig(max_retries=3))
        def fetch_data(url: str) -> dict:
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func_name = getattr(func, "__name__", "unknown")

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retry_exceptions as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed for {func_name}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_retries + 1} attempts failed for {func_name}: {e}"
                        )

            raise last_exception  # type: ignore

        return wrapper

    return decorator


@dataclass
class FailedItem:
    """Record of a failed item."""

    item: Any
    error: str
    attempts: int = 1
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class RetryQueue:
    """Queue for tracking and retrying failed items."""

    def __init__(self, save_path: Path | None = None):
        """
        Initialize retry queue.

        Args:
            save_path: Path to save/load failed items (JSON file)
        """
        self.failed_items: list[FailedItem] = []
        self.save_path = save_path

    def add_failed(self, item: Any, error: str) -> None:
        """
        Add a failed item to the queue.

        Args:
            item: The item that failed (e.g., ticker symbol)
            error: Error message
        """
        self.failed_items.append(FailedItem(item=item, error=str(error)))

    def get_failed_items(self) -> list[Any]:
        """Get list of failed items (just the items, not the metadata)."""
        return [fi.item for fi in self.failed_items]

    def save_to_file(self) -> None:
        """Save failed items to JSON file."""
        if not self.save_path:
            return

        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                "item": fi.item,
                "error": fi.error,
                "attempts": fi.attempts,
                "timestamp": fi.timestamp,
            }
            for fi in self.failed_items
        ]

        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.failed_items)} failed items to {self.save_path}")

    def load_from_file(self) -> list[Any]:
        """
        Load failed items from JSON file.

        Returns:
            List of items that previously failed
        """
        if not self.save_path or not self.save_path.exists():
            return []

        with open(self.save_path, encoding="utf-8") as f:
            data = json.load(f)

        items = [d["item"] for d in data]
        logger.info(f"Loaded {len(items)} failed items from {self.save_path}")
        return items

    def clear(self) -> None:
        """Clear all failed items."""
        self.failed_items = []

    @property
    def count(self) -> int:
        """Number of failed items."""
        return len(self.failed_items)

    def get_summary(self) -> dict:
        """Get summary of failed items."""
        if not self.failed_items:
            return {"count": 0, "errors": {}}

        # Group by error type
        error_counts: dict[str, int] = {}
        for fi in self.failed_items:
            # Truncate long error messages
            error_key = fi.error[:100] if len(fi.error) > 100 else fi.error
            error_counts[error_key] = error_counts.get(error_key, 0) + 1

        return {
            "count": len(self.failed_items),
            "errors": error_counts,
        }
