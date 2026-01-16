"""Circuit Breaker pattern for cascade failure prevention.

State transitions:
CLOSED (normal) → [failure_threshold failures] → OPEN (blocked)
OPEN → [recovery_timeout wait] → HALF_OPEN (testing)
HALF_OPEN → [success_threshold successes] → CLOSED
HALF_OPEN → [any failure] → OPEN
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from observability.logger import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for preventing cascade failures.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=300)

        async with breaker:
            result = await risky_operation()

        # Or with execute:
        result = await breaker.execute(risky_operation)
    """

    # Configuration
    failure_threshold: int = 5
    recovery_timeout: float = 300.0  # seconds
    success_threshold: int = 3

    # State
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self._state == CircuitState.OPEN

    async def __aenter__(self) -> CircuitBreaker:
        """Enter context manager - check if call is allowed."""
        await self._check_state()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager - record success or failure."""
        if exc_type is None:
            await self.record_success()
        else:
            await self.record_failure()

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async or sync function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        from core.errors import CircuitOpenError

        async with self._lock:
            await self._check_state()

        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result

            await self.record_success()
            return result

        except Exception:
            await self.record_failure()
            raise

    async def _check_state(self) -> None:
        """Check circuit state and allow/reject call."""
        from core.errors import CircuitOpenError

        now = time.monotonic()

        if self._state == CircuitState.CLOSED:
            return

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if now - self._last_failure_time >= self.recovery_timeout:
                logger.info(
                    "Circuit breaker entering HALF_OPEN state",
                    extra={"recovery_timeout": self.recovery_timeout},
                )
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
            else:
                remaining = self.recovery_timeout - (now - self._last_failure_time)
                raise CircuitOpenError(
                    f"Circuit is OPEN. Retry in {remaining:.0f}s"
                )

        # HALF_OPEN allows the call to test if service recovered

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(
                        "Circuit breaker closing after recovery",
                        extra={"success_count": self._success_count},
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            now = time.monotonic()
            self._last_failure_time = now

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN returns to OPEN
                logger.warning("Circuit breaker returning to OPEN state after failure in HALF_OPEN")
                self._state = CircuitState.OPEN
                self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        "Circuit breaker opening",
                        extra={"failure_count": self._failure_count},
                    )
                    self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        logger.info("Circuit breaker reset to CLOSED state")
