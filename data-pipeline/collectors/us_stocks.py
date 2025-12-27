"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.

Optimized for speed with:
- Batch yfinance calls (50 tickers at a time)
- ThreadPoolExecutor for parallel processing
"""

import math
import os
import random
import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from tqdm import tqdm

from supabase import Client, create_client


def calculate_graham_number(eps: float | None, bvps: float | None) -> float | None:
    """
    Calculate Graham Number = sqrt(22.5 * EPS * BVPS).

    Only valid when both EPS and BVPS are positive.
    """
    if eps is None or bvps is None:
        return None
    if eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def calculate_rsi(ticker_symbol: str, period: int = 14) -> float | None:
    """
    Calculate RSI (Relative Strength Index) for a ticker.

    Args:
        ticker_symbol: Stock ticker symbol
        period: RSI period (default 14 days)

    Returns:
        RSI value (0-100) or None if calculation fails
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(ticker_symbol)
        # Get 1 month of history to ensure enough data for 14-day RSI
        hist = ticker.history(period="1mo")

        if len(hist) < period + 1:
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


def calculate_volume_change(ticker_symbol: str, period: int = 20) -> float | None:
    """
    Calculate volume change rate compared to average volume.

    Args:
        ticker_symbol: Stock ticker symbol
        period: Period for average volume (default 20 days)

    Returns:
        Volume change rate as percentage (e.g., 50.0 means 50% above average)
        or None if calculation fails
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1mo")

        if len(hist) < period:
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
    ticker_symbol: str,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, float | None] | None:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        ticker_symbol: Stock ticker symbol
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)

    Returns:
        Dictionary with macd, signal, histogram values or None if calculation fails
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="3mo")  # Need enough data for 26-day EMA

        if len(hist) < slow + signal:
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
    ticker_symbol: str,
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, float | None] | None:
    """
    Calculate Bollinger Bands.

    Args:
        ticker_symbol: Stock ticker symbol
        period: SMA period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)

    Returns:
        Dictionary with upper, middle, lower bands and %B indicator
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="3mo")

        if len(hist) < period:
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


load_dotenv()

# Data directory for CSV exports
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
FINANCIALS_DIR = DATA_DIR / "financials"


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    return create_client(url, key)


def _fetch_wiki_tickers(url: str, index_name: str) -> list[str]:
    """Fetch tickers from Wikipedia table."""
    from io import StringIO

    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers)
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]

    # Column name might be 'Symbol' or 'Ticker'
    col = "Symbol" if "Symbol" in df.columns else "Ticker"
    tickers = df[col].str.replace(".", "-").tolist()
    print(f"Fetched {len(tickers)} {index_name} tickers")
    return tickers


def get_sp500_tickers() -> list[str]:
    """Get S&P 500 tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            "S&P 500",
        )
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        return []


def get_sp400_tickers() -> list[str]:
    """Get S&P 400 Mid Cap tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
            "S&P 400",
        )
    except Exception as e:
        print(f"Error fetching S&P 400: {e}")
        return []


def get_sp600_tickers() -> list[str]:
    """Get S&P 600 Small Cap tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
            "S&P 600",
        )
    except Exception as e:
        print(f"Error fetching S&P 600: {e}")
        return []


def get_russell2000_tickers() -> list[str]:
    """Get Russell 2000 tickers from iShares IWM ETF holdings."""
    try:
        # iShares Russell 2000 ETF holdings
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
        df = pd.read_csv(url, skiprows=9)

        # Filter to stocks only (exclude cash, futures, etc.)
        if "Asset Class" in df.columns:
            df = df[df["Asset Class"] == "Equity"]

        tickers = df["Ticker"].dropna().str.strip().tolist()
        # Clean up tickers
        tickers = [t for t in tickers if t and isinstance(t, str) and len(t) <= 5]
        print(f"Fetched {len(tickers)} Russell 2000 tickers")
        return tickers
    except Exception as e:
        print(f"Error fetching Russell 2000 from iShares: {e}")
        # Fallback: try alternative source
        try:
            # Alternative: use a static list or another source
            print("Trying alternative source for Russell 2000...")
            # For now, return empty - will implement alternative later
            return []
        except Exception:
            return []


def get_all_us_tickers() -> dict[str, list[str]]:
    """
    Get all US tickers with index membership.

    Returns:
        Dictionary mapping ticker to list of indices it belongs to.
        Example: {"AAPL": ["SP500"], "ACAD": ["SP600", "RUSSELL2000"]}
    """
    print("Fetching all US index tickers...")

    # Fetch from all indices
    sp500 = set(get_sp500_tickers())
    sp400 = set(get_sp400_tickers())
    sp600 = set(get_sp600_tickers())
    russell2000 = set(get_russell2000_tickers())

    # Build membership dictionary
    all_tickers: dict[str, list[str]] = {}

    for ticker in sp500:
        all_tickers.setdefault(ticker, []).append("SP500")

    for ticker in sp400:
        all_tickers.setdefault(ticker, []).append("SP400")

    for ticker in sp600:
        all_tickers.setdefault(ticker, []).append("SP600")

    for ticker in russell2000:
        all_tickers.setdefault(ticker, []).append("RUSSELL2000")

    print(f"\nTotal unique tickers: {len(all_tickers)}")
    print(f"  - S&P 500: {len(sp500)}")
    print(f"  - S&P 400: {len(sp400)}")
    print(f"  - S&P 600: {len(sp600)}")
    print(f"  - Russell 2000: {len(russell2000)}")

    return all_tickers


def get_stock_info(ticker: str) -> dict | None:
    """Get stock info using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


def get_financials(ticker: str) -> dict | None:
    """Get financial data using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "gross_margin": info.get("grossMargins"),
            "net_margin": info.get("profitMargins"),
            "fcf": info.get("freeCashflow"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception as e:
        print(f"Error fetching financials for {ticker}: {e}")
        return None


def get_single_stock_info(
    ticker: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> dict | None:
    """
    Fetch info for a single ticker with exponential backoff.

    Args:
        ticker: Stock ticker symbol
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
    """
    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if info and info.get("regularMarketPrice") is not None:
                eps = info.get("trailingEps")
                bvps = info.get("bookValue")
                return {
                    "name": info.get("longName"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "market_cap": info.get("marketCap"),
                    "currency": info.get("currency", "USD"),
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "ps_ratio": info.get("priceToSalesTrailing12Months"),
                    "ev_ebitda": info.get("enterpriseToEbitda"),
                    "roe": info.get("returnOnEquity"),
                    "roa": info.get("returnOnAssets"),
                    "debt_equity": info.get("debtToEquity"),
                    "current_ratio": info.get("currentRatio"),
                    "gross_margin": info.get("grossMargins"),
                    "net_margin": info.get("profitMargins"),
                    "fcf": info.get("freeCashflow"),
                    "dividend_yield": info.get("dividendYield"),
                    "beta": info.get("beta"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "fifty_day_average": info.get("fiftyDayAverage"),
                    "two_hundred_day_average": info.get("twoHundredDayAverage"),
                    "peg_ratio": info.get("trailingPegRatio"),
                    "eps": eps,
                    "book_value_per_share": bvps,
                    "graham_number": calculate_graham_number(eps, bvps),
                    "rsi": calculate_rsi(ticker),
                    "volume_change": calculate_volume_change(ticker),
                    **(calculate_macd(ticker) or {}),
                    **(calculate_bollinger_bands(ticker) or {}),
                }
            # No valid data, but not an error - don't retry
            return None
        except Exception:
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
                time.sleep(delay)
            # Last attempt failed
    return None


def get_stock_data_batch(
    tickers: list[str],
    batch_size: int = 50,
    with_fallback: bool = True,
    delay: float = 0.5,
) -> dict[str, dict]:
    """
    Fetch stock info and financials for multiple tickers in batches.

    Args:
        tickers: List of ticker symbols
        batch_size: Number of tickers per batch
        with_fallback: If True, retry failed tickers individually
        delay: Delay between individual fallback calls

    Returns:
        Dict mapping ticker to combined stock info and financials dict.
    """
    results: dict[str, dict] = {}
    failed_tickers: list[str] = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            # Use yf.Tickers for batch processing
            tickers_obj = yf.Tickers(" ".join(batch))

            for ticker in batch:
                try:
                    info = tickers_obj.tickers[ticker].info
                    if info and info.get("regularMarketPrice") is not None:
                        eps = info.get("trailingEps")
                        bvps = info.get("bookValue")
                        results[ticker] = {
                            "name": info.get("longName"),
                            "sector": info.get("sector"),
                            "industry": info.get("industry"),
                            "market_cap": info.get("marketCap"),
                            "currency": info.get("currency", "USD"),
                            "pe_ratio": info.get("trailingPE"),
                            "forward_pe": info.get("forwardPE"),
                            "pb_ratio": info.get("priceToBook"),
                            "ps_ratio": info.get("priceToSalesTrailing12Months"),
                            "ev_ebitda": info.get("enterpriseToEbitda"),
                            "roe": info.get("returnOnEquity"),
                            "roa": info.get("returnOnAssets"),
                            "debt_equity": info.get("debtToEquity"),
                            "current_ratio": info.get("currentRatio"),
                            "gross_margin": info.get("grossMargins"),
                            "net_margin": info.get("profitMargins"),
                            "fcf": info.get("freeCashflow"),
                            "dividend_yield": info.get("dividendYield"),
                            "beta": info.get("beta"),
                            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                            "fifty_day_average": info.get("fiftyDayAverage"),
                            "two_hundred_day_average": info.get("twoHundredDayAverage"),
                            "peg_ratio": info.get("trailingPegRatio"),
                            "eps": eps,
                            "book_value_per_share": bvps,
                            "graham_number": calculate_graham_number(eps, bvps),
                            "rsi": calculate_rsi(ticker),
                            "volume_change": calculate_volume_change(ticker),
                            **(calculate_macd(ticker) or {}),
                            **(calculate_bollinger_bands(ticker) or {}),
                        }
                    else:
                        failed_tickers.append(ticker)
                except Exception:
                    failed_tickers.append(ticker)
        except Exception as e:
            print(f"Batch error: {e}")
            failed_tickers.extend(batch)

    # Fallback: retry failed tickers individually with exponential backoff
    if with_fallback and failed_tickers:
        print(f"  Retrying {len(failed_tickers)} failed tickers individually...")
        consecutive_failures = 0
        base_delay = 0.5

        for ticker in tqdm(failed_tickers, desc="  Fallback", leave=False):
            data = get_single_stock_info(ticker)
            if data:
                results[ticker] = data
                consecutive_failures = 0  # Reset on success
            else:
                consecutive_failures += 1

            # Adaptive delay: increase if seeing consecutive failures
            if consecutive_failures >= 3:
                current_delay = min(
                    base_delay * (2 ** (consecutive_failures - 2)), 30.0
                )
                current_delay += random.uniform(0, 1)  # Jitter
            else:
                current_delay = base_delay

            time.sleep(current_delay)

    return results


def get_prices_batch(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch price data for multiple tickers using yf.download.

    Args:
        tickers: List of ticker symbols

    Returns:
        Dict mapping ticker to price dict.
    """
    results: dict[str, dict] = {}

    try:
        # Download all prices at once
        df = yf.download(tickers, period="1d", group_by="ticker", progress=False)

        if df.empty:
            return results

        today = date.today().isoformat()

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    # Single ticker: no multi-level columns
                    row = df.iloc[-1]
                else:
                    # Multiple tickers: access by ticker name
                    if ticker not in df.columns.get_level_values(0):
                        continue
                    row = df[ticker].iloc[-1]

                if pd.notna(row.get("Close")):
                    results[ticker] = {
                        "date": today,
                        "open": float(row["Open"])
                        if pd.notna(row.get("Open"))
                        else None,
                        "high": float(row["High"])
                        if pd.notna(row.get("High"))
                        else None,
                        "low": float(row["Low"]) if pd.notna(row.get("Low")) else None,
                        "close": float(row["Close"])
                        if pd.notna(row.get("Close"))
                        else None,
                        "volume": int(row["Volume"])
                        if pd.notna(row.get("Volume"))
                        else None,
                    }
            except Exception:
                pass

    except Exception as e:
        print(f"Price batch error: {e}")

    return results


def upsert_company(
    client: Client, stock_info: dict, index_membership: list[str] | None = None
) -> str | None:
    """Insert or update company in Supabase, return company ID."""
    try:
        data = {
            "ticker": stock_info["ticker"],
            "name": stock_info["name"],
            "market": "US",
            "sector": stock_info.get("sector"),
            "industry": stock_info.get("industry"),
            "currency": stock_info.get("currency", "USD"),
            "is_active": True,
        }

        # Note: index_membership stored in separate tracking for now
        # Could add a column later if needed

        result = (
            client.table("companies")
            .upsert(data, on_conflict="ticker,market")
            .execute()
        )

        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        print(f"Error upserting company {stock_info['ticker']}: {e}")
        return None


def upsert_metrics(client: Client, company_id: str, financials: dict) -> bool:
    """Insert or update metrics in Supabase."""
    try:
        today = date.today().isoformat()

        data = {
            "company_id": company_id,
            "date": today,
            "pe_ratio": financials.get("pe_ratio"),
            "pb_ratio": financials.get("pb_ratio"),
            "ps_ratio": financials.get("ps_ratio"),
            "ev_ebitda": financials.get("ev_ebitda"),
            "roe": financials.get("roe"),
            "roa": financials.get("roa"),
            "debt_equity": financials.get("debt_equity"),
            "current_ratio": financials.get("current_ratio"),
            "gross_margin": financials.get("gross_margin"),
            "net_margin": financials.get("net_margin"),
            "dividend_yield": financials.get("dividend_yield"),
            "eps": financials.get("eps"),
            "book_value_per_share": financials.get("book_value_per_share"),
            "graham_number": financials.get("graham_number"),
            "fifty_two_week_high": financials.get("fifty_two_week_high"),
            "fifty_two_week_low": financials.get("fifty_two_week_low"),
            "fifty_day_average": financials.get("fifty_day_average"),
            "two_hundred_day_average": financials.get("two_hundred_day_average"),
            "peg_ratio": financials.get("peg_ratio"),
            "beta": financials.get("beta"),
            "rsi": financials.get("rsi"),
            "volume_change": financials.get("volume_change"),
            "macd": financials.get("macd"),
            "macd_signal": financials.get("macd_signal"),
            "macd_histogram": financials.get("macd_histogram"),
            "bb_upper": financials.get("bb_upper"),
            "bb_middle": financials.get("bb_middle"),
            "bb_lower": financials.get("bb_lower"),
            "bb_percent": financials.get("bb_percent"),
            "data_source": "yfinance",
        }

        client.table("metrics").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting metrics for company {company_id}: {e}")
        return False


def upsert_price(client: Client, company_id: str, stock_info: dict) -> bool:
    """Insert or update price/market_cap in Supabase."""
    try:
        today = date.today().isoformat()

        # Get current price
        stock = yf.Ticker(stock_info["ticker"])
        hist = stock.history(period="1d")

        if hist.empty:
            return False

        latest = hist.iloc[-1]

        data = {
            "company_id": company_id,
            "date": today,
            "open": float(latest["Open"]) if pd.notna(latest["Open"]) else None,
            "high": float(latest["High"]) if pd.notna(latest["High"]) else None,
            "low": float(latest["Low"]) if pd.notna(latest["Low"]) else None,
            "close": float(latest["Close"]) if pd.notna(latest["Close"]) else None,
            "volume": int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,
            "market_cap": stock_info.get("market_cap"),
        }

        client.table("prices").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting price for company {company_id}: {e}")
        return False


def collect_and_save(
    tickers: list[str] | None = None,
    ticker_membership: dict[str, list[str]] | None = None,
    delay: float = 1.0,
    save_csv: bool = True,
    save_db: bool = True,
    universe: str = "sp500",
    batch_size: int = 30,
    is_test: bool = False,
) -> dict:
    """
    Collect US stock data and save to Supabase and/or CSV.

    Optimized version with:
    - Batch yfinance calls (50 tickers at a time)
    - Bulk price download using yf.download

    Args:
        tickers: List of tickers to collect. If None, uses universe param.
        ticker_membership: Dict mapping ticker to index membership list.
        delay: Delay between batches in seconds (reduced due to batching).
        save_csv: Whether to save data to CSV files.
        save_db: Whether to save data to Supabase.
        universe: Which universe to collect: "sp500", "full" (all indices).
        batch_size: Number of tickers per batch.

    Returns:
        Dictionary with success/failure counts.
    """
    client = None
    if save_db:
        client = get_supabase_client()

    # Determine tickers to collect
    if tickers is None:
        if universe == "full":
            print("Fetching full US universe (S&P 500 + 400 + 600 + Russell 2000)...")
            ticker_membership = get_all_us_tickers()
            tickers = list(ticker_membership.keys())
        else:
            print("Fetching S&P 500 tickers...")
            tickers = get_sp500_tickers()
            ticker_membership = {t: ["SP500"] for t in tickers}

        print(f"Found {len(tickers)} unique tickers")

    if ticker_membership is None:
        ticker_membership = {t: [] for t in tickers}

    # === PHASE 1: Batch fetch prices FIRST (more reliable) ===
    print("\nPhase 1: Fetching prices for all tickers...")
    prices_all = get_prices_batch(tickers)
    valid_tickers = list(prices_all.keys())
    print(
        f"Found {len(valid_tickers)} tickers with valid prices (out of {len(tickers)})"
    )

    # === PHASE 2: Fetch stock info only for valid tickers ===
    print(f"\nPhase 2: Fetching stock data in batches of {batch_size}...")
    stock_data_all: dict[str, dict] = {}

    for i in tqdm(range(0, len(valid_tickers), batch_size), desc="Fetching stock data"):
        batch = valid_tickers[i : i + batch_size]
        batch_data = get_stock_data_batch(
            batch, batch_size=len(batch), with_fallback=True, delay=0.3
        )
        stock_data_all.update(batch_data)
        time.sleep(delay)

    print(f"Fetched data for {len(stock_data_all)} stocks")

    # === PHASE 3: Combine and save ===
    print("\nPhase 3: Combining data and saving...")
    no_price_count = len(tickers) - len(valid_tickers)
    stats = {"success": 0, "failed": 0, "no_price": no_price_count, "no_info": 0}

    all_companies: list[dict] = []
    all_metrics: list[dict] = []
    all_prices: list[dict] = []

    for ticker in tqdm(valid_tickers, desc="Processing"):
        try:
            data = stock_data_all.get(ticker)
            if not data or not data.get("name"):
                stats["no_info"] += 1
                continue

            membership = ticker_membership.get(ticker, [])
            company_id = None

            # Save to database
            if save_db and client:
                stock_info = {
                    "ticker": ticker,
                    "name": data.get("name"),
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "market_cap": data.get("market_cap"),
                    "currency": data.get("currency", "USD"),
                }
                company_id = upsert_company(client, stock_info, membership)
                if company_id:
                    upsert_metrics(client, company_id, data)
                    if ticker in prices_all:
                        upsert_price(
                            client,
                            company_id,
                            {"ticker": ticker, "market_cap": data.get("market_cap")},
                        )

            # Collect for CSV
            if save_csv:
                all_companies.append(
                    {
                        "ticker": ticker,
                        "name": data.get("name"),
                        "market": "US",
                        "sector": data.get("sector"),
                        "industry": data.get("industry"),
                        "currency": data.get("currency", "USD"),
                        "market_cap": data.get("market_cap"),
                        "index_membership": ",".join(membership),
                    }
                )

                # Metrics
                all_metrics.append(
                    {
                        "ticker": ticker,
                        "date": date.today().isoformat(),
                        "pe_ratio": data.get("pe_ratio"),
                        "forward_pe": data.get("forward_pe"),
                        "pb_ratio": data.get("pb_ratio"),
                        "ps_ratio": data.get("ps_ratio"),
                        "ev_ebitda": data.get("ev_ebitda"),
                        "roe": data.get("roe"),
                        "roa": data.get("roa"),
                        "debt_equity": data.get("debt_equity"),
                        "current_ratio": data.get("current_ratio"),
                        "gross_margin": data.get("gross_margin"),
                        "net_margin": data.get("net_margin"),
                        "dividend_yield": data.get("dividend_yield"),
                        "beta": data.get("beta"),
                        "fifty_two_week_high": data.get("fifty_two_week_high"),
                        "fifty_two_week_low": data.get("fifty_two_week_low"),
                        "fifty_day_average": data.get("fifty_day_average"),
                        "two_hundred_day_average": data.get("two_hundred_day_average"),
                        "peg_ratio": data.get("peg_ratio"),
                        "eps": data.get("eps"),
                        "book_value_per_share": data.get("book_value_per_share"),
                        "graham_number": data.get("graham_number"),
                        "rsi": data.get("rsi"),
                        "volume_change": data.get("volume_change"),
                        "macd": data.get("macd"),
                        "macd_signal": data.get("macd_signal"),
                        "macd_histogram": data.get("macd_histogram"),
                        "bb_upper": data.get("bb_upper"),
                        "bb_middle": data.get("bb_middle"),
                        "bb_lower": data.get("bb_lower"),
                        "bb_percent": data.get("bb_percent"),
                    }
                )

                # Prices
                if ticker in prices_all:
                    price = prices_all[ticker]
                    all_prices.append(
                        {
                            "ticker": ticker,
                            **price,
                            "market_cap": data.get("market_cap"),
                        }
                    )

            stats["success"] += 1

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            stats["failed"] += 1

    # Save to CSV
    if save_csv:
        save_to_csv(all_companies, all_metrics, all_prices, is_test=is_test)

    print(f"\nCollection complete: {stats}")
    return stats


def save_to_csv(
    companies: list[dict],
    metrics: list[dict],
    prices: list[dict],
    is_test: bool = False,
) -> None:
    """Save collected data to CSV files for local storage."""
    today = date.today().strftime("%Y%m%d")
    suffix = "_test" if is_test else ""

    # Ensure directories exist
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    FINANCIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Save companies (append to existing or create new)
    if companies:
        companies_df = pd.DataFrame(companies)
        companies_file = DATA_DIR / f"us_companies{suffix}.csv"
        if not is_test and companies_file.exists():
            existing = pd.read_csv(companies_file)
            combined = pd.concat([existing, companies_df]).drop_duplicates(
                subset=["ticker"], keep="last"
            )
            combined.to_csv(companies_file, index=False)
        else:
            companies_df.to_csv(companies_file, index=False)
        print(f"Saved {len(companies)} companies to {companies_file}")

    # Save metrics with date
    if metrics:
        metrics_df = pd.DataFrame(metrics)
        metrics_file = FINANCIALS_DIR / f"us_metrics_{today}{suffix}.csv"
        metrics_df.to_csv(metrics_file, index=False)
        print(f"Saved {len(metrics)} metrics to {metrics_file}")

    # Save prices with date
    if prices:
        prices_df = pd.DataFrame(prices)
        prices_file = PRICES_DIR / f"us_prices_{today}{suffix}.csv"
        prices_df.to_csv(prices_file, index=False)
        print(f"Saved {len(prices)} prices to {prices_file}")


def dry_run_test(tickers: list[str] | None = None) -> None:
    """Test data collection without saving to database."""
    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOGL"]

    print(f"Dry run test with {len(tickers)} tickers...\n")

    for ticker in tickers:
        print(f"=== {ticker} ===")

        # Get stock info
        stock_info = get_stock_info(ticker)
        if stock_info:
            print(f"Name: {stock_info.get('name')}")
            print(f"Sector: {stock_info.get('sector')}")
            print(f"Industry: {stock_info.get('industry')}")
            print(
                f"Market Cap: {stock_info.get('market_cap'):,}"
                if stock_info.get("market_cap")
                else "Market Cap: N/A"
            )

        # Get financials
        financials = get_financials(ticker)
        if financials:
            print(f"P/E: {financials.get('pe_ratio')}")
            print(f"P/B: {financials.get('pb_ratio')}")
            print(f"ROE: {financials.get('roe')}")
            print(f"Dividend Yield: {financials.get('dividend_yield')}")

        print()


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    csv_only = "--csv-only" in args
    full_universe = "--full" in args

    if "--dry-run" in args:
        # Dry run: test data collection without database
        dry_run_test()
    elif "--test" in args:
        # Test mode: only a few tickers
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        print(f"Running in test mode (csv_only={csv_only})...")
        collect_and_save(
            tickers=test_tickers,
            delay=0.2,
            save_csv=True,
            save_db=not csv_only,
            is_test=True,
        )
    elif "--list-tickers" in args:
        # Just list tickers without collecting
        if full_universe:
            tickers = get_all_us_tickers()
            print("\nSample tickers with membership:")
            for t, m in list(tickers.items())[:20]:
                print(f"  {t}: {m}")
        else:
            tickers = get_sp500_tickers()
    elif full_universe:
        # Full universe: S&P 500 + 400 + 600 + Russell 2000
        print("Running FULL US universe collection...")
        print("This will take 3-4 hours. Press Ctrl+C to cancel.\n")
        collect_and_save(
            save_csv=True,
            save_db=not csv_only,
            universe="full",
        )
    elif csv_only:
        # CSV only: save to files without database
        print("Running S&P 500 collection (CSV only)...")
        collect_and_save(save_csv=True, save_db=False, universe="sp500")
    else:
        # S&P 500 only: both database and CSV
        print("Running S&P 500 collection...")
        collect_and_save(save_csv=True, save_db=True, universe="sp500")
