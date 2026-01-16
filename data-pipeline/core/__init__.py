"""Core infrastructure for data pipeline."""

from .errors import (
    CircuitOpenError,
    DataNotFoundError,
    PipelineError,
    RateLimitError,
    TimeoutError,
)
from .types import (
    CollectionPhase,
    CollectionResult,
    FetchResult,
    HistoryData,
    Market,
    MetricsData,
    PriceData,
    TickerData,
)

__all__ = [
    # Errors
    "PipelineError",
    "TimeoutError",
    "RateLimitError",
    "DataNotFoundError",
    "CircuitOpenError",
    # Types
    "Market",
    "CollectionPhase",
    "TickerData",
    "PriceData",
    "HistoryData",
    "MetricsData",
    "FetchResult",
    "CollectionResult",
]
