"""Error hierarchy for data pipeline.

All pipeline errors inherit from PipelineError.
Use `is_retryable` property to determine if an error can be retried.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class PipelineError(Exception):
    """Base error for all pipeline errors.

    Attributes:
        message: Error description
        ticker: Related ticker symbol (if applicable)
        source: Data source name (if applicable)
    """

    def __init__(
        self,
        message: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> None:
        self.ticker = ticker
        self.source = source
        super().__init__(message)

    @property
    def is_retryable(self) -> bool:
        """Whether this error can be retried."""
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for structured logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "ticker": self.ticker,
            "source": self.source,
            "is_retryable": self.is_retryable,
        }


class TimeoutError(PipelineError):
    """Request timed out.

    This is retryable - the server might be temporarily slow.
    """

    def __init__(
        self,
        message: str = "Request timed out",
        *,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds

    @property
    def is_retryable(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["timeout_seconds"] = self.timeout_seconds
        return d


class RateLimitError(PipelineError):
    """Rate limit exceeded (HTTP 429).

    This is retryable after waiting for `retry_after` seconds.
    Primarily used in US pipeline with yfinance.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

    @property
    def is_retryable(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["retry_after"] = self.retry_after
        return d


class DataNotFoundError(PipelineError):
    """No data available for the requested ticker.

    This is NOT retryable - the data simply doesn't exist.
    """

    def __init__(
        self,
        message: str = "Data not found",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return False


class CircuitOpenError(PipelineError):
    """Circuit breaker is open - failing fast.

    This is NOT retryable immediately. Wait until `reset_at` time.
    Used in US pipeline to prevent cascading failures.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        reset_at: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.reset_at = reset_at

    @property
    def is_retryable(self) -> bool:
        return False  # Not immediately retryable

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["reset_at"] = self.reset_at.isoformat() if self.reset_at else None
        return d


class NetworkError(PipelineError):
    """Network connectivity error.

    This is retryable - might be a temporary network issue.
    """

    def __init__(
        self,
        message: str = "Network error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)

    @property
    def is_retryable(self) -> bool:
        return True


class ValidationError(PipelineError):
    """Data validation failed.

    This is NOT retryable - the data format is invalid.
    """

    def __init__(
        self,
        message: str = "Validation error",
        *,
        field: str | None = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value

    @property
    def is_retryable(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["field"] = self.field
        d["value"] = str(self.value) if self.value is not None else None
        return d


def classify_exception(error: Exception, source: str | None = None) -> PipelineError:
    """Classify a generic exception into a PipelineError.

    Args:
        error: The exception to classify
        source: Data source name for context

    Returns:
        Appropriate PipelineError subclass
    """
    error_str = str(error).lower()

    # Rate limit indicators
    rate_limit_indicators = ["429", "rate limit", "too many requests", "throttl"]
    if any(indicator in error_str for indicator in rate_limit_indicators):
        return RateLimitError(str(error), source=source)

    # Timeout indicators
    timeout_indicators = ["timeout", "timed out", "deadline exceeded"]
    if any(indicator in error_str for indicator in timeout_indicators):
        return TimeoutError(str(error), source=source)

    # Network indicators
    network_indicators = [
        "connection",
        "network",
        "unreachable",
        "refused",
        "reset",
        "broken pipe",
    ]
    if any(indicator in error_str for indicator in network_indicators):
        return NetworkError(str(error), source=source)

    # Data not found indicators
    not_found_indicators = ["not found", "no data", "empty", "missing"]
    if any(indicator in error_str for indicator in not_found_indicators):
        return DataNotFoundError(str(error), source=source)

    # Default to base PipelineError
    return PipelineError(str(error), source=source)
