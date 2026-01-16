"""Token Bucket Rate Limiter.

Provides fair rate limiting with burst support:
- Requests consume tokens from bucket
- Tokens refill at a constant rate
- Burst allowed up to bucket capacity
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimiter:
    """Token bucket rate limiter.

    Usage:
        limiter = RateLimiter(rate=5.0, burst=10)

        # Acquire before making request
        await limiter.acquire()
        await make_request()

        # Or acquire multiple tokens
        await limiter.acquire(5)
        await batch_request()
    """

    # Configuration
    rate: float = 5.0  # Tokens per second
    burst: int = 10  # Maximum bucket capacity

    # State
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        """Initialize bucket to full capacity."""
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens from the bucket.

        Blocks until tokens are available.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        async with self._lock:
            wait_time = 0.0

            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                # Tokens available
                self._tokens -= tokens
            else:
                # Need to wait for tokens
                needed = tokens - self._tokens
                wait_time = needed / self.rate

                # Wait and then consume
                await asyncio.sleep(wait_time)
                self._tokens = 0
                self._last_refill = time.monotonic()

            return wait_time

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False if not enough tokens
        """
        async with self._lock:
            # Refill tokens
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Get current number of available tokens (approximate)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self.burst, self._tokens + elapsed * self.rate)
