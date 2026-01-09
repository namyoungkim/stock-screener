"""Data validation for stock metrics.

This module provides validation rules and a validator class for ensuring
data quality before saving to database.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Validation rule for a single field."""

    field: str
    min_value: float | None = None
    max_value: float | None = None
    max_abs: float | None = (
        None  # Maximum absolute value (for numeric overflow prevention)
    )
    warn_only: bool = (
        True  # If True, log warning but keep value. If False, set to None.
    )


# Default validation rules based on Supabase schema constraints
# and reasonable financial metric ranges
DEFAULT_RULES: dict[str, ValidationRule] = {
    # Valuation ratios - can be negative but should be within reason
    # Note: inf values from zero earnings/revenue will be converted to None
    "pe_ratio": ValidationRule(
        "pe_ratio", min_value=-1000, max_value=10000, max_abs=1e6, warn_only=False
    ),
    "pb_ratio": ValidationRule(
        "pb_ratio", min_value=-500, max_value=500, max_abs=1e6
    ),  # Allow negative PB for companies with negative book value
    "ps_ratio": ValidationRule(
        "ps_ratio", min_value=0, max_value=1000, max_abs=1e6, warn_only=False
    ),
    "ev_ebitda": ValidationRule(
        "ev_ebitda", min_value=-100, max_value=1000, max_abs=1e7
    ),
    "peg_ratio": ValidationRule(
        "peg_ratio", min_value=-100, max_value=100, max_abs=1e4
    ),
    # Profitability ratios (as decimals, e.g., 0.15 = 15%)
    "roe": ValidationRule(
        "roe", min_value=-10, max_value=10, max_abs=1e3
    ),  # -1000% to 1000%
    "roa": ValidationRule("roa", min_value=-10, max_value=10, max_abs=1e3),
    "gross_margin": ValidationRule(
        "gross_margin", min_value=-10, max_value=10, max_abs=1e3
    ),
    "net_margin": ValidationRule(
        "net_margin", min_value=-10, max_value=10, max_abs=1e3
    ),
    # Financial health
    "debt_equity": ValidationRule(
        "debt_equity", min_value=0, max_value=1000, max_abs=1e7
    ),
    "current_ratio": ValidationRule(
        "current_ratio", min_value=0, max_value=100, max_abs=1e7
    ),
    # Other ratios
    # Note: yfinance returns dividend_yield as percentage (e.g., 3.5 = 3.5%)
    # Allow up to 30% yield (some REITs/MLPs can have high yields)
    "dividend_yield": ValidationRule(
        "dividend_yield", min_value=0, max_value=30, max_abs=1e2
    ),  # 0-30%
    "beta": ValidationRule("beta", min_value=-10, max_value=10, max_abs=1e3),
    # Technical indicators with strict ranges
    "rsi": ValidationRule(
        "rsi", min_value=0, max_value=100, max_abs=1e2, warn_only=False
    ),
    "mfi": ValidationRule(
        "mfi", min_value=0, max_value=100, max_abs=1e2, warn_only=False
    ),
    "volume_change": ValidationRule(
        "volume_change", min_value=-100, max_value=10000, max_abs=1e4
    ),
    "bb_percent": ValidationRule(
        "bb_percent", min_value=-100, max_value=200, max_abs=1e3
    ),
    # Price-based columns (large values allowed)
    "macd": ValidationRule("macd", max_abs=1e11),
    "macd_signal": ValidationRule("macd_signal", max_abs=1e11),
    "macd_histogram": ValidationRule("macd_histogram", max_abs=1e11),
    "fifty_two_week_high": ValidationRule(
        "fifty_two_week_high", min_value=0, max_abs=1e11
    ),
    "fifty_two_week_low": ValidationRule(
        "fifty_two_week_low", min_value=0, max_abs=1e11
    ),
    "fifty_day_average": ValidationRule("fifty_day_average", min_value=0, max_abs=1e11),
    "two_hundred_day_average": ValidationRule(
        "two_hundred_day_average", min_value=0, max_abs=1e11
    ),
    "bb_upper": ValidationRule("bb_upper", min_value=0, max_abs=1e11),
    "bb_middle": ValidationRule("bb_middle", min_value=0, max_abs=1e11),
    "bb_lower": ValidationRule("bb_lower", min_value=0, max_abs=1e11),
    "eps": ValidationRule("eps", max_abs=1e7),
    "book_value_per_share": ValidationRule("book_value_per_share", max_abs=1e11),
    "graham_number": ValidationRule("graham_number", min_value=0, max_abs=1e11),
}


@dataclass
class ValidationResult:
    """Result of validation for a single record."""

    ticker: str
    is_valid: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    modified_fields: list[str] = field(default_factory=list)


class MetricsValidator:
    """Validator for stock metrics data."""

    def __init__(self, rules: dict[str, ValidationRule] | None = None):
        """
        Initialize validator with rules.

        Args:
            rules: Custom validation rules (uses DEFAULT_RULES if None)
        """
        self.rules = rules or DEFAULT_RULES
        self.results: list[ValidationResult] = []

    def _is_valid_number(self, value: Any) -> bool:
        """Check if value is a valid number (not None, nan, or inf)."""
        if value is None:
            return False
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return False
        if isinstance(value, pd.Series):
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _safe_float(self, value: Any) -> float | None:
        """Convert value to float safely."""
        if not self._is_valid_number(value):
            return None
        return float(value)

    def validate(self, metrics: dict, ticker: str = "UNKNOWN") -> dict:
        """
        Validate and clean metrics dictionary.

        Args:
            metrics: Dictionary of metric values
            ticker: Ticker symbol for logging

        Returns:
            Cleaned metrics dictionary with invalid values set to None
        """
        result = ValidationResult(ticker=ticker, is_valid=True)
        cleaned = metrics.copy()

        for field_name, value in metrics.items():
            if field_name not in self.rules:
                continue

            rule = self.rules[field_name]

            # Convert to safe float
            safe_value = self._safe_float(value)

            if safe_value is None:
                if value is not None:
                    # Value was invalid (nan, inf, etc.)
                    result.warnings.append(
                        f"{field_name}: Invalid value {value} -> None"
                    )
                    cleaned[field_name] = None
                    result.modified_fields.append(field_name)
                continue

            # Check max_abs (numeric overflow prevention)
            if rule.max_abs is not None and abs(safe_value) >= rule.max_abs:
                msg = f"{field_name}: Value {safe_value} exceeds max_abs {rule.max_abs}"
                if rule.warn_only:
                    result.warnings.append(msg)
                else:
                    result.errors.append(msg)
                    cleaned[field_name] = None
                    result.modified_fields.append(field_name)
                    result.is_valid = False
                continue

            # Check min_value
            if rule.min_value is not None and safe_value < rule.min_value:
                msg = f"{field_name}: Value {safe_value} below min {rule.min_value}"
                if rule.warn_only:
                    result.warnings.append(msg)
                else:
                    result.errors.append(msg)
                    cleaned[field_name] = None
                    result.modified_fields.append(field_name)
                    result.is_valid = False
                continue

            # Check max_value
            if rule.max_value is not None and safe_value > rule.max_value:
                msg = f"{field_name}: Value {safe_value} exceeds max {rule.max_value}"
                if rule.warn_only:
                    result.warnings.append(msg)
                else:
                    result.errors.append(msg)
                    cleaned[field_name] = None
                    result.modified_fields.append(field_name)
                    result.is_valid = False
                continue

            # Value is valid, ensure it's a proper float
            cleaned[field_name] = safe_value

        # Log warnings if any
        if result.warnings:
            logger.warning(
                f"[{ticker}] Validation warnings: {', '.join(result.warnings[:5])}"
            )
        if result.errors:
            logger.error(f"[{ticker}] Validation errors: {', '.join(result.errors)}")

        self.results.append(result)
        return cleaned

    def get_summary(self) -> dict:
        """Get validation summary statistics."""
        if not self.results:
            return {"total": 0, "valid": 0, "with_warnings": 0, "invalid": 0}

        valid_count = sum(1 for r in self.results if r.is_valid and not r.warnings)
        warning_count = sum(1 for r in self.results if r.is_valid and r.warnings)
        invalid_count = sum(1 for r in self.results if not r.is_valid)

        # Aggregate field warnings
        field_issues: dict[str, int] = {}
        for result in self.results:
            for warning in result.warnings + result.errors:
                field = warning.split(":")[0]
                field_issues[field] = field_issues.get(field, 0) + 1

        return {
            "total": len(self.results),
            "valid": valid_count,
            "with_warnings": warning_count,
            "invalid": invalid_count,
            "field_issues": dict(
                sorted(field_issues.items(), key=lambda x: -x[1])[:10]
            ),
        }

    def reset(self) -> None:
        """Reset validation results."""
        self.results = []
