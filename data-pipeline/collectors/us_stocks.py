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

Ticker Sources:
    --sp500: S&P 500 only (~500 stocks)
    --index-only: S&P 500 + 400 + 600 + Russell 2000 (~2,800 stocks)
    (default): Full US market via NASDAQ FTP (~6,000-8,000 stocks)
"""

import logging
import random
import time
from datetime import date
from io import StringIO

import pandas as pd
import requests
import yfinance as yf
from common.indicators import calculate_all_technicals, calculate_graham_number
from common.retry import RetryConfig, with_retry
from tqdm import tqdm

from .base import BaseCollector

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


class USCollector(BaseCollector):
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
        """
        super().__init__(save_db=save_db, save_csv=save_csv, log_level=log_level)
        self.universe = universe
        self._ticker_membership: dict[str, list[str]] = {}

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
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return None

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
        today = date.today().isoformat()

        self.logger.info(
            f"Fetching prices for {len(tickers)} tickers in batches of {batch_size}..."
        )

        for i in tqdm(
            range(0, len(tickers), batch_size), desc="Fetching prices", leave=False
        ):
            batch = tickers[i : i + batch_size]
            try:
                df = yf.download(
                    batch, period="1d", group_by="ticker", progress=False, threads=True
                )

                if df.empty:
                    continue

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
                                "date": today,
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
        batch_size: int = 300,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for all tickers in bulk using yf.download.

        Rate limit handling:
        - Batch size: 300 (reduced from 500)
        - Sleep between batches: 1-2 seconds
        - yf.download is more lenient than individual ticker.info calls
        """
        results: dict[str, pd.DataFrame] = {}

        self.logger.info(
            f"Downloading {period} history for {len(tickers)} tickers in bulk..."
        )

        for i in tqdm(
            range(0, len(tickers), batch_size), desc="Downloading history", leave=False
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

                # Sleep between batches: 1-2 seconds
                time.sleep(1.0 + random.uniform(0, 1.0))

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
        batch_size: int = 10,
    ) -> dict[str, dict]:
        """
        Fetch stock info for multiple tickers in batches.

        Rate limit handling:
        - Batch size: 10 (conservative to avoid rate limits)
        - Sleep between batches: 2-3 seconds with jitter
        - Rate limit detection: Stop early if 5+ consecutive failures
        - Fallback retry: Longer delays (3-5 seconds)
        """
        results: dict[str, dict] = {}
        failed_tickers: list[str] = []
        consecutive_failures = 0
        max_consecutive_failures = 5  # Stop if 5 batches fail in a row

        total_batches = (len(tickers) + batch_size - 1) // batch_size

        for batch_idx, i in enumerate(
            tqdm(
                range(0, len(tickers), batch_size),
                desc="Fetching stock data",
                leave=False,
            )
        ):
            batch = tickers[i : i + batch_size]
            batch_success = 0

            try:
                tickers_obj = yf.Tickers(" ".join(batch))

                for ticker in batch:
                    try:
                        stock = tickers_obj.tickers[ticker]
                        info = stock.info

                        if info and info.get("regularMarketPrice") is not None:
                            eps = info.get("trailingEps")
                            bvps = info.get("bookValue")

                            # Use pre-fetched history if available
                            hist = history_data.get(ticker) if history_data else None
                            if hist is None or hist.empty:
                                hist = stock.history(period="2mo")
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
                                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                                "fifty_day_average": info.get("fiftyDayAverage"),
                                "two_hundred_day_average": info.get(
                                    "twoHundredDayAverage"
                                ),
                                "peg_ratio": info.get("trailingPegRatio"),
                                "eps": eps,
                                "book_value_per_share": bvps,
                                "graham_number": calculate_graham_number(eps, bvps),
                                **technicals,
                            }
                            batch_success += 1
                        else:
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

            # Stop early if rate limited
            if consecutive_failures >= max_consecutive_failures:
                self.logger.warning(
                    f"Stopping batch processing: {consecutive_failures} consecutive failures detected. "
                    f"Completed {len(results)}/{len(tickers)} tickers."
                )
                break

            # Sleep between batches: 2-3 seconds with random jitter
            sleep_time = 2.0 + random.uniform(0, 1.0)
            time.sleep(sleep_time)

        # Retry failed tickers with longer delays
        if failed_tickers and consecutive_failures < max_consecutive_failures:
            self.logger.info(
                f"Retrying {len(failed_tickers)} failed tickers with longer delays..."
            )
            retry_failures = 0
            max_retry_failures = 10  # Stop retry if 10 consecutive failures

            for ticker in tqdm(failed_tickers, desc="Fallback", leave=False):
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

                # Longer sleep for fallback: 3-5 seconds
                time.sleep(3.0 + random.uniform(0, 2.0))
        elif consecutive_failures >= max_consecutive_failures:
            self.logger.info("Skipping fallback retry due to rate limit detection.")

        return results

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        batch_size: int = 10,
        is_test: bool = False,
        check_rate_limit_first: bool = True,
        auto_retry: bool = True,
    ) -> dict:
        """
        Override collect to use optimized batch fetching.

        This version uses batch processing for stock data fetching
        which is significantly faster than individual calls.

        Args:
            auto_retry: If True, retry missing tickers after quality check
        """
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

        # Phase 2: Bulk download history
        self.logger.info("Phase 2: Downloading history for technical indicators...")
        history_data = self.fetch_history_bulk(
            valid_tickers, period="2mo", batch_size=300
        )

        # Phase 3: Batch fetch stock data
        self.logger.info(f"Phase 3: Fetching stock data in batches of {batch_size}...")
        stock_data_all = self.fetch_stock_data_batch(
            valid_tickers,
            history_data=history_data,
            batch_size=batch_size,
        )
        self.logger.info(f"Fetched data for {len(stock_data_all)} stocks")

        # Phase 4: Process and save
        self.logger.info("Phase 4: Processing and saving...")

        from common.logging import CollectionProgress

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
                    all_metrics.append(self._build_metrics_record(ticker, validated))
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

        progress.log_summary()

        # Log validation summary
        validation_summary = self.validator.get_summary()
        if validation_summary["with_warnings"] > 0:
            self.logger.warning(f"Validation summary: {validation_summary}")

        # Save failed items
        if self.retry_queue.count > 0:
            from common.config import DATA_DIR

            failed_file = DATA_DIR / f"{self.MARKET_PREFIX}_failed_tickers.json"
            self.retry_queue.save_path = failed_file
            self.retry_queue.save_to_file()

        return progress.get_stats()


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
    log_level = logging.DEBUG if "--verbose" in args else logging.INFO

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
    )

    if is_test:
        print("Running in test mode (3 tickers)...")
        stats = collector.collect(
            tickers=["AAPL", "MSFT", "GOOGL"],
            is_test=True,
        )
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

        stats = collector.collect(resume=resume)

    print(f"\nCollection complete: {stats}")


if __name__ == "__main__":
    main()
