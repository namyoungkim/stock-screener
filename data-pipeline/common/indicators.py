"""Technical indicator calculations for stock data.

This module contains all technical indicator functions used by both US and KR collectors.
All functions are pure and only depend on pandas DataFrames.
"""

import math

import pandas as pd


def calculate_graham_number(eps: float | None, bvps: float | None) -> float | None:
    """
    Calculate Graham Number = sqrt(22.5 * EPS * BVPS).

    The Graham Number is a figure that measures a stock's fundamental value
    by taking into account the company's earnings per share and book value per share.

    Args:
        eps: Earnings Per Share (must be positive)
        bvps: Book Value Per Share (must be positive)

    Returns:
        Graham Number or None if inputs are invalid
    """
    if eps is None or bvps is None:
        return None
    if eps <= 0 or bvps <= 0:
        return None
    return round(math.sqrt(22.5 * eps * bvps), 2)


def calculate_rsi(hist: pd.DataFrame, period: int = 14) -> float | None:
    """
    Calculate RSI (Relative Strength Index) from history DataFrame.

    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions.

    Args:
        hist: DataFrame with 'Close' column
        period: RSI period (default 14 days)

    Returns:
        RSI value (0-100) or None if calculation fails
    """
    try:
        if hist.empty or len(hist) < period + 1:
            return None

        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        if loss.iloc[-1] == 0:
            return 100.0 if gain.iloc[-1] > 0 else 50.0

        rs = gain.iloc[-1] / loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    except Exception:
        return None


def calculate_volume_change(hist: pd.DataFrame, period: int = 20) -> float | None:
    """
    Calculate volume change rate compared to moving average.

    Args:
        hist: DataFrame with 'Volume' column
        period: Period for average volume (default 20 days)

    Returns:
        Volume change rate as percentage or None if calculation fails
    """
    try:
        if hist.empty or len(hist) < period:
            return None

        avg_volume = hist["Volume"].iloc[-period:].mean()
        current_volume = hist["Volume"].iloc[-1]

        if avg_volume == 0:
            return None

        change_rate = ((current_volume / avg_volume) - 1) * 100
        return round(change_rate, 2)
    except Exception:
        return None


def calculate_macd(
    hist: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, float | None] | None:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD is a trend-following momentum indicator that shows the relationship
    between two moving averages of a security's price.

    Args:
        hist: DataFrame with 'Close' column
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)

    Returns:
        Dictionary with macd, macd_signal, macd_histogram values or None
    """
    try:
        if hist.empty or len(hist) < slow + signal:
            return None

        close = hist["Close"]

        # Calculate EMAs
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        # MACD Line
        macd_line = ema_fast - ema_slow

        # Signal Line (9-day EMA of MACD)
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        # Histogram
        histogram = macd_line - signal_line

        return {
            "macd": round(macd_line.iloc[-1], 4),
            "macd_signal": round(signal_line.iloc[-1], 4),
            "macd_histogram": round(histogram.iloc[-1], 4),
        }
    except Exception:
        return None


def calculate_bollinger_bands(
    hist: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, float | None] | None:
    """
    Calculate Bollinger Bands.

    Bollinger Bands are a volatility indicator that consists of a middle band
    (SMA) and an upper and lower band based on standard deviation.

    Args:
        hist: DataFrame with 'Close' column
        period: SMA period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)

    Returns:
        Dictionary with bb_upper, bb_middle, bb_lower, bb_percent values or None
    """
    try:
        if hist.empty or len(hist) < period:
            return None

        close = hist["Close"]

        # Middle Band (SMA)
        middle = close.rolling(window=period).mean()

        # Standard Deviation
        std = close.rolling(window=period).std()

        # Upper and Lower Bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        # %B indicator: (Price - Lower) / (Upper - Lower)
        current_price = close.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        middle_val = middle.iloc[-1]

        if upper_val == lower_val:
            percent_b = 0.5
        else:
            percent_b = (current_price - lower_val) / (upper_val - lower_val)

        return {
            "bb_upper": round(upper_val, 2),
            "bb_middle": round(middle_val, 2),
            "bb_lower": round(lower_val, 2),
            "bb_percent": round(percent_b * 100, 2),  # As percentage
        }
    except Exception:
        return None


def calculate_mfi(hist: pd.DataFrame, period: int = 14) -> float | None:
    """
    Calculate MFI (Money Flow Index).

    MFI is a momentum indicator that uses both price and volume data.
    It's also known as volume-weighted RSI.

    Args:
        hist: DataFrame with 'High', 'Low', 'Close', 'Volume' columns
        period: MFI period (default 14 days)

    Returns:
        MFI value (0-100) or None if calculation fails
    """
    try:
        if hist.empty or len(hist) < period + 1:
            return None

        # Typical Price = (High + Low + Close) / 3
        typical_price = (hist["High"] + hist["Low"] + hist["Close"]) / 3

        # Raw Money Flow = Typical Price x Volume
        raw_money_flow = typical_price * hist["Volume"]

        # Determine positive/negative money flow
        tp_diff = typical_price.diff()

        positive_flow = raw_money_flow.where(tp_diff > 0, 0)
        negative_flow = raw_money_flow.where(tp_diff < 0, 0)

        # Sum over period
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()

        # Money Flow Ratio
        mf_ratio = positive_mf / negative_mf.replace(0, float("inf"))

        # MFI = 100 - (100 / (1 + MFR))
        mfi = 100 - (100 / (1 + mf_ratio))

        result = mfi.iloc[-1]
        if pd.isna(result) or result == float("inf") or result == float("-inf"):
            return None

        return round(result, 2)
    except Exception:
        return None


def calculate_price_to_52w_high_pct(
    current_price: float | None,
    fifty_two_week_high: float | None,
) -> float | None:
    """
    Calculate current price as percentage of 52-week high.

    Used for momentum screening: stocks near 52-week high (>=90%) are in strong uptrend.

    Args:
        current_price: Current stock price
        fifty_two_week_high: 52-week high price

    Returns:
        Percentage (0-100+) or None if inputs are invalid
        Example: 95.5 means current price is 95.5% of 52-week high
    """
    if current_price is None or fifty_two_week_high is None:
        return None
    if fifty_two_week_high <= 0:
        return None
    return round((current_price / fifty_two_week_high) * 100, 2)


def calculate_ma_trend(
    fifty_day_average: float | None,
    two_hundred_day_average: float | None,
) -> float | None:
    """
    Calculate MA trend: difference between MA50 and MA200 as percentage.

    Positive value = Golden Cross (bullish): MA50 > MA200
    Negative value = Death Cross (bearish): MA50 < MA200

    Args:
        fifty_day_average: 50-day moving average
        two_hundred_day_average: 200-day moving average

    Returns:
        Percentage difference or None if inputs are invalid
        Example: 5.2 means MA50 is 5.2% above MA200 (bullish)
    """
    if fifty_day_average is None or two_hundred_day_average is None:
        return None
    if two_hundred_day_average <= 0:
        return None
    return round((fifty_day_average / two_hundred_day_average - 1) * 100, 2)


def calculate_all_technicals(hist: pd.DataFrame) -> dict:
    """
    Calculate all technical indicators from a single history DataFrame.

    This is the main entry point for calculating all technicals at once.
    It's more efficient than calling individual functions separately.

    Args:
        hist: DataFrame from yf.Ticker.history(period="3mo")
              Must have columns: Open, High, Low, Close, Volume

    Returns:
        Dictionary with all technical indicator values:
        - rsi: RSI (14-day)
        - volume_change: Volume change rate (%)
        - macd: MACD line
        - macd_signal: MACD signal line
        - macd_histogram: MACD histogram
        - bb_upper: Bollinger upper band
        - bb_middle: Bollinger middle band (SMA20)
        - bb_lower: Bollinger lower band
        - bb_percent: Bollinger %B
        - mfi: Money Flow Index
    """
    result = {
        "rsi": calculate_rsi(hist),
        "volume_change": calculate_volume_change(hist),
        "mfi": calculate_mfi(hist),
    }

    # Add MACD values
    macd_values = calculate_macd(hist)
    if macd_values:
        result.update(macd_values)
    else:
        result.update({"macd": None, "macd_signal": None, "macd_histogram": None})

    # Add Bollinger Bands values
    bb_values = calculate_bollinger_bands(hist)
    if bb_values:
        result.update(bb_values)
    else:
        result.update(
            {"bb_upper": None, "bb_middle": None, "bb_lower": None, "bb_percent": None}
        )

    return result
