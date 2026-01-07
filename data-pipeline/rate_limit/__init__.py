"""Rate limiting infrastructure for data collection."""

from .backoff import BackoffPolicy, ExponentialBackoff, LinearBackoff, NoBackoff
from .progress import ProgressTracker
from .strategies import (
    BatchResult,
    FailureType,
    RateLimitStrategy,
    AdaptiveRateLimitStrategy,
    NoOpRateLimitStrategy,
    classify_failure,
    is_retryable,
)

__all__ = [
    # Backoff policies
    "BackoffPolicy",
    "ExponentialBackoff",
    "LinearBackoff",
    "NoBackoff",
    # Progress tracking
    "ProgressTracker",
    # Strategies
    "BatchResult",
    "FailureType",
    "RateLimitStrategy",
    "AdaptiveRateLimitStrategy",
    "NoOpRateLimitStrategy",
    # Utilities
    "classify_failure",
    "is_retryable",
]
