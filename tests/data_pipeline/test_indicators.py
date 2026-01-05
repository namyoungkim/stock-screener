"""Tests for data_pipeline/common/indicators.py.

TDD approach: Testing all technical indicator calculations.
Pure functions - no mocking required.
"""

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

# Add data-pipeline to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "data-pipeline"))

from common.indicators import (
    calculate_52_week_high_low,
    calculate_all_technicals,
    calculate_beta,
    calculate_bollinger_bands,
    calculate_graham_number,
    calculate_ma_trend,
    calculate_macd,
    calculate_mfi,
    calculate_moving_averages,
    calculate_price_to_52w_high_pct,
    calculate_rsi,
    calculate_volume_change,
)


# =============================================================================
# Step 2: Pure Function Tests (no DataFrame required)
# =============================================================================


class TestCalculateGrahamNumber:
    """Tests for calculate_graham_number()."""

    def test_normal_case(self):
        """Graham Number with valid positive EPS and BVPS."""
        # Graham Number = sqrt(22.5 * EPS * BVPS)
        # sqrt(22.5 * 5 * 20) = sqrt(2250) = 47.43
        result = calculate_graham_number(eps=5.0, bvps=20.0)
        assert result == 47.43

    def test_another_normal_case(self):
        """Test with different values."""
        # sqrt(22.5 * 10 * 50) = sqrt(11250) = 106.07
        result = calculate_graham_number(eps=10.0, bvps=50.0)
        assert result == 106.07

    def test_none_eps(self):
        """Returns None when EPS is None."""
        result = calculate_graham_number(eps=None, bvps=20.0)
        assert result is None

    def test_none_bvps(self):
        """Returns None when BVPS is None."""
        result = calculate_graham_number(eps=5.0, bvps=None)
        assert result is None

    def test_both_none(self):
        """Returns None when both are None."""
        result = calculate_graham_number(eps=None, bvps=None)
        assert result is None

    def test_negative_eps(self):
        """Returns None for negative EPS (unprofitable company)."""
        result = calculate_graham_number(eps=-5.0, bvps=20.0)
        assert result is None

    def test_negative_bvps(self):
        """Returns None for negative BVPS (negative equity)."""
        result = calculate_graham_number(eps=5.0, bvps=-20.0)
        assert result is None

    def test_zero_eps(self):
        """Returns None for zero EPS."""
        result = calculate_graham_number(eps=0.0, bvps=20.0)
        assert result is None

    def test_zero_bvps(self):
        """Returns None for zero BVPS."""
        result = calculate_graham_number(eps=5.0, bvps=0.0)
        assert result is None


class TestCalculatePriceTo52wHighPct:
    """Tests for calculate_price_to_52w_high_pct()."""

    def test_at_52w_high(self):
        """Price equals 52-week high = 100%."""
        result = calculate_price_to_52w_high_pct(100.0, 100.0)
        assert result == 100.0

    def test_below_52w_high(self):
        """Price 10% below 52-week high."""
        result = calculate_price_to_52w_high_pct(90.0, 100.0)
        assert result == 90.0

    def test_well_below_52w_high(self):
        """Price significantly below 52-week high."""
        result = calculate_price_to_52w_high_pct(50.0, 100.0)
        assert result == 50.0

    def test_none_current_price(self):
        """Returns None when current price is None."""
        result = calculate_price_to_52w_high_pct(None, 100.0)
        assert result is None

    def test_none_52w_high(self):
        """Returns None when 52-week high is None."""
        result = calculate_price_to_52w_high_pct(90.0, None)
        assert result is None

    def test_zero_52w_high(self):
        """Returns None when 52-week high is zero."""
        result = calculate_price_to_52w_high_pct(90.0, 0.0)
        assert result is None

    def test_negative_52w_high(self):
        """Returns None for negative 52-week high."""
        result = calculate_price_to_52w_high_pct(90.0, -100.0)
        assert result is None


class TestCalculateMaTrend:
    """Tests for calculate_ma_trend()."""

    def test_golden_cross(self):
        """MA50 above MA200 (bullish) = positive value."""
        # (105 / 100 - 1) * 100 = 5%
        result = calculate_ma_trend(105.0, 100.0)
        assert result == 5.0

    def test_death_cross(self):
        """MA50 below MA200 (bearish) = negative value."""
        # (95 / 100 - 1) * 100 = -5%
        result = calculate_ma_trend(95.0, 100.0)
        assert result == -5.0

    def test_equal_averages(self):
        """MA50 equals MA200 = 0%."""
        result = calculate_ma_trend(100.0, 100.0)
        assert result == 0.0

    def test_none_ma50(self):
        """Returns None when MA50 is None."""
        result = calculate_ma_trend(None, 100.0)
        assert result is None

    def test_none_ma200(self):
        """Returns None when MA200 is None."""
        result = calculate_ma_trend(100.0, None)
        assert result is None

    def test_zero_ma200(self):
        """Returns None when MA200 is zero."""
        result = calculate_ma_trend(100.0, 0.0)
        assert result is None


# =============================================================================
# Step 3: DataFrame Input Function Tests
# =============================================================================


class TestCalculateRsi:
    """Tests for calculate_rsi()."""

    def test_normal_case(self, sample_ohlcv_df):
        """RSI calculation with sufficient data."""
        result = calculate_rsi(sample_ohlcv_df)
        assert result is not None
        assert 0 <= result <= 100

    def test_uptrend_high_rsi(self, sample_uptrend_df):
        """Uptrend should have RSI > 50."""
        result = calculate_rsi(sample_uptrend_df)
        assert result is not None
        assert result > 50, f"Expected RSI > 50 in uptrend, got {result}"

    def test_downtrend_low_rsi(self, sample_downtrend_df):
        """Downtrend should have RSI < 50."""
        result = calculate_rsi(sample_downtrend_df)
        assert result is not None
        assert result < 50, f"Expected RSI < 50 in downtrend, got {result}"

    def test_empty_dataframe(self, sample_empty_df):
        """Returns None for empty DataFrame."""
        result = calculate_rsi(sample_empty_df)
        assert result is None

    def test_insufficient_data(self, sample_short_df):
        """Returns None when data is insufficient (< period + 1)."""
        result = calculate_rsi(sample_short_df, period=14)
        assert result is None

    def test_custom_period(self, sample_ohlcv_df):
        """RSI with custom period."""
        result = calculate_rsi(sample_ohlcv_df, period=7)
        assert result is not None
        assert 0 <= result <= 100


class TestCalculateVolumeChange:
    """Tests for calculate_volume_change()."""

    def test_normal_case(self, sample_ohlcv_df):
        """Volume change calculation."""
        result = calculate_volume_change(sample_ohlcv_df)
        assert result is not None
        # Result is percentage, can be negative or positive

    def test_empty_dataframe(self, sample_empty_df):
        """Returns None for empty DataFrame."""
        result = calculate_volume_change(sample_empty_df)
        assert result is None

    def test_insufficient_data(self, sample_short_df):
        """Returns None when data is insufficient."""
        result = calculate_volume_change(sample_short_df, period=20)
        assert result is None

    def test_zero_volume(self):
        """Returns None when average volume is zero."""
        df = pd.DataFrame(
            {
                "Volume": [0] * 25,
            }
        )
        result = calculate_volume_change(df)
        assert result is None


class TestCalculateMacd:
    """Tests for calculate_macd()."""

    def test_normal_case(self, sample_ohlcv_df):
        """MACD calculation with sufficient data."""
        result = calculate_macd(sample_ohlcv_df)
        assert result is not None
        assert "macd" in result
        assert "macd_signal" in result
        assert "macd_histogram" in result

    def test_empty_dataframe(self, sample_empty_df):
        """Returns None for empty DataFrame."""
        result = calculate_macd(sample_empty_df)
        assert result is None

    def test_insufficient_data(self, sample_short_df):
        """Returns None when data is insufficient (< slow + signal)."""
        result = calculate_macd(sample_short_df)
        assert result is None

    def test_histogram_equals_difference(self, sample_ohlcv_df):
        """MACD histogram = MACD - Signal."""
        result = calculate_macd(sample_ohlcv_df)
        if result:
            expected_hist = round(result["macd"] - result["macd_signal"], 4)
            assert result["macd_histogram"] == expected_hist


class TestCalculateBollingerBands:
    """Tests for calculate_bollinger_bands()."""

    def test_normal_case(self, sample_ohlcv_df):
        """Bollinger Bands calculation."""
        result = calculate_bollinger_bands(sample_ohlcv_df)
        assert result is not None
        assert "bb_upper" in result
        assert "bb_middle" in result
        assert "bb_lower" in result
        assert "bb_percent" in result

    def test_band_order(self, sample_ohlcv_df):
        """Upper > Middle > Lower."""
        result = calculate_bollinger_bands(sample_ohlcv_df)
        if result:
            assert result["bb_upper"] >= result["bb_middle"]
            assert result["bb_middle"] >= result["bb_lower"]

    def test_empty_dataframe(self, sample_empty_df):
        """Returns None for empty DataFrame."""
        result = calculate_bollinger_bands(sample_empty_df)
        assert result is None

    def test_insufficient_data(self, sample_short_df):
        """Returns None when data is insufficient."""
        result = calculate_bollinger_bands(sample_short_df, period=20)
        assert result is None


class TestCalculateMfi:
    """Tests for calculate_mfi()."""

    def test_normal_case(self, sample_ohlcv_df):
        """MFI calculation with sufficient data."""
        result = calculate_mfi(sample_ohlcv_df)
        assert result is not None
        assert 0 <= result <= 100

    def test_empty_dataframe(self, sample_empty_df):
        """Returns None for empty DataFrame."""
        result = calculate_mfi(sample_empty_df)
        assert result is None

    def test_insufficient_data(self, sample_short_df):
        """Returns None when data is insufficient."""
        result = calculate_mfi(sample_short_df, period=14)
        assert result is None


class TestCalculateMovingAverages:
    """Tests for calculate_moving_averages()."""

    def test_short_ma_only(self, sample_ohlcv_df):
        """50-day data gives MA50 but not MA200."""
        result = calculate_moving_averages(sample_ohlcv_df)
        ma50, ma200 = result
        assert ma50 is not None
        assert ma200 is None  # Not enough data for 200-day

    def test_both_averages(self, sample_long_df):
        """300-day data gives both MA50 and MA200."""
        result = calculate_moving_averages(sample_long_df)
        ma50, ma200 = result
        assert ma50 is not None
        assert ma200 is not None

    def test_empty_dataframe(self, sample_empty_df):
        """Returns (None, None) for empty DataFrame."""
        result = calculate_moving_averages(sample_empty_df)
        assert result == (None, None)

    def test_insufficient_data(self, sample_short_df):
        """Returns (None, None) when data is insufficient for MA50."""
        result = calculate_moving_averages(sample_short_df)
        ma50, ma200 = result
        assert ma50 is None
        assert ma200 is None


class TestCalculate52WeekHighLow:
    """Tests for calculate_52_week_high_low()."""

    def test_normal_case(self, sample_ohlcv_df):
        """52-week high/low calculation."""
        high, low = calculate_52_week_high_low(sample_ohlcv_df)
        assert high is not None
        assert low is not None
        assert high >= low

    def test_long_data(self, sample_long_df):
        """Uses last 252 days for 1-year calculation."""
        high, low = calculate_52_week_high_low(sample_long_df)
        assert high is not None
        assert low is not None

    def test_empty_dataframe(self, sample_empty_df):
        """Returns (None, None) for empty DataFrame."""
        result = calculate_52_week_high_low(sample_empty_df)
        assert result == (None, None)


# =============================================================================
# Step 4: Complex Function Tests
# =============================================================================


class TestCalculateBeta:
    """Tests for calculate_beta()."""

    def test_normal_case(self, sample_long_df, sample_market_df):
        """Beta calculation with sufficient overlapping data."""
        result = calculate_beta(sample_long_df, sample_market_df)
        assert result is not None
        # Beta typically ranges from -2 to 3 for most stocks
        assert -3 <= result <= 5

    def test_empty_stock_df(self, sample_empty_df, sample_market_df):
        """Returns None for empty stock DataFrame."""
        result = calculate_beta(sample_empty_df, sample_market_df)
        assert result is None

    def test_empty_market_df(self, sample_long_df, sample_empty_df):
        """Returns None for empty market DataFrame."""
        result = calculate_beta(sample_long_df, sample_empty_df)
        assert result is None

    def test_insufficient_common_dates(self, sample_short_df, sample_market_df):
        """Returns None when common dates < 30."""
        result = calculate_beta(sample_short_df, sample_market_df)
        assert result is None


class TestCalculateAllTechnicals:
    """Tests for calculate_all_technicals() - integration test."""

    def test_returns_all_keys(self, sample_ohlcv_df):
        """Returns dictionary with all technical indicators."""
        result = calculate_all_technicals(sample_ohlcv_df)

        expected_keys = [
            "rsi",
            "volume_change",
            "mfi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_percent",
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_with_sufficient_data(self, sample_ohlcv_df):
        """All indicators calculated with sufficient data."""
        result = calculate_all_technicals(sample_ohlcv_df)

        # These should have values with 50 days of data
        assert result["rsi"] is not None
        assert result["volume_change"] is not None
        assert result["bb_middle"] is not None

    def test_empty_dataframe(self, sample_empty_df):
        """Handles empty DataFrame gracefully."""
        result = calculate_all_technicals(sample_empty_df)

        # All values should be None
        assert result["rsi"] is None
        assert result["macd"] is None
        assert result["bb_upper"] is None
