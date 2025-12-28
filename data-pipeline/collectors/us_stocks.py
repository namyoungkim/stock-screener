"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.

Usage:
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --sp500
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --test
    uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --resume
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


def get_all_us_tickers() -> dict[str, list[str]]:
    """
    Get all US tickers with index membership.

    Returns:
        Dictionary mapping ticker to list of indices it belongs to.
    """
    print("Fetching all US index tickers...")

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

    print(f"\nTotal unique tickers: {len(all_tickers)}")
    print(f"  - S&P 500: {len(sp500)}")
    print(f"  - S&P 400: {len(sp400)}")
    print(f"  - S&P 600: {len(sp600)}")
    print(f"  - Russell 2000: {len(russell2000)}")

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
            universe: "sp500" or "full" (S&P 500+400+600 + Russell 2000)
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
        else:
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

    def fetch_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch price data for multiple tickers using yf.download."""
        results: dict[str, dict] = {}

        try:
            df = yf.download(tickers, period="1d", group_by="ticker", progress=False)

            if df.empty:
                return results

            today = date.today().isoformat()

            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        row = df.iloc[-1]
                    else:
                        if ticker not in df.columns.get_level_values(0):
                            continue
                        row = df[ticker].iloc[-1]

                    if pd.notna(row.get("Close")):
                        results[ticker] = {
                            "date": today,
                            "open": float(row["Open"]) if pd.notna(row.get("Open")) else None,
                            "high": float(row["High"]) if pd.notna(row.get("High")) else None,
                            "low": float(row["Low"]) if pd.notna(row.get("Low")) else None,
                            "close": float(row["Close"]) if pd.notna(row.get("Close")) else None,
                            "volume": int(row["Volume"]) if pd.notna(row.get("Volume")) else None,
                        }
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Price batch error: {e}")

        return results

    def fetch_history_bulk(
        self,
        tickers: list[str],
        period: str = "3mo",
        batch_size: int = 500,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for all tickers in bulk using yf.download."""
        results: dict[str, pd.DataFrame] = {}

        self.logger.info(f"Downloading {period} history for {len(tickers)} tickers in bulk...")

        for i in tqdm(range(0, len(tickers), batch_size), desc="Downloading history", leave=False):
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

                time.sleep(0.2)  # Reduced for self-hosted runner

            except Exception as e:
                self.logger.error(f"History batch error: {e}")
                continue

        self.logger.info(f"Downloaded history for {len(results)} tickers")
        return results

    def fetch_stock_data_batch(
        self,
        tickers: list[str],
        history_data: dict[str, pd.DataFrame] | None = None,
        batch_size: int = 50,
    ) -> dict[str, dict]:
        """
        Fetch stock info for multiple tickers in batches.

        Uses yf.Tickers for batch processing with fallback for failed tickers.
        """
        results: dict[str, dict] = {}
        failed_tickers: list[str] = []

        for i in tqdm(range(0, len(tickers), batch_size), desc="Fetching stock data", leave=False):
            batch = tickers[i : i + batch_size]
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
                                "two_hundred_day_average": info.get("twoHundredDayAverage"),
                                "peg_ratio": info.get("trailingPegRatio"),
                                "eps": eps,
                                "book_value_per_share": bvps,
                                "graham_number": calculate_graham_number(eps, bvps),
                                **technicals,
                            }
                        else:
                            failed_tickers.append(ticker)
                    except Exception:
                        failed_tickers.append(ticker)

            except Exception as e:
                self.logger.warning(f"Batch error: {e}")
                failed_tickers.extend(batch)

            time.sleep(0.1)  # Reduced for self-hosted runner

        # Retry failed tickers with exponential backoff
        if failed_tickers:
            self.logger.info(f"Retrying {len(failed_tickers)} failed tickers...")
            consecutive_failures = 0
            base_delay = 0.5

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
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                except Exception:
                    consecutive_failures += 1

                # Adaptive delay
                if consecutive_failures >= 3:
                    current_delay = min(base_delay * (2 ** (consecutive_failures - 2)), 30.0)
                    current_delay += random.uniform(0, 1)
                else:
                    current_delay = base_delay
                time.sleep(current_delay)

        return results

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        batch_size: int = 50,
        is_test: bool = False,
    ) -> dict:
        """
        Override collect to use optimized batch fetching.

        This version uses batch processing for stock data fetching
        which is significantly faster than individual calls.
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
        history_data = self.fetch_history_bulk(valid_tickers, period="2mo", batch_size=500)

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
                            self._build_price_record(ticker, prices_all[ticker], validated)
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
        else:
            ticker_membership = get_all_us_tickers()
            print("\nSample tickers with membership:")
            for t, m in list(ticker_membership.items())[:20]:
                print(f"  {t}: {m}")
        return

    # Create collector
    universe = "sp500" if sp500_only else "full"
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
            print("Running FULL US universe collection...")
            print("S&P 500 + 400 + 600 + Russell 2000 (~2,800 stocks)")
            print("This will take 3-4 hours. Press Ctrl+C to cancel.\n")
        else:
            print("Running S&P 500 collection...")

        stats = collector.collect(resume=resume)

    print(f"\nCollection complete: {stats}")


if __name__ == "__main__":
    main()
