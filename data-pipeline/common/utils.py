"""Common utility functions for data pipeline.

This module provides shared utilities used across the data pipeline:
- safe_float, safe_int: Type conversion with NaN/Inf handling
- get_supabase_client: Supabase client initialization
"""

import math
import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

    return create_client(url, key)


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
