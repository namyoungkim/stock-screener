"""Rate limit detection and handling utilities.

This module provides utilities for detecting and handling yfinance rate limits,
including timeout wrappers to prevent deadlocks from unresponsive API calls.
"""

import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

import yfinance as yf

from .config import (
    DATA_DIR,
    YFINANCE_HISTORY_TIMEOUT,
    YFINANCE_INFO_TIMEOUT,
)


class RateLimitError(Exception):
    """Raised when yfinance rate limit is detected."""

    pass


class YFinanceTimeoutError(Exception):
    """Raised when yfinance call times out."""

    pass


def run_with_timeout(func: Callable[..., Any], timeout: float, *args: Any, **kwargs: Any) -> Any:
    """
    Run a function with a timeout using ThreadPoolExecutor.

    Args:
        func: Function to execute
        timeout: Timeout in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of func(*args, **kwargs)

    Raises:
        YFinanceTimeoutError: If function doesn't complete within timeout
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as err:
            func_name = getattr(func, "__name__", "unknown")
            raise YFinanceTimeoutError(
                f"Function {func_name} timed out after {timeout}s"
            ) from err


def get_stock_info_with_timeout(
    stock: yf.Ticker,
    timeout: float = YFINANCE_INFO_TIMEOUT,
) -> dict[str, Any] | None:
    """
    Get stock.info with timeout protection.

    Args:
        stock: yfinance Ticker object
        timeout: Timeout in seconds (default: YFINANCE_INFO_TIMEOUT)

    Returns:
        Stock info dict or None if failed/timeout

    Raises:
        YFinanceTimeoutError: If call times out
    """
    try:
        return run_with_timeout(lambda: stock.info, timeout)
    except YFinanceTimeoutError:
        raise
    except Exception:
        return None


def get_stock_history_with_timeout(
    stock: yf.Ticker,
    period: str = "2mo",
    timeout: float = YFINANCE_HISTORY_TIMEOUT,
):
    """
    Get stock.history with timeout protection.

    Args:
        stock: yfinance Ticker object
        period: History period (default: "2mo")
        timeout: Timeout in seconds (default: YFINANCE_HISTORY_TIMEOUT)

    Returns:
        DataFrame with history or empty DataFrame if failed/timeout

    Raises:
        YFinanceTimeoutError: If call times out
    """
    import pandas as pd

    try:
        return run_with_timeout(lambda: stock.history(period=period), timeout)
    except YFinanceTimeoutError:
        raise
    except Exception:
        return pd.DataFrame()


def check_rate_limit(test_ticker: str = "AAPL") -> bool:
    """
    Check if we're currently rate limited by yfinance.

    Args:
        test_ticker: Ticker to use for testing (default: AAPL)

    Returns:
        True if rate limited, False if OK
    """
    try:
        ticker = yf.Ticker(test_ticker)
        info = ticker.info
        # If we can get info, we're not rate limited
        return info is None or len(info) == 0
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "too many requests" in error_msg:
            return True
        # Other errors might also indicate rate limiting
        return "429" in error_msg


def wait_for_rate_limit_reset(
    check_interval: int = 60,
    max_wait: int = 1800,
    test_ticker: str = "AAPL",
) -> bool:
    """
    Wait for rate limit to reset.

    Args:
        check_interval: Seconds between checks (default: 60)
        max_wait: Maximum seconds to wait (default: 1800 = 30 min)
        test_ticker: Ticker to use for testing

    Returns:
        True if rate limit cleared, False if max_wait exceeded
    """
    waited = 0
    while waited < max_wait:
        if not check_rate_limit(test_ticker):
            return True
        print(f"Rate limited. Waiting {check_interval}s... (total waited: {waited}s)")
        time.sleep(check_interval)
        waited += check_interval
    return False


class ProgressTracker:
    """Track collection progress for resume functionality."""

    def __init__(self, market_prefix: str, data_dir: Path = DATA_DIR):
        """
        Initialize progress tracker.

        Args:
            market_prefix: "us" or "kr"
            data_dir: Directory to save progress files
        """
        self.market_prefix = market_prefix
        self.data_dir = data_dir
        self.progress_file = data_dir / f"{market_prefix}_progress.txt"
        self.completed_tickers: set[str] = set()
        self._load_progress()

    def _load_progress(self) -> None:
        """Load previously completed tickers."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                self.completed_tickers = set(line.strip() for line in f if line.strip())

    def mark_completed(self, ticker: str) -> None:
        """Mark a ticker as completed."""
        self.completed_tickers.add(ticker)

    def save_progress(self) -> None:
        """Save progress to file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, "w") as f:
            for ticker in sorted(self.completed_tickers):
                f.write(f"{ticker}\n")

    def get_remaining(self, all_tickers: list[str]) -> list[str]:
        """Get tickers that haven't been completed yet."""
        return [t for t in all_tickers if t not in self.completed_tickers]

    def clear_progress(self) -> None:
        """Clear all progress (start fresh)."""
        self.completed_tickers.clear()
        if self.progress_file.exists():
            self.progress_file.unlink()

    @property
    def count(self) -> int:
        """Number of completed tickers."""
        return len(self.completed_tickers)


def handle_rate_limit_exit(
    market_prefix: str,
    completed_count: int,
    total_count: int,
    message: str = "",
) -> None:
    """
    Handle rate limit by printing message and exiting gracefully.

    Args:
        market_prefix: "us" or "kr"
        completed_count: Number of tickers completed
        total_count: Total number of tickers
        message: Additional message to display
    """
    print("\n" + "=" * 60)
    print("RATE LIMIT DETECTED")
    print("=" * 60)
    print(f"Market: {market_prefix.upper()}")
    print(f"Progress: {completed_count}/{total_count} tickers completed")
    print(f"Progress saved to: data/{market_prefix}_progress.txt")
    print()
    print("To resume collection after rate limit resets:")
    print(f"  ./scripts/collect-and-backup.sh {market_prefix}")
    print()
    print("Or wait and retry:")
    print("  - Usually resets in 15-30 minutes")
    print("  - Try using a different network/VPN")
    if message:
        print()
        print(f"Details: {message}")
    print("=" * 60)
    sys.exit(2)  # Exit code 2 = rate limit
