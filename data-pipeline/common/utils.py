"""Common utility functions for data pipeline.

This module provides shared utilities used across the data pipeline:
- safe_float, safe_int: Type conversion with NaN/Inf handling
- get_supabase_client: Supabase client initialization
- socket_timeout: Context manager for temporary socket timeout
"""

import math
import os
import socket
from contextlib import contextmanager
from typing import Any, Generator

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


@contextmanager
def socket_timeout(timeout: float) -> Generator[None, None, None]:
    """Context manager to temporarily set socket timeout.

    Safely sets and restores socket timeout to avoid affecting other code.

    Usage:
        with socket_timeout(10.0):
            # code that needs timeout
            pass

    Args:
        timeout: Timeout in seconds
    """
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        yield
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

    return create_client(url, key)


def safe_float_series(series: pd.Series, max_abs: float | None = None) -> pd.Series:
    """
    Vectorized version of safe_float for pandas Series.

    Converts series to float, handling inf/nan values.

    Args:
        series: Pandas Series to convert
        max_abs: Optional maximum absolute value (values exceeding this become None)

    Returns:
        Series with float values or None for invalid values
    """
    # Convert to numeric, coercing errors to NaN
    result = pd.to_numeric(series, errors="coerce")

    # Replace inf with NaN
    result = result.replace([float("inf"), float("-inf")], pd.NA)

    # Apply max_abs filter if specified
    if max_abs is not None:
        result = result.where(result.abs() < max_abs, pd.NA)

    return result


def safe_float(value: Any, max_abs: float | None = None) -> float | None:
    """
    Convert value to JSON-safe float (handles inf/nan).

    Args:
        value: The value to convert
        max_abs: Optional maximum absolute value (returns None if exceeded)

    Returns:
        Float value or None if invalid
    """
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    try:
        result = float(value)
        if max_abs is not None and abs(result) >= max_abs:
            return None
        return result
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> int | None:
    """Convert value to int (handles nan)."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
