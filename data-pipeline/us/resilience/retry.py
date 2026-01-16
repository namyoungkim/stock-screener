"""Exponential Backoff Retry Executor.

Provides automatic retry with exponential backoff and jitter:
- Configurable max retries
- Exponential delay increase
- Random jitter to prevent thundering herd
- Selective retry based on exception type
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from core.errors import PipelineError
from observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryExecutor:
    """Retry executor with exponential backoff.

    Usage:
        executor = RetryExecutor(max_retries=3, base_delay=2.0)

        result = await executor.execute(risky_operation, arg1, arg2)
    """

    # Configuration
    max_retries: int = 3
    base_delay: float = 2.0  # seconds
    max_delay: float = 300.0  # seconds
    multiplier: float = 2.0
    jitter: float = 0.1  # 0.0 to 1.0

    # State
    _attempt: int = field(default=0, init=False)

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with retries.

        Args:
            func: Async or sync function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._attempt = attempt

            try:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result

                # Success - reset attempt counter
                self._attempt = 0
                return result

            except Exception as e:
                last_exception = e

                # Check if retryable
                if not self._is_retryable(e):
                    logger.debug(f"Non-retryable error: {type(e).__name__}")
                    raise

                # Check if retries exhausted
                if attempt >= self.max_retries:
                    logger.warning(
                        f"Max retries ({self.max_retries}) exhausted",
                        extra={"error": str(e)},
                    )
                    raise

                # Calculate delay with exponential backoff and jitter
                delay = self._calculate_delay(attempt)

                logger.info(
                    f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s",
                    extra={"error": type(e).__name__},
                )

                await asyncio.sleep(delay)

        # Should not reach here, but satisfy type checker
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic error")

    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable.

        Args:
            error: Exception to check

        Returns:
            True if error should be retried
        """
        # PipelineError has is_retryable property
        if isinstance(error, PipelineError):
            return error.is_retryable

        # Common retryable exceptions
        retryable_types = (
            TimeoutError,
            asyncio.TimeoutError,
            ConnectionError,
            OSError,
        )

        if isinstance(error, retryable_types):
            return True

        # Check error message for rate limit indicators
        error_str = str(error).lower()
        rate_limit_indicators = ["429", "rate limit", "too many requests", "throttl"]
        if any(indicator in error_str for indicator in rate_limit_indicators):
            return True

        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base * multiplier^attempt
        delay = self.base_delay * (self.multiplier ** attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # Add jitter
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)

        return max(0.0, delay)

    @property
    def current_attempt(self) -> int:
        """Get current attempt number."""
        return self._attempt
