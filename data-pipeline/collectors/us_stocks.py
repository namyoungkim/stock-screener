"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.

Usage:
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --sp500
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --index-only
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --test
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --resume
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --tickers-file data/missing_tickers.txt

Ticker Sources:
    --sp500: S&P 500 only (~500 stocks)
    --index-only: S&P 500 + 400 + 600 + Russell 2000 (~2,800 stocks)
    --tickers-file FILE: Custom ticker list from file (one ticker per line)
    (default): Full US market via NASDAQ FTP (~6,000-8,000 stocks)
"""

import contextlib
import logging
import random
import time
from datetime import date
from io import StringIO

import pandas as pd
import requests
import yfinance as yf
from common.config import (
    BACKOFF_TIMES,
    BASE_DELAY_HISTORY,
    BASE_DELAY_INFO,
    BATCH_SIZE_HISTORY,
    BATCH_SIZE_INFO,
    DATA_DIR,
    DELAY_JITTER_HISTORY,
    DELAY_JITTER_INFO,
    MAX_BACKOFFS,
    MAX_CONSECUTIVE_FAILURES,
    RATE_LIMIT_WAIT_HISTORY,
    RATE_LIMIT_WAIT_INFO,
)
from common.indicators import (
    calculate_all_technicals,
    calculate_graham_number,
    calculate_ma_trend,
    calculate_price_to_52w_high_pct,
)
from common.logging import CollectionProgress, setup_logger
from common.rate_limit import (
    YFinanceTimeoutError,
    get_stock_history_with_timeout,
    get_stock_info_with_timeout,
)
from common.retry import RetryConfig, RetryQueue, with_retry
from common.session import create_browser_session
from common.storage import StorageManager, get_supabase_client
from processors.validators import MetricsValidator
from tqdm import tqdm

# Rate limit retry settings
MAX_RETRY_ROUNDS = 10  # Maximum retry rounds for rate-limited tickers

# ============================================================
# Ticker Source Functions
# ============================================================


def _fetch_wiki_tickers(url: str, index_name: str) -> list[str]:
    """Fetch tickers from Wikipedia table."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    response = requests.get(url, headers=headers)
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]

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
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
        df = pd.read_csv(url, skiprows=9)

        if "Asset Class" in df.columns:
            df = df[df["Asset Class"] == "Equity"]

        tickers = df["Ticker"].dropna().str.strip().tolist()
        tickers = [t for t in tickers if t and isinstance(t, str) and len(t) <= 5]
        print(f"Fetched {len(tickers)} Russell 2000 tickers")
        return tickers
    except Exception as e:
        print(f"Error fetching Russell 2000: {e}")
        return []


def _fetch_nasdaq_ftp() -> tuple[list[str], list[str]]:
    """
    Fetch all tickers from NASDAQ FTP.

    Returns:
        Tuple of (nasdaq_tickers, other_tickers)
        - nasdaq_tickers: NASDAQ listed stocks
        - other_tickers: NYSE, AMEX, and other exchange stocks

    Data source: ftp://ftp.nasdaqtrader.com/symboldirectory/
    Files: nasdaqlisted.txt, otherlisted.txt
    """
    nasdaq_tickers: list[str] = []
    other_tickers: list[str] = []

    # NASDAQ listed stocks
    try:
        url = "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt"
        df = pd.read_csv(url, sep="|")

        # Filter out test symbols (ends with File Creation Time row)
        df = df[df["Symbol"].notna()]
        df = df[~df["Symbol"].str.contains("File Creation Time", na=False)]

        # Filter: only common stocks (exclude ETFs, warrants, etc.)
        # ETF column: Y = ETF, N = Not ETF
        if "ETF" in df.columns:
            df = df[df["ETF"] == "N"]

        # Test Issue column: Y = Test, N = Not Test
        if "Test Issue" in df.columns:
            df = df[df["Test Issue"] == "N"]

        nasdaq_tickers = df["Symbol"].str.strip().tolist()
        # Filter: only common stocks (exclude warrants, rights, units)
        # Warrants/Rights/Units are typically 5-letter tickers ending in W/R/U
        # 4-letter or shorter tickers ending in W/R/U are usually common stocks (e.g., SNOW, PLTR)
        nasdaq_tickers = [
            t for t in nasdaq_tickers
            if t and len(t) <= 5 and t.isalpha()
            and not (len(t) == 5 and t.endswith("W"))  # 5-letter Warrants
            and not (len(t) == 5 and t.endswith("R"))  # 5-letter Rights
            and not (len(t) == 5 and t.endswith("U"))  # 5-letter Units
        ]
        print(f"Fetched {len(nasdaq_tickers)} NASDAQ tickers")

    except Exception as e:
        print(f"Error fetching NASDAQ list: {e}")

    # Other exchanges (NYSE, AMEX, etc.)
    try:
        url = "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt"
        df = pd.read_csv(url, sep="|")

        # Filter out test symbols
        df = df[df["ACT Symbol"].notna()]
        df = df[~df["ACT Symbol"].str.contains("File Creation Time", na=False)]

        # Filter: only common stocks
        # ETF column: Y = ETF, N = Not ETF
        if "ETF" in df.columns:
            df = df[df["ETF"] == "N"]

        # Test Issue column: Y = Test, N = Not Test
        if "Test Issue" in df.columns:
            df = df[df["Test Issue"] == "N"]

        other_tickers = df["ACT Symbol"].str.strip().tolist()
        # Filter: only common stocks (exclude warrants, rights, units)
        # Warrants/Rights/Units are typically 5-letter tickers ending in W/R/U
        other_tickers = [
            t for t in other_tickers
            if t and len(t) <= 5 and t.isalpha()
            and not (len(t) == 5 and t.endswith("W"))  # 5-letter Warrants
            and not (len(t) == 5 and t.endswith("R"))  # 5-letter Rights
            and not (len(t) == 5 and t.endswith("U"))  # 5-letter Units
        ]
        print(f"Fetched {len(other_tickers)} other exchange tickers")

    except Exception as e:
        print(f"Error fetching other listings: {e}")

    return nasdaq_tickers, other_tickers


def get_index_tickers() -> dict[str, list[str]]:
    """
    Get US tickers from major indices (S&P 500/400/600 + Russell 2000).

    Returns:
        Dictionary mapping ticker to list of indices it belongs to.
    """
    print("Fetching US index tickers (S&P + Russell)...")

    sp500 = set(get_sp500_tickers())
    sp400 = set(get_sp400_tickers())
    sp600 = set(get_sp600_tickers())
    russell2000 = set(get_russell2000_tickers())

    all_tickers: dict[str, list[str]] = {}

    for ticker in sp500:
        all_tickers.setdefault(ticker, []).append("SP500")
    for ticker in sp400:
        all_tickers.setdefault(ticker, []).append("SP400")
    for ticker in sp600:
        all_tickers.setdefault(ticker, []).append("SP600")
    for ticker in russell2000:
        all_tickers.setdefault(ticker, []).append("RUSSELL2000")

    print(f"\nTotal unique index tickers: {len(all_tickers)}")
    print(f"  - S&P 500: {len(sp500)}")
    print(f"  - S&P 400: {len(sp400)}")
    print(f"  - S&P 600: {len(sp600)}")
    print(f"  - Russell 2000: {len(russell2000)}")

    return all_tickers


def get_all_us_tickers() -> dict[str, list[str]]:
    """
    Get all US tickers from NASDAQ FTP (full market coverage).

    Returns:
        Dictionary mapping ticker to list of exchanges it belongs to.
        Includes ~6,000-8,000 stocks from NYSE and NASDAQ.
    """
    print("Fetching full US market tickers via NASDAQ FTP...")

    nasdaq_tickers, other_tickers = _fetch_nasdaq_ftp()

    all_tickers: dict[str, list[str]] = {}

    for ticker in nasdaq_tickers:
        all_tickers.setdefault(ticker, []).append("NASDAQ")
    for ticker in other_tickers:
        all_tickers.setdefault(ticker, []).append("NYSE/OTHER")

    print(f"\nTotal unique tickers: {len(all_tickers)}")
    print(f"  - NASDAQ: {len(nasdaq_tickers)}")
    print(f"  - NYSE/Other: {len(other_tickers)}")

    return all_tickers


# ============================================================
# US Stock Collector Class
# ============================================================


class USCollector:
    """Collector for US stock data."""

    MARKET = "US"
    MARKET_PREFIX = "us"
    DATA_SOURCE = "yfinance"

    def __init__(
        self,
        universe: str = "full",
        save_db: bool = True,
        save_csv: bool = True,
        log_level: int = logging.INFO,
        quiet: bool = False,
    ):
        """
        Initialize US stock collector.

        Args:
            universe: "sp500", "index", or "full"
                - "sp500": S&P 500 only (~500 stocks)
                - "index": S&P 500+400+600 + Russell 2000 (~2,800 stocks)
                - "full": Full US market via NASDAQ FTP (~6,000-8,000 stocks)
            save_db: Whether to save to Supabase
            save_csv: Whether to save to CSV files
            log_level: Logging level
            quiet: If True, minimize output (disable tqdm, reduce logging)
        """
        self.universe = universe
        self.save_db = save_db
        self.save_csv = save_csv
        self.quiet = quiet

        # Setup logger (WARNING level if quiet)
        effective_log_level = logging.WARNING if quiet else log_level
        self.logger = setup_logger(self.__class__.__name__, level=effective_log_level)

        # Initialize components
        self.client = get_supabase_client() if save_db else None
        self.storage = StorageManager(
            client=self.client,
            data_dir=DATA_DIR,
            market_prefix=self.MARKET_PREFIX,
        )
        self.validator = MetricsValidator()
        self.retry_queue = RetryQueue()

        # US-specific state
        self._ticker_membership: dict[str, list[str]] = {}
        # Create browser session to bypass TLS fingerprinting
        self._session = create_browser_session()

    def get_tickers(self) -> list[str]:
        """Get list of US tickers based on universe setting."""
        if self.universe == "sp500":
            tickers = get_sp500_tickers()
            self._ticker_membership = {t: ["SP500"] for t in tickers}
        elif self.universe == "index":
            self._ticker_membership = get_index_tickers()
            tickers = list(self._ticker_membership.keys())
        else:  # full
            self._ticker_membership = get_all_us_tickers()
            tickers = list(self._ticker_membership.keys())

        return tickers

    def fetch_stock_info(self, ticker: str) -> dict | None:
        """Fetch stock information for a single ticker with retry."""
        return self._fetch_single_stock_info(ticker)

    @with_retry(RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0))
    def _fetch_single_stock_info(self, ticker: str) -> dict | None:
        """Internal method with retry decorator."""
        stock = yf.Ticker(ticker, session=self._session)
        info = get_stock_info_with_timeout(stock)

        if not info or info.get("regularMarketPrice") is None:
            return None

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")
        current_price = info.get("regularMarketPrice")
        fifty_two_week_high = info.get("fiftyTwoWeekHigh")
        fifty_day_average = info.get("fiftyDayAverage")
        two_hundred_day_average = info.get("twoHundredDayAverage")

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
            "fifty_two_week_high": fifty_two_week_high,
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": fifty_day_average,
            "two_hundred_day_average": two_hundred_day_average,
            "peg_ratio": info.get("trailingPegRatio"),
            "eps": eps,
            "book_value_per_share": bvps,
            "graham_number": calculate_graham_number(eps, bvps),
            "price_to_52w_high_pct": calculate_price_to_52w_high_pct(
                current_price, fifty_two_week_high
            ),
            "ma_trend": calculate_ma_trend(fifty_day_average, two_hundred_day_average),
        }

    def fetch_prices_batch(
        self, tickers: list[str], batch_size: int = 500
    ) -> dict[str, dict]:
        """Fetch price data for multiple tickers using yf.download in batches.

        Args:
            tickers: List of ticker symbols
            batch_size: Number of tickers per batch (default 500)
        """
        results: dict[str, dict] = {}
        trading_date: str | None = None  # Will be extracted from yfinance data

        self.logger.info(
            f"Fetching prices for {len(tickers)} tickers in batches of {batch_size}..."
        )

        for i in tqdm(
            range(0, len(tickers), batch_size), desc="Fetching prices", leave=False, disable=self.quiet
        ):
            batch = tickers[i : i + batch_size]
            try:
                df = yf.download(
                    batch, period="1d", group_by="ticker", progress=False, threads=True
                )

                if df.empty:
                    continue

                # Extract trading date from DataFrame index (first batch only)
                if trading_date is None and len(df.index) > 0:
                    trading_date = df.index[-1].strftime("%Y-%m-%d")

                for ticker in batch:
                    try:
                        if len(batch) == 1:
                            row = df.iloc[-1]
                        else:
                            if ticker not in df.columns.get_level_values(0):
                                continue
                            row = df[ticker].iloc[-1]

                        if pd.notna(row.get("Close")):
                            results[ticker] = {
                                "date": trading_date or date.today().isoformat(),
                                "open": float(row["Open"])
                                if pd.notna(row.get("Open"))
                                else None,
                                "high": float(row["High"])
                                if pd.notna(row.get("High"))
                                else None,
                                "low": float(row["Low"])
                                if pd.notna(row.get("Low"))
                                else None,
                                "close": float(row["Close"])
                                if pd.notna(row.get("Close"))
                                else None,
                                "volume": int(row["Volume"])
                                if pd.notna(row.get("Volume"))
                                else None,
                            }
                    except Exception:
                        pass

                # Sleep between batches
                time.sleep(0.5 + random.uniform(0, 0.5))

            except Exception as e:
                self.logger.error(f"Price batch error: {e}")
                time.sleep(2.0)
                continue

        return results

    def fetch_history_bulk(
        self,
        tickers: list[str],
        period: str = "3mo",
        batch_size: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for all tickers in bulk using yf.download.

        Rate limit handling:
        - Batch size: BATCH_SIZE_HISTORY (default 500)
        - Sleep between batches: BASE_DELAY_HISTORY + jitter
        - yf.download is more lenient than individual ticker.info calls
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_HISTORY
        results: dict[str, pd.DataFrame] = {}

        self.logger.info(
            f"Downloading {period} history for {len(tickers)} tickers in bulk..."
        )

        for i in tqdm(
            range(0, len(tickers), batch_size), desc="Downloading history", leave=False, disable=self.quiet
        ):
            batch = tickers[i : i + batch_size]
            try:
                df = yf.download(
                    batch,
                    period=period,
                    group_by="ticker",
                    progress=False,
                    threads=True,
                )

                if df.empty:
                    continue

                if len(batch) == 1:
                    results[batch[0]] = df
                else:
                    for ticker in batch:
                        try:
                            if ticker in df.columns.get_level_values(0):
                                ticker_df = df[ticker].dropna(how="all")
                                if not ticker_df.empty:
                                    results[ticker] = ticker_df
                        except Exception:
                            pass

                # Sleep between batches
                time.sleep(BASE_DELAY_HISTORY + random.uniform(0, DELAY_JITTER_HISTORY))

            except Exception as e:
                self.logger.error(f"History batch error: {e}")
                # Longer sleep on error
                time.sleep(5.0)
                continue

        self.logger.info(f"Downloaded history for {len(results)} tickers")
        return results

    def fetch_stock_data_batch(
        self,
        tickers: list[str],
        history_data: dict[str, pd.DataFrame] | None = None,
        batch_size: int | None = None,
    ) -> dict[str, dict]:
        """
        Fetch stock info for multiple tickers in batches.

        Rate limit handling:
        - Batch size: BATCH_SIZE_INFO (default 10)
        - Sleep between batches: BASE_DELAY_INFO + jitter
        - Rate limit detection: Progressive backoff on consecutive failures
        - Max retries: MAX_BACKOFFS before stopping
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_INFO

        results: dict[str, dict] = {}
        failed_tickers: list[str] = []
        consecutive_failures = 0
        backoff_count = 0

        total_batches = (len(tickers) + batch_size - 1) // batch_size

        for batch_idx, i in enumerate(
            tqdm(
                range(0, len(tickers), batch_size),
                desc="Fetching stock data",
                leave=False,
                disable=self.quiet,
            )
        ):
            batch = tickers[i : i + batch_size]
            batch_success = 0

            try:
                for ticker in batch:
                    try:
                        stock = yf.Ticker(ticker, session=self._session)
                        info = get_stock_info_with_timeout(stock)

                        if info and info.get("regularMarketPrice") is not None:
                            eps = info.get("trailingEps")
                            bvps = info.get("bookValue")
                            current_price = info.get("regularMarketPrice")
                            fifty_two_week_high = info.get("fiftyTwoWeekHigh")
                            fifty_day_average = info.get("fiftyDayAverage")
                            two_hundred_day_average = info.get("twoHundredDayAverage")

                            # Use pre-fetched history if available
                            hist = history_data.get(ticker) if history_data else None
                            if hist is None or hist.empty:
                                hist = get_stock_history_with_timeout(stock, period="2mo")
                            technicals = calculate_all_technicals(hist)

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
                                "fifty_two_week_high": fifty_two_week_high,
                                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                                "fifty_day_average": fifty_day_average,
                                "two_hundred_day_average": two_hundred_day_average,
                                "peg_ratio": info.get("trailingPegRatio"),
                                "eps": eps,
                                "book_value_per_share": bvps,
                                "graham_number": calculate_graham_number(eps, bvps),
                                "price_to_52w_high_pct": calculate_price_to_52w_high_pct(
                                    current_price, fifty_two_week_high
                                ),
                                "ma_trend": calculate_ma_trend(
                                    fifty_day_average, two_hundred_day_average
                                ),
                                **technicals,
                            }
                            batch_success += 1
                        else:
                            failed_tickers.append(ticker)
                    except YFinanceTimeoutError:
                        self.logger.warning(
                            f"Timeout for {ticker} in batch {batch_idx + 1}/{total_batches}"
                        )
                        consecutive_failures += 1
                        failed_tickers.append(ticker)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if (
                            "rate limit" in error_msg
                            or "too many requests" in error_msg
                        ):
                            self.logger.warning(
                                f"Rate limit detected in batch {batch_idx + 1}/{total_batches}"
                            )
                            consecutive_failures += 1
                        failed_tickers.append(ticker)

            except Exception as e:
                error_msg = str(e).lower()
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    self.logger.warning(f"Rate limit detected for batch: {e}")
                    consecutive_failures += 1
                else:
                    self.logger.warning(f"Batch error: {e}")
                failed_tickers.extend(batch)

            # Track consecutive failures
            if batch_success == 0:
                consecutive_failures += 1
            else:
                consecutive_failures = 0  # Reset on any success

            # Backoff if rate limited
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                backoff_count += 1
                if backoff_count > MAX_BACKOFFS:
                    self.logger.warning(
                        f"Stopping after {MAX_BACKOFFS} backoffs. "
                        f"Completed {len(results)}/{len(tickers)} tickers."
                    )
                    break

                # Progressive backoff: 1min -> 2min -> 3min -> 5min
                backoff_idx = min(backoff_count - 1, len(BACKOFF_TIMES) - 1)
                backoff_time = BACKOFF_TIMES[backoff_idx] + random.uniform(0, 30.0)
                self.logger.warning(
                    f"Rate limit detected. Backoff {backoff_count}/{MAX_BACKOFFS}: "
                    f"waiting {backoff_time:.0f}s... "
                    f"(Completed {len(results)}/{len(tickers)} so far)"
                )
                time.sleep(backoff_time)
                consecutive_failures = 0  # Reset after backoff

            # Sleep between batches
            sleep_time = BASE_DELAY_INFO + random.uniform(0, DELAY_JITTER_INFO)
            time.sleep(sleep_time)

        # Retry failed tickers with longer delays (only if not stopped by backoff limit)
        if failed_tickers and backoff_count <= MAX_BACKOFFS:
            self.logger.info(
                f"Retrying {len(failed_tickers)} failed tickers with longer delays..."
            )
            retry_failures = 0
            max_retry_failures = 20  # Allow more retries

            for ticker in tqdm(failed_tickers, desc="Fallback", leave=False, disable=self.quiet):
                try:
                    data = self._fetch_single_stock_info(ticker)
                    if data:
                        # Get technicals from history
                        hist = history_data.get(ticker) if history_data else None
                        if hist is not None and not hist.empty:
                            technicals = calculate_all_technicals(hist)
                            data.update(technicals)
                        results[ticker] = data
                        retry_failures = 0  # Reset on success
                    else:
                        retry_failures += 1
                except Exception as e:
                    error_msg = str(e).lower()
                    if "rate limit" in error_msg or "too many requests" in error_msg:
                        retry_failures += 1
                        if retry_failures >= max_retry_failures:
                            self.logger.warning(
                                f"Stopping fallback: {retry_failures} consecutive failures. "
                                f"Rate limit likely. Completed {len(results)}/{len(tickers)} tickers."
                            )
                            break
                        # Backoff on rate limit in fallback
                        if retry_failures % 5 == 0:
                            backoff_time = 300.0 + random.uniform(0, 60.0)  # 5-6 minutes
                            self.logger.warning(f"Fallback backoff: waiting {backoff_time:.0f}s...")
                            time.sleep(backoff_time)

                # Longer sleep for fallback: 5-8 seconds
                time.sleep(5.0 + random.uniform(0, 3.0))
        elif backoff_count > MAX_BACKOFFS:
            self.logger.info("Skipping fallback retry due to rate limit.")

        return results

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        batch_size: int | None = None,
        is_test: bool = False,
        check_rate_limit_first: bool = True,
        auto_retry: bool = True,
    ) -> dict:
        """
        Override collect to use optimized batch fetching.

        This version uses batch processing for stock data fetching
        which is significantly faster than individual calls.

        Args:
            batch_size: Batch size for .info calls (default: BATCH_SIZE_INFO from config)
            auto_retry: If True, retry missing tickers after quality check
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_INFO
        # Get tickers if not provided
        if tickers is None:
            tickers = self.get_tickers()
            self.logger.info(f"Found {len(tickers)} tickers to collect")

        # Resume: skip already collected tickers
        if resume:
            completed = self.storage.load_completed_tickers()
            original_count = len(tickers)
            tickers = [t for t in tickers if t not in completed]
            self.logger.info(
                f"Resume mode: Skipping {original_count - len(tickers)} already collected. "
                f"{len(tickers)} remaining."
            )

        if not tickers:
            self.logger.info("No tickers to collect")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        # Phase 1: Fetch prices
        self.logger.info("Phase 1: Fetching prices for all tickers...")
        prices_all = self.fetch_prices_batch(tickers)
        valid_tickers = list(prices_all.keys())
        self.logger.info(f"Found {len(valid_tickers)} tickers with valid prices")

        # Set up version directory (based on trading date from prices)
        if self.save_csv:
            trading_date = self._extract_trading_date_from_prices(prices_all)
            if resume:
                self.storage.resume_version_dir(target_date=trading_date)
            else:
                self.storage.get_or_create_version_dir(target_date=trading_date)

        # Phase 2: Bulk download history with retry loop
        self.logger.info("Phase 2: Downloading history for technical indicators...")
        history_retry_round = 0
        remaining_history_tickers = valid_tickers.copy()
        history_data: dict[str, pd.DataFrame] = {}

        while remaining_history_tickers and history_retry_round <= MAX_RETRY_ROUNDS:
            if history_retry_round > 0:
                wait_time = RATE_LIMIT_WAIT_HISTORY + random.uniform(0, 30)
                self.logger.info(
                    f"History retry {history_retry_round}/{MAX_RETRY_ROUNDS}: "
                    f"{len(remaining_history_tickers)} tickers remaining. "
                    f"Waiting {wait_time / 60:.1f} minutes..."
                )
                time.sleep(wait_time)

            batch_result = self.fetch_history_bulk(
                remaining_history_tickers, period="2mo", batch_size=300
            )
            history_data.update(batch_result)

            # Find tickers that weren't collected
            missing_tickers = [
                t for t in remaining_history_tickers if t not in batch_result
            ]

            if not missing_tickers:
                break

            # Check if we made any progress
            if len(batch_result) == 0 and history_retry_round > 0:
                self.logger.warning(
                    f"No progress in history retry round {history_retry_round}. "
                    f"Rate limit may still be active."
                )

            remaining_history_tickers = missing_tickers
            history_retry_round += 1

        if remaining_history_tickers:
            self.logger.warning(
                f"Failed to collect history for {len(remaining_history_tickers)} tickers "
                f"after {MAX_RETRY_ROUNDS} retry rounds"
            )

        # Phase 3: Batch fetch stock data with retry loop for rate-limited tickers
        self.logger.info(f"Phase 3: Fetching stock data in batches of {batch_size}...")

        retry_round = 0
        remaining_tickers = valid_tickers.copy()
        stock_data_all: dict[str, dict] = {}

        while remaining_tickers and retry_round <= MAX_RETRY_ROUNDS:
            if retry_round > 0:
                wait_time = RATE_LIMIT_WAIT_INFO + random.uniform(0, 60)
                self.logger.info(
                    f"Rate limit retry {retry_round}/{MAX_RETRY_ROUNDS}: "
                    f"{len(remaining_tickers)} tickers remaining. "
                    f"Waiting {wait_time / 60:.1f} minutes..."
                )
                time.sleep(wait_time)

            batch_result = self.fetch_stock_data_batch(
                remaining_tickers,
                history_data=history_data,
                batch_size=batch_size,
            )
            stock_data_all.update(batch_result)

            # Find tickers that weren't collected (potential rate limit failures)
            missing_tickers = [t for t in remaining_tickers if t not in batch_result]

            if not missing_tickers:
                remaining_tickers = []  # Clear before break for accurate warning check
                break  # All tickers collected successfully

            # Check if we made any progress
            collected_this_round = len(batch_result)
            if collected_this_round == 0 and retry_round > 0:
                self.logger.warning(
                    f"No progress in retry round {retry_round}. "
                    f"Rate limit may still be active."
                )

            remaining_tickers = missing_tickers
            retry_round += 1

        if remaining_tickers:
            self.logger.warning(
                f"Failed to collect {len(remaining_tickers)} tickers after "
                f"{MAX_RETRY_ROUNDS} retry rounds"
            )

        self.logger.info(f"Fetched data for {len(stock_data_all)} stocks")

        # Phase 4: Process and save
        self.logger.info("Phase 4: Processing and saving...")

        progress = CollectionProgress(
            total=len(valid_tickers),
            logger=self.logger,
            desc="Processing",
        )

        all_companies: list[dict] = []
        all_metrics: list[dict] = []
        all_prices: list[dict] = []

        for ticker in valid_tickers:
            try:
                data = stock_data_all.get(ticker)
                if not data or not data.get("name"):
                    progress.update(skipped=True)
                    continue

                # Validate metrics
                validated = self.validator.validate(data, ticker)

                # Save to database
                if self.save_db and self.client:
                    company_id = self.storage.upsert_company(
                        ticker=ticker,
                        name=validated.get("name", ""),
                        market=self.MARKET,
                        sector=validated.get("sector"),
                        industry=validated.get("industry"),
                        currency=validated.get("currency", "USD"),
                    )
                    if company_id:
                        self.storage.upsert_metrics(
                            company_id=company_id,
                            metrics=validated,
                            data_source=self.DATA_SOURCE,
                        )
                        if ticker in prices_all:
                            self.storage.upsert_price(
                                company_id=company_id,
                                price_data=prices_all[ticker],
                                market_cap=validated.get("market_cap"),
                            )

                # Collect for CSV
                if self.save_csv:
                    all_companies.append(self._build_company_record(ticker, validated))
                    trading_date_str = prices_all.get(ticker, {}).get("date")
                    all_metrics.append(
                        self._build_metrics_record(ticker, validated, trading_date_str)
                    )
                    if ticker in prices_all:
                        all_prices.append(
                            self._build_price_record(
                                ticker, prices_all[ticker], validated
                            )
                        )

                progress.update(success=True)

            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                self.retry_queue.add_failed(ticker, str(e))
                progress.update(success=False)

            progress.log_progress(interval=100)

        # Save to CSV
        if self.save_csv:
            self.storage.save_to_csv(
                companies=all_companies,
                metrics=all_metrics,
                prices=all_prices,
                is_test=is_test,
            )

            # Quality check and auto-retry (only for full collection, not test mode)
            if not is_test and len(all_metrics) > 0:
                from processors.quality_check import DataQualityChecker

                checker = DataQualityChecker()
                collected_tickers = [r["ticker"] for r in all_metrics]
                metrics_df = pd.DataFrame(all_metrics)

                report = checker.check(
                    market=self.MARKET,
                    collected_tickers=collected_tickers,
                    metrics_df=metrics_df,
                )
                checker.print_report(report)

                # Auto-retry missing tickers
                if (
                    auto_retry
                    and report.missing_count > 0
                    and report.missing_count <= 100
                ):
                    self.logger.info(
                        f"Auto-retrying {report.missing_count} missing tickers..."
                    )
                    retry_result = self.collect(
                        tickers=report.missing_tickers,
                        check_rate_limit_first=False,
                        auto_retry=False,  # Prevent infinite loop
                        is_test=is_test,
                    )

                    # Log retry results
                    if retry_result.get("success", 0) > 0:
                        self.logger.info(
                            f"Retry collected {retry_result['success']} additional tickers"
                        )

                # Save missing tickers to file for manual retry
                if report.missing_count > 0:
                    from common.config import DATA_DIR

                    missing_file = DATA_DIR / f"missing_{self.MARKET_PREFIX}_tickers.txt"
                    with open(missing_file, "w") as f:
                        f.write(f"# Missing {self.MARKET} tickers ({report.missing_count})\n")
                        f.write("# Generated after collection\n")
                        for ticker in report.missing_tickers:
                            f.write(f"{ticker}\n")
                    self.logger.info(
                        f"Saved {report.missing_count} missing tickers to {missing_file}"
                    )

        progress.log_summary()

        # Log validation summary
        validation_summary = self.validator.get_summary()
        if validation_summary["with_warnings"] > 0:
            self.logger.warning(f"Validation summary: {validation_summary}")

        # Save failed items
        if self.retry_queue.count > 0:
            failed_file = DATA_DIR / f"{self.MARKET_PREFIX}_failed_tickers.json"
            self.retry_queue.save_path = failed_file
            self.retry_queue.save_to_file()

        return progress.get_stats()

    def _extract_trading_date_from_prices(self, prices: dict[str, dict]) -> date | None:
        """Extract trading date from prices dictionary.

        Returns the latest date from the prices dictionary.
        Falls back to None if no valid date found.
        """
        dates = [p.get("date") for p in prices.values() if p.get("date")]
        if not dates:
            return None
        return date.fromisoformat(max(dates))

    def _build_company_record(self, ticker: str, data: dict) -> dict:
        """Build company record for CSV."""
        return {
            "ticker": ticker,
            "name": data.get("name"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "currency": data.get("currency", "USD"),
        }

    def _build_metrics_record(
        self, ticker: str, data: dict, trading_date: str | None = None
    ) -> dict:
        """Build metrics record for CSV."""
        record_date = trading_date or date.today().isoformat()
        return {
            "ticker": ticker,
            "date": record_date,
            "pe_ratio": data.get("pe_ratio"),
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
            "eps": data.get("eps"),
            "book_value_per_share": data.get("book_value_per_share"),
            "graham_number": data.get("graham_number"),
            "fifty_two_week_high": data.get("fifty_two_week_high"),
            "fifty_two_week_low": data.get("fifty_two_week_low"),
            "fifty_day_average": data.get("fifty_day_average"),
            "two_hundred_day_average": data.get("two_hundred_day_average"),
            "peg_ratio": data.get("peg_ratio"),
            "beta": data.get("beta"),
            "rsi": data.get("rsi"),
            "volume_change": data.get("volume_change"),
            "macd": data.get("macd"),
            "macd_signal": data.get("macd_signal"),
            "macd_histogram": data.get("macd_histogram"),
            "bb_upper": data.get("bb_upper"),
            "bb_middle": data.get("bb_middle"),
            "bb_lower": data.get("bb_lower"),
            "bb_percent": data.get("bb_percent"),
            "mfi": data.get("mfi"),
            "price_to_52w_high_pct": data.get("price_to_52w_high_pct"),
            "ma_trend": data.get("ma_trend"),
        }

    def _build_price_record(
        self,
        ticker: str,
        price_data: dict,
        stock_data: dict,
    ) -> dict:
        """Build price record for CSV."""
        return {
            "ticker": ticker,
            "date": price_data.get("date", date.today().isoformat()),
            "open": price_data.get("open"),
            "high": price_data.get("high"),
            "low": price_data.get("low"),
            "close": price_data.get("close"),
            "volume": price_data.get("volume"),
            "market_cap": stock_data.get("market_cap"),
        }


# ============================================================
# CLI Entry Point
# ============================================================


def main():
    """Main entry point for CLI."""
    import sys

    args = sys.argv[1:]
    csv_only = "--csv-only" in args
    sp500_only = "--sp500" in args
    index_only = "--index-only" in args
    resume = "--resume" in args
    is_test = "--test" in args
    quiet = "--quiet" in args or "-q" in args
    log_level = logging.DEBUG if "--verbose" in args else logging.INFO

    # Parse --batch-size N
    batch_size = None
    for i, arg in enumerate(args):
        if arg == "--batch-size" and i + 1 < len(args):
            with contextlib.suppress(ValueError):
                batch_size = int(args[i + 1])
            break

    # Parse --tickers-file FILE
    tickers_file = None
    for i, arg in enumerate(args):
        if arg == "--tickers-file" and i + 1 < len(args):
            tickers_file = args[i + 1]
            break

    if "--dry-run" in args:
        # Dry run: test without saving
        print("Dry run test with 3 tickers...")
        collector = USCollector(universe="sp500", save_db=False, save_csv=False)
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            info = collector.fetch_stock_info(ticker)
            if info:
                print(f"\n=== {ticker} ===")
                print(f"Name: {info.get('name')}")
                print(f"P/E: {info.get('pe_ratio')}")
                print(f"ROE: {info.get('roe')}")
        return

    if "--list-tickers" in args:
        if sp500_only:
            tickers = get_sp500_tickers()
            print(f"\nTotal: {len(tickers)} tickers")
        elif index_only:
            ticker_membership = get_index_tickers()
            print(f"\nTotal: {len(ticker_membership)} index tickers")
            print("\nSample tickers with membership:")
            for t, m in list(ticker_membership.items())[:20]:
                print(f"  {t}: {m}")
        else:
            ticker_membership = get_all_us_tickers()
            print(f"\nTotal: {len(ticker_membership)} tickers")
            print("\nSample tickers:")
            for t, m in list(ticker_membership.items())[:20]:
                print(f"  {t}: {m}")
        return

    # Determine universe
    if sp500_only:
        universe = "sp500"
    elif index_only:
        universe = "index"
    else:
        universe = "full"

    # Create collector
    collector = USCollector(
        universe=universe,
        save_db=not csv_only,
        save_csv=True,
        log_level=log_level,
        quiet=quiet,
    )

    if is_test:
        print("Running in test mode (3 tickers)...")
        stats = collector.collect(
            tickers=["AAPL", "MSFT", "GOOGL"],
            is_test=True,
            batch_size=batch_size,
        )
    elif tickers_file:
        # Load tickers from file
        from pathlib import Path

        tickers_path = Path(tickers_file)
        if not tickers_path.exists():
            print(f"Error: Tickers file not found: {tickers_file}")
            return
        tickers = [
            line.strip()
            for line in tickers_path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not tickers:
            print(f"Error: No tickers found in {tickers_file}")
            return
        print(f"Running collection for {len(tickers)} tickers from {tickers_file}...")
        stats = collector.collect(tickers=tickers, batch_size=batch_size)
    else:
        if universe == "full":
            print("Running FULL US market collection...")
            print("NYSE + NASDAQ via NASDAQ FTP (~6,000-8,000 stocks)")
            print("This may take 1-2 hours. Press Ctrl+C to cancel.\n")
        elif universe == "index":
            print("Running INDEX universe collection...")
            print("S&P 500 + 400 + 600 + Russell 2000 (~2,800 stocks)")
            print("This may take 30-60 minutes. Press Ctrl+C to cancel.\n")
        else:
            print("Running S&P 500 collection...")

        stats = collector.collect(resume=resume, batch_size=batch_size)

    print(f"\nCollection complete: {stats}")


if __name__ == "__main__":
    main()
