"""Structured JSON logger for data pipeline.

Provides context-aware logging with automatic JSON formatting.

Usage:
    from observability import get_logger, LogContext

    logger = get_logger(__name__)

    with LogContext(market="kr", phase="prices"):
        logger.info("Starting price collection", batch_size=100)
        # Output: {"timestamp": "...", "market": "kr", "phase": "prices", "message": "...", "batch_size": 100}
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass
class LogContext:
    """Context for structured logging.

    Attributes are automatically included in all log messages
    within this context.
    """

    market: str | None = None
    phase: str | None = None
    ticker: str | None = None
    source: str | None = None
    batch_index: int | None = None
    batch_size: int | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


# Context variable to store current log context
_log_context: contextvars.ContextVar[LogContext] = contextvars.ContextVar(
    "log_context",
    default=LogContext(),
)


class _ContextManager:
    """Context manager for setting log context."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.token: contextvars.Token[LogContext] | None = None

    def __enter__(self) -> LogContext:
        current = _log_context.get()
        # Merge with current context
        new_context = LogContext(
            market=self.kwargs.get("market", current.market),
            phase=self.kwargs.get("phase", current.phase),
            ticker=self.kwargs.get("ticker", current.ticker),
            source=self.kwargs.get("source", current.source),
            batch_index=self.kwargs.get("batch_index", current.batch_index),
            batch_size=self.kwargs.get("batch_size", current.batch_size),
            correlation_id=self.kwargs.get("correlation_id", current.correlation_id),
        )
        self.token = _log_context.set(new_context)
        return new_context

    def __exit__(self, *args: Any) -> None:
        if self.token is not None:
            _log_context.reset(self.token)


def log_context(**kwargs: Any) -> _ContextManager:
    """Create a context manager for setting log context.

    Args:
        **kwargs: Context fields to set (market, phase, ticker, etc.)

    Returns:
        Context manager that sets the context

    Example:
        with log_context(market="kr", phase="prices"):
            logger.info("Starting collection")
    """
    return _ContextManager(**kwargs)


class StructuredFormatter(logging.Formatter):
    """JSON formatter with context support."""

    def format(self, record: logging.LogRecord) -> str:
        # Get current context
        ctx = _log_context.get()

        # Build log entry
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context fields
        entry.update(ctx.to_dict())

        # Add extra fields from the log record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "taskName",
                    "message",
                }:
                    entry[key] = value

        # Add exception info if present
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str, ensure_ascii=False)


class PrettyFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ctx = _log_context.get()

        # Color for level
        color = self.COLORS.get(record.levelname, "")

        # Build prefix from context
        prefix_parts = []
        if ctx.market:
            prefix_parts.append(f"[{ctx.market.upper()}]")
        if ctx.phase:
            prefix_parts.append(f"[{ctx.phase}]")
        if ctx.ticker:
            prefix_parts.append(f"[{ctx.ticker}]")

        prefix = " ".join(prefix_parts)
        if prefix:
            prefix += " "

        # Format message
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname[:4]
        message = record.getMessage()

        # Add extra fields
        extras = []
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "taskName",
                    "message",
                }:
                    extras.append(f"{key}={value}")

        extra_str = " | " + ", ".join(extras) if extras else ""

        formatted = f"{timestamp} {color}{level}{self.RESET} {prefix}{message}{extra_str}"

        # Add exception if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


class StructuredLogger(logging.Logger):
    """Logger with structured logging support.

    Use the extra parameter to add custom fields:
        logger.info("Message", extra={"field": "value"})
    """

    pass  # Use standard Logger implementation


# Set the custom logger class
logging.setLoggerClass(StructuredLogger)

# Track if logging has been set up
_logging_configured = False


def setup_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    quiet: bool = False,
) -> None:
    """Set up logging for the pipeline.

    Args:
        level: Logging level (default: INFO)
        json_format: Use JSON format (default: False, use pretty format)
        quiet: Suppress all output except errors (default: False)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Get root logger for data-pipeline
    root = logging.getLogger("data_pipeline")
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR if quiet else level)

    # Set formatter
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(PrettyFormatter())

    root.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _logging_configured = True


def get_logger(name: str) -> StructuredLogger:
    """Get a logger for the given module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Configured logger instance
    """
    # Ensure logging is set up with defaults
    setup_logging()

    # Create logger under data_pipeline namespace
    if not name.startswith("data_pipeline"):
        name = f"data_pipeline.{name}"

    return logging.getLogger(name)  # type: ignore
