"""Technical indicator calculations for stock data.

This module contains all technical indicator functions used by both US and KR collectors.
All functions are pure and only depend on pandas DataFrames.
"""

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)


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
    except Exception as e:
        logger.debug(f"RSI calculation failed: {e}")
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
    except Exception as e:
        logger.debug(f"Volume change calculation failed: {e}")
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
    except Exception as e:
        logger.debug(f"MACD calculation failed: {e}")
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
    except Exception as e:
        logger.debug(f"Bollinger Bands calculation failed: {e}")
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
    except Exception as e:
        logger.debug(f"MFI calculation failed: {e}")
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


def calculate_moving_averages(
    hist: pd.DataFrame,
    short_period: int = 50,
    long_period: int = 200,
) -> tuple[float | None, float | None]:
    """
    Calculate short and long-term moving averages.

    Args:
        hist: DataFrame with 'Close' column
        short_period: Short-term MA period (default 50 days)
        long_period: Long-term MA period (default 200 days)

    Returns:
        Tuple of (short_ma, long_ma) values or (None, None) if calculation fails
    """
    try:
        if hist.empty:
            return None, None

        close = hist["Close"]

        short_ma = None
        long_ma = None

        if len(close) >= short_period:
            short_ma = round(close.iloc[-short_period:].mean(), 2)

        if len(close) >= long_period:
            long_ma = round(close.iloc[-long_period:].mean(), 2)

        return short_ma, long_ma
    except Exception as e:
        logger.debug(f"Moving averages calculation failed: {e}")
        return None, None


def calculate_beta(
    stock_hist: pd.DataFrame,
    market_hist: pd.DataFrame,
    period: int = 252,
) -> float | None:
    """
    Calculate Beta relative to a market index.

    Beta measures the volatility of a stock relative to the overall market.
    Beta > 1 means more volatile than market, Beta < 1 means less volatile.

    Uses linear regression: Covariance(stock, market) / Variance(market)

    Args:
        stock_hist: Stock DataFrame with 'Close' column
        market_hist: Market index DataFrame with 'Close' column
                     (handles MultiIndex columns from yf.download)
        period: Number of trading days to use (default 252 = 1 year)

    Returns:
        Beta value or None if calculation fails
    """
    try:
        if stock_hist.empty or market_hist.empty:
            return None

        # Helper to extract Close column (handles MultiIndex from yfinance)
        def get_close(df: pd.DataFrame) -> pd.Series:
            if "Close" in df.columns:
                close = df["Close"]
                # If it's a DataFrame (MultiIndex), get first column
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                return close
            return pd.Series(dtype=float)

        stock_close = get_close(stock_hist)
        market_close = get_close(market_hist)

        if stock_close.empty or market_close.empty:
            return None

        # Limit to period
        stock_close = stock_close.iloc[-period:] if len(stock_close) >= period else stock_close
        market_close = market_close.iloc[-period:] if len(market_close) >= period else market_close

        # Calculate daily returns
        stock_returns = stock_close.pct_change().dropna()
        market_returns = market_close.pct_change().dropna()

        # Find common dates
        common_idx = stock_returns.index.intersection(market_returns.index)
        if len(common_idx) < 30:  # Need at least 30 data points
            return None

        stock_returns = stock_returns.loc[common_idx]
        market_returns = market_returns.loc[common_idx]

        # Calculate covariance and variance
        covariance = stock_returns.cov(market_returns)
        variance = market_returns.var()

        if variance == 0:
            return None

        beta = covariance / variance
        return round(beta, 4)
    except Exception as e:
        logger.debug(f"Beta calculation failed: {e}")
        return None


def calculate_52_week_high_low(hist: pd.DataFrame) -> tuple[float | None, float | None]:
    """
    Calculate 52-week high and low from history DataFrame.

    Args:
        hist: DataFrame with 'High' and 'Low' columns (needs ~1 year of data)

    Returns:
        Tuple of (high_52w, low_52w) or (None, None) if calculation fails
    """
    try:
        if hist.empty:
            return None, None

        # Use last 252 trading days (approximately 1 year)
        period = min(252, len(hist))
        recent = hist.iloc[-period:]

        high_52w = recent["High"].max() if "High" in recent.columns else None
        low_52w = recent["Low"].min() if "Low" in recent.columns else None

        if pd.notna(high_52w) and high_52w is not None:
            high_52w = round(float(high_52w), 2)
        else:
            high_52w = None
        if pd.notna(low_52w) and low_52w is not None:
            low_52w = round(float(low_52w), 2)
        else:
            low_52w = None

        return high_52w, low_52w
    except Exception as e:
        logger.debug(f"52-week high/low calculation failed: {e}")
        return None, None


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
