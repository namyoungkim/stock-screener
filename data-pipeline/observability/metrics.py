"""Metrics collection for data pipeline.

Tracks collection statistics like success rate, duration, and error types.

Usage:
    from observability import MetricsCollector

    metrics = MetricsCollector()

    with metrics.collection("kr", total=2800) as m:
        # ... do collection ...
        m.record_success(100)
        m.record_failure(5, error_type="TimeoutError")

    print(metrics.current.success_rate)  # 95.24
    print(metrics.current.to_summary())
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator


@dataclass
class CollectionMetrics:
    """Metrics for a single collection run.

    Tracks success/failure counts, timing, and error breakdown.
    """

    market: str
    started_at: datetime
    ended_at: datetime | None = None

    # Counts
    total_tickers: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    # Phase timing (seconds)
    phase_durations: dict[str, float] = field(default_factory=dict)

    # Error breakdown by type
    errors_by_type: dict[str, int] = field(default_factory=dict)

    # Rate limiting (US specific)
    rate_limit_hits: int = 0
    circuit_breaker_trips: int = 0

    # Batch tracking
    batches_completed: int = 0
    batches_total: int = 0

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        if self.total_tickers == 0:
            return 0.0
        return self.successful / self.total_tickers * 100

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds()
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def tickers_per_second(self) -> float:
        """Processing speed in tickers per second."""
        if self.duration_seconds == 0:
            return 0.0
        return self.successful / self.duration_seconds

    def record_success(self, count: int = 1) -> None:
        """Record successful ticker(s)."""
        self.successful += count

    def record_failure(self, count: int = 1, error_type: str = "unknown") -> None:
        """Record failed ticker(s) with error type."""
        self.failed += count
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + count

    def record_skip(self, count: int = 1) -> None:
        """Record skipped ticker(s)."""
        self.skipped += count

    def record_rate_limit(self) -> None:
        """Record a rate limit hit."""
        self.rate_limit_hits += 1

    def record_circuit_breaker_trip(self) -> None:
        """Record a circuit breaker trip."""
        self.circuit_breaker_trips += 1

    def record_phase_duration(self, phase: str, duration: float) -> None:
        """Record duration for a specific phase."""
        self.phase_durations[phase] = duration

    def complete(self) -> None:
        """Mark collection as complete."""
        self.ended_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "market": self.market,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_tickers": self.total_tickers,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 2),
            "tickers_per_second": round(self.tickers_per_second, 2),
            "phase_durations": self.phase_durations,
            "errors_by_type": self.errors_by_type,
            "rate_limit_hits": self.rate_limit_hits,
            "circuit_breaker_trips": self.circuit_breaker_trips,
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Collection Summary ({self.market.upper()})",
            "=" * 40,
            f"Duration: {self.duration_seconds:.1f}s",
            f"Total: {self.total_tickers} tickers",
            f"Success: {self.successful} ({self.success_rate:.1f}%)",
            f"Failed: {self.failed}",
            f"Skipped: {self.skipped}",
            f"Speed: {self.tickers_per_second:.1f} tickers/sec",
        ]

        if self.phase_durations:
            lines.append("")
            lines.append("Phase Durations:")
            for phase, duration in self.phase_durations.items():
                lines.append(f"  {phase}: {duration:.1f}s")

        if self.errors_by_type:
            lines.append("")
            lines.append("Errors by Type:")
            for error_type, count in sorted(
                self.errors_by_type.items(), key=lambda x: -x[1]
            ):
                lines.append(f"  {error_type}: {count}")

        if self.rate_limit_hits > 0:
            lines.append(f"\nRate Limit Hits: {self.rate_limit_hits}")

        if self.circuit_breaker_trips > 0:
            lines.append(f"Circuit Breaker Trips: {self.circuit_breaker_trips}")

        return "\n".join(lines)


class PhaseTimer:
    """Context manager for timing a phase."""

    def __init__(self, metrics: CollectionMetrics, phase: str) -> None:
        self.metrics = metrics
        self.phase = phase
        self.start_time: float = 0

    def __enter__(self) -> PhaseTimer:
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.monotonic() - self.start_time
        self.metrics.record_phase_duration(self.phase, duration)


class MetricsCollector:
    """Collect and manage pipeline metrics.

    Provides context managers for tracking collection runs and phases.
    """

    def __init__(self) -> None:
        self._current: CollectionMetrics | None = None
        self._history: list[CollectionMetrics] = []

    @property
    def current(self) -> CollectionMetrics | None:
        """Get current collection metrics."""
        return self._current

    @property
    def history(self) -> list[CollectionMetrics]:
        """Get history of completed collections."""
        return self._history.copy()

    @contextmanager
    def collection(
        self,
        market: str,
        total: int,
    ) -> Generator[CollectionMetrics, None, None]:
        """Context manager for a collection run.

        Args:
            market: Market identifier (kr/us)
            total: Total number of tickers to collect

        Yields:
            CollectionMetrics instance for tracking

        Example:
            with metrics.collection("kr", total=2800) as m:
                for ticker in tickers:
                    if success:
                        m.record_success()
                    else:
                        m.record_failure(error_type="TimeoutError")
        """
        self._current = CollectionMetrics(
            market=market,
            started_at=datetime.now(),
            total_tickers=total,
        )

        try:
            yield self._current
        finally:
            self._current.complete()
            self._history.append(self._current)

    def phase(self, name: str) -> PhaseTimer:
        """Context manager for timing a phase.

        Args:
            name: Phase name (e.g., "prices", "history", "metrics")

        Returns:
            PhaseTimer context manager

        Example:
            with metrics.phase("prices"):
                # ... fetch prices ...
        """
        if self._current is None:
            raise RuntimeError("No active collection. Use collection() context manager first.")
        return PhaseTimer(self._current, name)

    def get_summary(self) -> str:
        """Get summary of current or last collection."""
        if self._current:
            return self._current.to_summary()
        if self._history:
            return self._history[-1].to_summary()
        return "No collections recorded."

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics across all collections."""
        if not self._history:
            return {}

        total_success = sum(m.successful for m in self._history)
        total_failed = sum(m.failed for m in self._history)
        total_duration = sum(m.duration_seconds for m in self._history)

        return {
            "total_collections": len(self._history),
            "total_tickers_processed": total_success + total_failed,
            "total_successful": total_success,
            "total_failed": total_failed,
            "total_duration_seconds": round(total_duration, 2),
            "average_success_rate": round(
                sum(m.success_rate for m in self._history) / len(self._history), 2
            ),
        }
