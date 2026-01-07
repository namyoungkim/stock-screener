"""Backoff policies for rate limit handling."""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass


class BackoffPolicy(ABC):
    """Abstract base for backoff policies.

    A backoff policy determines how long to wait between retry attempts.
    """

    @abstractmethod
    def next_delay(self, attempt: int) -> float:
        """Calculate delay for the next retry attempt.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds before the next attempt
        """
        ...

    @abstractmethod
    def max_attempts(self) -> int:
        """Maximum number of retry attempts allowed."""
        ...

    def should_retry(self, attempt: int) -> bool:
        """Check if another retry attempt should be made."""
        return attempt < self.max_attempts()


@dataclass
class ExponentialBackoff(BackoffPolicy):
    """Exponential backoff with optional jitter.

    delay = min(base * (multiplier ^ attempt) + jitter, max_delay)

    Example with defaults:
        attempt 0: 60s + jitter
        attempt 1: 120s + jitter
        attempt 2: 240s + jitter
        attempt 3: 480s + jitter
        attempt 4: 600s + jitter (capped at max)
    """

    base: float = 60.0  # Base delay in seconds
    multiplier: float = 2.0  # Exponential multiplier
    max_delay: float = 600.0  # Maximum delay (10 minutes)
    jitter: float = 30.0  # Random jitter range (0 to this value)
    max_attempts_val: int = 5  # Maximum retry attempts

    def next_delay(self, attempt: int) -> float:
        """Calculate exponential delay with jitter."""
        delay = min(self.base * (self.multiplier**attempt), self.max_delay)
        if self.jitter > 0:
            delay += random.uniform(0, self.jitter)
        return delay

    def max_attempts(self) -> int:
        return self.max_attempts_val


@dataclass
class LinearBackoff(BackoffPolicy):
    """Linear backoff with optional jitter.

    delay = min(base + (increment * attempt) + jitter, max_delay)

    Example with defaults:
        attempt 0: 30s + jitter
        attempt 1: 60s + jitter
        attempt 2: 90s + jitter
        ...
    """

    base: float = 30.0  # Base delay in seconds
    increment: float = 30.0  # Linear increment per attempt
    max_delay: float = 300.0  # Maximum delay (5 minutes)
    jitter: float = 10.0  # Random jitter range
    max_attempts_val: int = 5  # Maximum retry attempts

    def next_delay(self, attempt: int) -> float:
        """Calculate linear delay with jitter."""
        delay = min(self.base + (self.increment * attempt), self.max_delay)
        if self.jitter > 0:
            delay += random.uniform(0, self.jitter)
        return delay

    def max_attempts(self) -> int:
        return self.max_attempts_val


@dataclass
class NoBackoff(BackoffPolicy):
    """No backoff - immediate retry (for testing)."""

    max_attempts_val: int = 1

    def next_delay(self, attempt: int) -> float:
        return 0.0

    def max_attempts(self) -> int:
        return self.max_attempts_val


# Predefined backoff policies for different scenarios
YFINANCE_INFO_BACKOFF = ExponentialBackoff(
    base=600.0,  # 10 minutes - .info() is very strict
    multiplier=1.5,
    max_delay=3600.0,  # 1 hour max
    jitter=60.0,
    max_attempts_val=3,
)

YFINANCE_DOWNLOAD_BACKOFF = ExponentialBackoff(
    base=120.0,  # 2 minutes - download() is more lenient
    multiplier=2.0,
    max_delay=600.0,  # 10 minutes max
    jitter=30.0,
    max_attempts_val=5,
)

FDR_BACKOFF = ExponentialBackoff(
    base=60.0,  # 1 minute - FDR is generally stable
    multiplier=2.0,
    max_delay=300.0,  # 5 minutes max
    jitter=10.0,
    max_attempts_val=3,
)

NAVER_BACKOFF = LinearBackoff(
    base=30.0,  # 30 seconds - web scraping
    increment=30.0,
    max_delay=180.0,  # 3 minutes max
    jitter=10.0,
    max_attempts_val=3,
)

KIS_BACKOFF = LinearBackoff(
    base=60.0,  # 1 minute - API rate limit is clear
    increment=60.0,
    max_delay=300.0,  # 5 minutes max
    jitter=5.0,
    max_attempts_val=3,
)
