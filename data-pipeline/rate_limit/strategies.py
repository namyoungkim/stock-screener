"""Rate limit handling strategies."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol, TypeVar

from .backoff import BackoffPolicy, ExponentialBackoff, NoBackoff

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FailureType(Enum):
    """Classification of failure types for retry decisions."""

    RATE_LIMIT = "rate_limit"  # API rate limit hit - wait and retry
    TIMEOUT = "timeout"  # Request timed out - retry with shorter timeout
    NO_DATA = "no_data"  # No data available for ticker - don't retry
    AUTH_ERROR = "auth_error"  # Authentication failed - don't retry
    OTHER = "other"  # Unknown error - don't retry


def classify_failure(error: Exception) -> FailureType:
    """Classify an exception into a FailureType.

    This is the central place for error classification logic.
    All collectors should use this for consistent error handling.
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Rate limit indicators
    rate_limit_indicators = [
        "rate limit",
        "too many requests",
        "429",
        "throttl",
        "exceeded",
        "quota",
    ]
    if any(indicator in error_str for indicator in rate_limit_indicators):
        return FailureType.RATE_LIMIT

    # Timeout indicators
    timeout_indicators = [
        "timeout",
        "timed out",
        "read timeout",
        "connect timeout",
        "deadline",
    ]
    if any(indicator in error_str for indicator in timeout_indicators):
        return FailureType.TIMEOUT
    if "timeout" in error_type:
        return FailureType.TIMEOUT

    # No data indicators
    no_data_indicators = [
        "no data",
        "not found",
        "404",
        "delisted",
        "no price data",
        "empty",
        "no timezone found",
    ]
    if any(indicator in error_str for indicator in no_data_indicators):
        return FailureType.NO_DATA

    # Auth error indicators
    auth_indicators = [
        "unauthorized",
        "401",
        "403",
        "forbidden",
        "invalid key",
        "authentication",
    ]
    if any(indicator in error_str for indicator in auth_indicators):
        return FailureType.AUTH_ERROR

    return FailureType.OTHER


def is_retryable(failure_type: FailureType) -> bool:
    """Check if a failure type should be retried."""
    return failure_type in (FailureType.RATE_LIMIT, FailureType.TIMEOUT)


@dataclass
class BatchResult:
    """Result of a batch operation."""

    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, FailureType] = field(default_factory=dict)  # ticker -> failure type

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    @property
    def retryable_failures(self) -> list[str]:
        """Get tickers that failed with retryable errors."""
        return [ticker for ticker, ft in self.failed.items() if is_retryable(ft)]

    @property
    def permanent_failures(self) -> list[str]:
        """Get tickers that failed with non-retryable errors."""
        return [ticker for ticker, ft in self.failed.items() if not is_retryable(ft)]

    def merge(self, other: "BatchResult") -> "BatchResult":
        """Merge another BatchResult into this one."""
        return BatchResult(
            succeeded=self.succeeded + other.succeeded,
            failed={**self.failed, **other.failed},
        )


class RateLimitStrategy(Protocol):
    """Protocol for rate limit handling strategies.

    A rate limit strategy controls how batches of items are processed,
    including retry logic, backoff, and failure classification.
    """

    async def execute_batch(
        self,
        items: list[str],
        operation: Callable[[str], Awaitable[T | None]],
        classify_error: Callable[[Exception], FailureType] = classify_failure,
    ) -> BatchResult:
        """Execute an operation on a batch of items with rate limit handling.

        Args:
            items: List of items (typically tickers) to process
            operation: Async function that processes a single item
            classify_error: Function to classify exceptions into FailureType

        Returns:
            BatchResult with succeeded items and failed items with their failure types
        """
        ...

    def should_stop(self) -> bool:
        """Check if we should stop due to rate limits."""
        ...

    def reset(self) -> None:
        """Reset internal state for a new collection run."""
        ...


@dataclass
class AdaptiveRateLimitStrategy:
    """Adaptive rate limit strategy with exponential backoff.

    This is the main strategy used for production collection.
    It adapts to rate limit errors by backing off and retrying.
    """

    batch_size: int = 10
    base_delay: float = 2.5
    jitter: float = 1.0
    backoff_policy: BackoffPolicy = field(default_factory=ExponentialBackoff)
    max_consecutive_failures: int = 10

    # Internal state
    _consecutive_failures: int = field(default=0, init=False)
    _backoff_count: int = field(default=0, init=False)
    _stopped: bool = field(default=False, init=False)
    _total_rate_limits: int = field(default=0, init=False)

    async def execute_batch(
        self,
        items: list[str],
        operation: Callable[[str], Awaitable[T | None]],
        classify_error: Callable[[Exception], FailureType] = classify_failure,
    ) -> BatchResult:
        """Execute operation on items with adaptive rate limiting."""
        succeeded: list[str] = []
        failed: dict[str, FailureType] = {}

        for i in range(0, len(items), self.batch_size):
            if self._stopped:
                # Mark remaining items as rate limited
                for item in items[i:]:
                    failed[item] = FailureType.RATE_LIMIT
                break

            batch = items[i : i + self.batch_size]
            batch_succeeded, batch_failed = await self._execute_one_batch(
                batch, operation, classify_error
            )

            succeeded.extend(batch_succeeded)
            failed.update(batch_failed)

            # Check for rate limit situation
            rate_limit_count = sum(
                1 for ft in batch_failed.values() if ft == FailureType.RATE_LIMIT
            )

            if rate_limit_count == len(batch):
                # Entire batch failed with rate limit
                self._consecutive_failures += 1
                self._total_rate_limits += rate_limit_count
                logger.warning(
                    f"Batch entirely rate limited. "
                    f"Consecutive failures: {self._consecutive_failures}"
                )

                if self._consecutive_failures >= self.max_consecutive_failures:
                    logger.error("Max consecutive failures reached. Stopping.")
                    self._stopped = True
                    break

                if self._should_backoff():
                    await self._do_backoff()
            elif rate_limit_count > 0:
                # Partial rate limit
                self._consecutive_failures = max(0, self._consecutive_failures - 1)
                self._total_rate_limits += rate_limit_count
            else:
                # No rate limits
                self._consecutive_failures = 0

            # Inter-batch delay
            if i + self.batch_size < len(items):
                delay = self.base_delay + random.uniform(0, self.jitter)
                await asyncio.sleep(delay)

        return BatchResult(succeeded=succeeded, failed=failed)

    async def _execute_one_batch(
        self,
        batch: list[str],
        operation: Callable[[str], Awaitable[T | None]],
        classify_error: Callable[[Exception], FailureType],
    ) -> tuple[list[str], dict[str, FailureType]]:
        """Execute operation on a single batch."""
        succeeded = []
        failed = {}

        for item in batch:
            try:
                result = await operation(item)
                if result is not None:
                    succeeded.append(item)
                else:
                    failed[item] = FailureType.NO_DATA
            except Exception as e:
                failure_type = classify_error(e)
                failed[item] = failure_type
                logger.debug(f"Failed {item}: {failure_type.value} - {e}")

        return succeeded, failed

    def _should_backoff(self) -> bool:
        """Determine if we should backoff."""
        return (
            self._consecutive_failures >= 2
            and self._backoff_count < self.backoff_policy.max_attempts()
        )

    async def _do_backoff(self) -> None:
        """Perform backoff wait."""
        delay = self.backoff_policy.next_delay(self._backoff_count)
        logger.info(
            f"Rate limit backoff #{self._backoff_count + 1}: "
            f"waiting {delay:.1f}s"
        )
        await asyncio.sleep(delay)
        self._backoff_count += 1
        # Reset consecutive failures after backoff
        self._consecutive_failures = 0

    def should_stop(self) -> bool:
        """Check if we should stop due to rate limits."""
        return self._stopped

    def reset(self) -> None:
        """Reset internal state for a new collection run."""
        self._consecutive_failures = 0
        self._backoff_count = 0
        self._stopped = False
        self._total_rate_limits = 0


@dataclass
class NoOpRateLimitStrategy:
    """No-op strategy for testing - executes everything immediately."""

    async def execute_batch(
        self,
        items: list[str],
        operation: Callable[[str], Awaitable[T | None]],
        classify_error: Callable[[Exception], FailureType] = classify_failure,
    ) -> BatchResult:
        """Execute operation on all items without rate limiting."""
        succeeded = []
        failed = {}

        for item in items:
            try:
                result = await operation(item)
                if result is not None:
                    succeeded.append(item)
                else:
                    failed[item] = FailureType.NO_DATA
            except Exception as e:
                failed[item] = classify_error(e)

        return BatchResult(succeeded=succeeded, failed=failed)

    def should_stop(self) -> bool:
        return False

    def reset(self) -> None:
        pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded and cannot be recovered."""

    def __init__(self, message: str, completed: int = 0, total: int = 0):
        super().__init__(message)
        self.completed = completed
        self.total = total


class RetryExhaustedError(Exception):
    """Raised when all retries are exhausted."""

    def __init__(self, message: str, remaining_items: list[str]):
        super().__init__(message)
        self.remaining_items = remaining_items
