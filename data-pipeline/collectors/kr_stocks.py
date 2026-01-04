"""
Korean Stock Data Collector

Collects financial data for Korean stocks using FinanceDataReader and yfinance.
Supports hybrid storage: Supabase for latest data, CSV for history.

Data sources:
- CSV (kr_companies.csv): ticker list (fallback when KRX API is blocked)
- FinanceDataReader: prices, market cap (via Naver Finance)
- Naver Finance: EPS, BPS, PER, PBR (web scraping)
- yfinance: ROE, ROA, margins, ratios, technical indicators (bulk)

Note: As of Dec 27, 2025, KRX requires login for data access, breaking pykrx.
This collector now uses a hybrid approach with FinanceDataReader for prices
and Naver Finance scraping for EPS/BPS.

Usage:
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kospi
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --test
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --resume
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --tickers-file data/missing_kr_tickers.txt

Ticker Sources:
    --kospi: KOSPI only
    --kosdaq: KOSDAQ only
    --tickers-file FILE: Custom ticker list from file (one ticker per line)
    (default): All (KOSPI + KOSDAQ)
"""

import asyncio
import contextlib
import logging
import random
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import aiohttp
import FinanceDataReader as fdr
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from common.config import (
    BACKOFF_TIMES,
    BASE_DELAY_HISTORY,
    BASE_DELAY_INFO,
    BATCH_SIZE_HISTORY,
    BATCH_SIZE_INFO,
    COMPANIES_DIR,
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
from common.logging import CollectionProgress
from common.rate_limit import (
    YFinanceTimeoutError,
    get_stock_history_with_timeout,
    get_stock_info_with_timeout,
)
from common.retry import RetryConfig, with_retry
from common.session import create_browser_session
from tqdm import tqdm

from .base import BaseCollector

# Rate limit retry settings
MAX_RETRY_ROUNDS = 10  # Maximum retry rounds for rate-limited tickers

# pykrx is optional - KRX API blocked since Dec 27, 2025
# Suppress pkg_resources deprecation warning from pykrx
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

try:
    from pykrx import stock as pykrx  # type: ignore[import-untyped]

    PYKRX_AVAILABLE = True
except ImportError:
    pykrx = None
    PYKRX_AVAILABLE = False


class KRCollector(BaseCollector):
    """Collector for Korean stock data using FinanceDataReader + yfinance."""

    MARKET = "KOSPI"  # Will be overridden per ticker
    MARKET_PREFIX = "kr"
    DATA_SOURCE = "yfinance+fdr"

    def __init__(
        self,
        market: str = "ALL",
        save_db: bool = True,
        save_csv: bool = True,
        log_level: int = logging.INFO,
        quiet: bool = False,
    ):
        """
        Initialize KR stock collector.

        Args:
            market: "KOSPI", "KOSDAQ", or "ALL"
            save_db: Whether to save to Supabase
            save_csv: Whether to save to CSV files
            log_level: Logging level
            quiet: If True, minimize output (disable tqdm, reduce logging)
        """
        super().__init__(save_db=save_db, save_csv=save_csv, log_level=log_level, quiet=quiet)
        self.market = market
        self._ticker_markets: dict[str, str] = {}
        self._ticker_names: dict[str, str] = {}
        self._fundamentals: dict[str, dict] = {}  # PER, PBR, EPS, BPS from pykrx
        # Create browser session to bypass TLS fingerprinting
        self._session = create_browser_session()

    def get_tickers(self) -> list[str]:
        """Get list of KRX tickers from CSV file (primary) or pykrx (fallback).

        Since Dec 27, 2025, KRX requires login, breaking pykrx.
        Primary source is now kr_companies.csv file.
        """
        tickers_data = []

        # Primary: Load from CSV file
        csv_path = COMPANIES_DIR / "kr_companies.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    market = row.get("market", "KOSPI")
                    if self.market == "ALL" or self.market == market:
                        tickers_data.append(
                            {
                                "ticker": str(row["ticker"]),
                                "name": row.get("name", ""),
                                "market": market,
                            }
                        )
                self.logger.info(f"Loaded {len(tickers_data)} tickers from {csv_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load CSV: {e}")

        # Fallback: Try pykrx if CSV is empty or failed
        if not tickers_data and PYKRX_AVAILABLE and pykrx is not None:
            self.logger.info("Trying pykrx as fallback...")
            today = datetime.now().strftime("%Y%m%d")

            if self.market in ("KOSPI", "ALL"):
                try:
                    kospi_tickers = pykrx.get_market_ticker_list(today, market="KOSPI")
                    for ticker in kospi_tickers:
                        name = pykrx.get_market_ticker_name(ticker)
                        tickers_data.append(
                            {"ticker": ticker, "name": name, "market": "KOSPI"}
                        )
                except Exception as e:
                    self.logger.warning(f"pykrx KOSPI failed: {e}")

            if self.market in ("KOSDAQ", "ALL"):
                try:
                    kosdaq_tickers = pykrx.get_market_ticker_list(
                        today, market="KOSDAQ"
                    )
                    for ticker in kosdaq_tickers:
                        name = pykrx.get_market_ticker_name(ticker)
                        tickers_data.append(
                            {"ticker": ticker, "name": name, "market": "KOSDAQ"}
                        )
                except Exception as e:
                    self.logger.warning(f"pykrx KOSDAQ failed: {e}")

        # Build mappings
        for item in tickers_data:
            self._ticker_markets[item["ticker"]] = item["market"]
            self._ticker_names[item["ticker"]] = item["name"]

        tickers = [item["ticker"] for item in tickers_data]
        self.logger.info(f"Found {len(tickers)} {self.market} tickers")
        return tickers

    def fetch_stock_info(self, ticker: str) -> dict | None:
        """Fetch stock information for a single ticker."""
        market = self._ticker_markets.get(ticker, "KOSPI")
        suffix = ".KS" if market == "KOSPI" else ".KQ"
        yf_ticker = f"{ticker}{suffix}"

        return self._fetch_yfinance_metrics(yf_ticker, ticker)

    @with_retry(RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0))
    def _fetch_yfinance_metrics(self, yf_ticker: str, krx_ticker: str) -> dict | None:
        """Fetch yfinance metrics with retry and timeout."""
        stock = yf.Ticker(yf_ticker, session=self._session)
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
            "name": self._ticker_names.get(krx_ticker, ""),
            "market": self._ticker_markets.get(krx_ticker, "KOSPI"),
            "currency": "KRW",
            # Valuation from yfinance
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("trailingPegRatio"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            # Profitability
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "gross_margin": info.get("grossMargins"),
            "net_margin": info.get("profitMargins"),
            # Financial health
            "debt_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            # Other
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "fifty_two_week_high": fifty_two_week_high,
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": fifty_day_average,
            "two_hundred_day_average": two_hundred_day_average,
            "eps": eps,
            "book_value_per_share": bvps,
            "graham_number": calculate_graham_number(eps, bvps),
            "price_to_52w_high_pct": calculate_price_to_52w_high_pct(
                current_price, fifty_two_week_high
            ),
            "ma_trend": calculate_ma_trend(fifty_day_average, two_hundred_day_average),
        }

    def _fetch_pykrx_fundamentals(self, trading_date: str) -> dict[str, dict]:
        """Fetch PER, PBR, EPS, BPS from pykrx for all stocks.

        Note: This may fail if KRX requires login (since Dec 27, 2025).
        In that case, fundamentals will come from yfinance instead.
        """
        results: dict[str, dict] = {}

        if not PYKRX_AVAILABLE or pykrx is None:
            self.logger.info("pykrx not available, skipping fundamentals fetch")
            return results

        for market_name in ["KOSPI", "KOSDAQ"]:
            if self.market != "ALL" and self.market != market_name:
                continue

            try:
                df = pykrx.get_market_fundamental(trading_date, market=market_name)
                if df.empty:
                    continue

                for ticker in df.index:
                    row = df.loc[ticker]
                    per = row.get("PER", 0)
                    pbr = row.get("PBR", 0)
                    eps = row.get("EPS", 0)
                    bps = row.get("BPS", 0)

                    results[ticker] = {
                        "pe_ratio": per if per != 0 else None,
                        "pb_ratio": pbr if pbr != 0 else None,
                        "eps": eps if eps != 0 else None,
                        "book_value_per_share": bps if bps != 0 else None,
                    }
            except Exception as e:
                self.logger.warning(f"Failed to fetch {market_name} fundamentals: {e}")

        return results

    def _fetch_naver_fundamentals(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch EPS, BPS, PER, PBR from Naver Finance via parallel web scraping.

        This is the primary source for Korean stock fundamentals since KRX API
        requires login (Dec 27, 2025). Naver Finance provides reliable data.

        Uses asyncio + aiohttp for parallel requests with rate limiting.
        """
        self.logger.info(
            f"Fetching fundamentals from Naver Finance for {len(tickers)} tickers (parallel)..."
        )

        # Run async function in sync context
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # If we're in an event loop, use nest_asyncio or run in executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._fetch_naver_fundamentals_async(tickers))
                results = future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            results = asyncio.run(self._fetch_naver_fundamentals_async(tickers))

        self.logger.info(f"Fetched Naver fundamentals for {len(results)} tickers")
        return results

    async def _fetch_naver_fundamentals_async(self, tickers: list[str]) -> dict[str, dict]:
        """Async implementation of Naver Finance fundamentals fetching."""
        results: dict[str, dict] = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        # Semaphore to limit concurrent requests (10 at a time)
        semaphore = asyncio.Semaphore(10)
        # Track progress
        completed = 0
        total = len(tickers)

        async def fetch_one(session: aiohttp.ClientSession, ticker: str) -> tuple[str, dict | None]:
            nonlocal completed
            async with semaphore:
                try:
                    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            return ticker, None

                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        data: dict = {}

                        # Extract PER from em#_per
                        per_em = soup.find("em", id="_per")
                        if per_em:
                            with contextlib.suppress(ValueError, TypeError):
                                data["pe_ratio"] = float(per_em.get_text().replace(",", ""))

                        # Extract EPS from em#_eps
                        eps_em = soup.find("em", id="_eps")
                        if eps_em:
                            with contextlib.suppress(ValueError, TypeError):
                                data["eps"] = float(eps_em.get_text().replace(",", ""))

                        # Extract PBR from em#_pbr
                        pbr_em = soup.find("em", id="_pbr")
                        if pbr_em:
                            with contextlib.suppress(ValueError, TypeError):
                                data["pb_ratio"] = float(pbr_em.get_text().replace(",", ""))

                        # Extract BPS from per_table
                        per_table = soup.find("table", class_="per_table")
                        if per_table:
                            table_text = per_table.get_text()
                            bps_match = re.search(
                                r"PBR.*?l\s*BPS.*?([\d,.]+)배.*?l\s*([\d,]+)원",
                                table_text,
                                re.DOTALL,
                            )
                            if bps_match:
                                with contextlib.suppress(ValueError, TypeError):
                                    data["book_value_per_share"] = float(
                                        bps_match.group(2).replace(",", "")
                                    )

                        # Small delay between requests to be polite
                        await asyncio.sleep(0.05)

                        completed += 1
                        if not self.quiet and completed % 100 == 0:
                            self.logger.info(f"Naver fundamentals: {completed}/{total}")

                        return ticker, data if data else None

                except Exception as e:
                    self.logger.debug(f"Naver fundamentals failed for {ticker}: {e}")
                    return ticker, None

        # Create session with connection limit
        connector = aiohttp.TCPConnector(limit=20)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tasks = [fetch_one(session, ticker) for ticker in tickers]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for response in responses:
                if isinstance(response, Exception):
                    continue
                ticker, data = response
                if data:
                    results[ticker] = data

        return results

    def fetch_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch price data using FinanceDataReader (primary) or pykrx (fallback).

        FinanceDataReader fetches from Naver Finance, which works even when KRX API is blocked.
        Uses ThreadPoolExecutor for parallel fetching with rate limiting.
        """
        results: dict[str, dict] = {}
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        self.logger.info(
            f"Fetching prices for {len(tickers)} tickers via FinanceDataReader (parallel)..."
        )

        def fetch_one(ticker: str) -> tuple[str, dict | None]:
            """Fetch price data for a single ticker."""
            try:
                df = fdr.DataReader(ticker, start_date, end_date)
                if df.empty:
                    return ticker, None

                # Get the most recent data
                latest = df.iloc[-1]
                latest_date = df.index[-1].strftime("%Y-%m-%d")

                # Get market cap from yfinance (FDR doesn't provide it reliably)
                market = self._ticker_markets.get(ticker, "KOSPI")
                suffix = ".KS" if market == "KOSPI" else ".KQ"
                yf_ticker = f"{ticker}{suffix}"

                market_cap = None
                try:
                    stock = yf.Ticker(yf_ticker, session=self._session)
                    info = stock.info
                    market_cap = info.get("marketCap")
                except Exception:
                    pass

                return ticker, {
                    "date": latest_date,
                    "close": int(latest["Close"])
                    if pd.notna(latest["Close"])
                    else None,
                    "volume": int(latest["Volume"])
                    if pd.notna(latest["Volume"])
                    else None,
                    "market_cap": market_cap,
                }

            except Exception as e:
                self.logger.debug(f"FDR failed for {ticker}: {e}")
                return ticker, None

        # Parallel fetch with ThreadPoolExecutor (10 workers)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_one, t): t for t in tickers}

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Fetching prices",
                leave=False,
                disable=self.quiet,
            ):
                try:
                    ticker, data = future.result()
                    if data:
                        results[ticker] = data
                except Exception as e:
                    ticker = futures[future]
                    self.logger.debug(f"FDR failed for {ticker}: {e}")

        self.logger.info(f"Fetched prices for {len(results)} tickers")

        # Fallback to pykrx if FDR got very few results
        if len(results) < len(tickers) * 0.5 and PYKRX_AVAILABLE and pykrx is not None:
            self.logger.info("FDR got few results, trying pykrx fallback...")
            pykrx_results = self._fetch_prices_pykrx(tickers)
            # Merge: only add tickers not already in results
            for ticker, data in pykrx_results.items():
                if ticker not in results:
                    results[ticker] = data
            self.logger.info(f"After pykrx fallback: {len(results)} tickers")

        return results

    def _fetch_prices_pykrx(self, tickers: list[str]) -> dict[str, dict]:
        """Fallback: Fetch prices from pykrx (may fail if KRX requires login)."""
        results: dict[str, dict] = {}

        if not PYKRX_AVAILABLE or pykrx is None:
            return results

        # Find the most recent trading day
        market_df = None
        trading_date = None

        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                df = pykrx.get_market_cap(day)
                if not df.empty and df["시가총액"].sum() > 0:
                    market_df = df
                    trading_date = day
                    break
            except Exception:
                continue

        if market_df is None or trading_date is None:
            self.logger.warning("pykrx fallback: Could not fetch market data")
            return results

        self.logger.info(f"pykrx: Fetched bulk market data for {len(market_df)} stocks")

        # Fetch fundamentals (PER, PBR, EPS, BPS)
        self._fundamentals = self._fetch_pykrx_fundamentals(trading_date)

        formatted_date = f"{trading_date[:4]}-{trading_date[4:6]}-{trading_date[6:8]}"

        for ticker in tickers:
            if ticker in market_df.index:
                row = market_df.loc[ticker]
                results[ticker] = {
                    "date": formatted_date,
                    "close": int(row["종가"]) if pd.notna(row["종가"]) else None,
                    "volume": int(row["거래량"]) if pd.notna(row["거래량"]) else None,
                    "market_cap": int(row["시가총액"])
                    if pd.notna(row["시가총액"])
                    else None,
                }

        return results

    def fetch_history_bulk(
        self,
        tickers: list[str],
        period: str = "3mo",
        batch_size: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for all KR tickers in bulk using yf.download.

        Rate limit handling:
        - Batch size: BATCH_SIZE_HISTORY (default 500)
        - Sleep between batches: BASE_DELAY_HISTORY + jitter
        - yf.download is more lenient than individual ticker.info calls
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_HISTORY
        results: dict[str, pd.DataFrame] = {}

        # Convert to yfinance format
        yf_tickers = []
        ticker_map = {}
        for ticker in tickers:
            market = self._ticker_markets.get(ticker, "KOSPI")
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            yf_ticker = f"{ticker}{suffix}"
            yf_tickers.append(yf_ticker)
            ticker_map[yf_ticker] = ticker

        self.logger.info(
            f"Downloading {period} history for {len(tickers)} KR tickers..."
        )

        for i in tqdm(
            range(0, len(yf_tickers), batch_size),
            desc="Downloading history",
            leave=False,
            disable=self.quiet,
        ):
            batch = yf_tickers[i : i + batch_size]
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
                    krx_ticker = ticker_map[batch[0]]
                    results[krx_ticker] = df
                else:
                    for yf_ticker in batch:
                        try:
                            if yf_ticker in df.columns.get_level_values(0):
                                ticker_df = df[yf_ticker].dropna(how="all")
                                if not ticker_df.empty:
                                    krx_ticker = ticker_map[yf_ticker]
                                    results[krx_ticker] = ticker_df
                        except Exception:
                            pass

                # Sleep between batches
                time.sleep(BASE_DELAY_HISTORY + random.uniform(0, DELAY_JITTER_HISTORY))

            except Exception as e:
                self.logger.error(f"History batch error: {e}")
                # Longer sleep on error
                time.sleep(5.0)
                continue

        self.logger.info(f"Downloaded history for {len(results)} KR tickers")
        return results

    def fetch_yfinance_batch(
        self,
        tickers: list[str],
        history_data: dict[str, pd.DataFrame] | None = None,
        batch_size: int | None = None,
    ) -> dict[str, dict]:
        """Fetch yfinance metrics for multiple tickers in batches.

        Rate limit handling:
        - Batch size: BATCH_SIZE_INFO (default 10)
        - Sleep between batches: BASE_DELAY_INFO + jitter
        - Rate limit detection: Progressive backoff on consecutive failures
        - Max retries: MAX_BACKOFFS before stopping
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_INFO

        results: dict[str, dict] = {}
        failed_tickers: list[tuple[str, str]] = []
        consecutive_failures = 0
        backoff_count = 0

        # Convert to yfinance format
        yf_tickers = []
        ticker_map = {}
        for ticker in tickers:
            market = self._ticker_markets.get(ticker, "KOSPI")
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            yf_ticker = f"{ticker}{suffix}"
            yf_tickers.append(yf_ticker)
            ticker_map[yf_ticker] = ticker

        total_batches = (len(yf_tickers) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(
            tqdm(
                range(0, len(yf_tickers), batch_size),
                desc="yfinance batch",
                leave=False,
                disable=self.quiet,
            )
        ):
            batch = yf_tickers[i : i + batch_size]
            batch_success = 0

            try:
                for yf_ticker in batch:
                    try:
                        stock = yf.Ticker(yf_ticker, session=self._session)
                        info = get_stock_info_with_timeout(stock)

                        if info and info.get("regularMarketPrice") is not None:
                            krx_ticker = ticker_map[yf_ticker]
                            eps = info.get("trailingEps")
                            bvps = info.get("bookValue")
                            current_price = info.get("regularMarketPrice")
                            fifty_two_week_high = info.get("fiftyTwoWeekHigh")
                            fifty_day_average = info.get("fiftyDayAverage")
                            two_hundred_day_average = info.get("twoHundredDayAverage")

                            # Get technicals from pre-fetched history
                            hist = (
                                history_data.get(krx_ticker) if history_data else None
                            )
                            if hist is None or hist.empty:
                                hist = get_stock_history_with_timeout(stock, period="2mo")
                            technicals = calculate_all_technicals(hist)

                            results[krx_ticker] = {
                                "name": self._ticker_names.get(krx_ticker, ""),
                                "market": self._ticker_markets.get(krx_ticker, "KOSPI"),
                                "currency": "KRW",
                                # Valuation from yfinance
                                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                                "forward_pe": info.get("forwardPE"),
                                "peg_ratio": info.get("trailingPegRatio"),
                                "ev_ebitda": info.get("enterpriseToEbitda"),
                                # Profitability
                                "roe": info.get("returnOnEquity"),
                                "roa": info.get("returnOnAssets"),
                                "gross_margin": info.get("grossMargins"),
                                "net_margin": info.get("profitMargins"),
                                # Financial health
                                "debt_equity": info.get("debtToEquity"),
                                "current_ratio": info.get("currentRatio"),
                                # Other
                                "dividend_yield": info.get("dividendYield"),
                                "beta": info.get("beta"),
                                "fifty_two_week_high": fifty_two_week_high,
                                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                                "fifty_day_average": fifty_day_average,
                                "two_hundred_day_average": two_hundred_day_average,
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
                            failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))
                    except YFinanceTimeoutError:
                        self.logger.warning(
                            f"Timeout for {yf_ticker} in batch {batch_idx + 1}/{total_batches}"
                        )
                        consecutive_failures += 1
                        failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))
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
                        failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))

            except Exception as e:
                error_msg = str(e).lower()
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    self.logger.warning(f"Rate limit detected for batch: {e}")
                    consecutive_failures += 1
                else:
                    self.logger.warning(f"Batch error: {e}")
                for yf_ticker in batch:
                    failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))

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

            for yf_ticker, krx_ticker in tqdm(
                failed_tickers, desc="Fallback", leave=False, disable=self.quiet
            ):
                try:
                    data = self._fetch_yfinance_metrics(yf_ticker, krx_ticker)
                    if data:
                        hist = history_data.get(krx_ticker) if history_data else None
                        if hist is not None and not hist.empty:
                            technicals = calculate_all_technicals(hist)
                            data.update(technicals)
                        results[krx_ticker] = data
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
                            backoff_time = 30.0 + random.uniform(0, 30.0)
                            self.logger.warning(
                                f"Fallback backoff: waiting {backoff_time:.0f}s..."
                            )
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
        Collect Korean stock data with optimized batch processing.

        Args:
            batch_size: Batch size for .info calls (default: BATCH_SIZE_INFO from config)
            auto_retry: If True, retry missing tickers after quality check

        Phases:
        1. Fetch prices from FinanceDataReader (via Naver)
        2. Fetch EPS/BPS from Naver Finance (web scraping)
        3. Download history for technical indicators (yfinance bulk)
        4. Fetch yfinance metrics (ROE, ROA, margins, etc.)
        5. Combine and save
        """
        if batch_size is None:
            batch_size = BATCH_SIZE_INFO

        # Get tickers if not provided
        if tickers is None:
            tickers = self.get_tickers()

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

        # Phase 1: Fetch prices from FinanceDataReader
        self.logger.info("Phase 1: Fetching prices from FinanceDataReader...")
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

        # Phase 2: Fetch EPS/BPS from Naver Finance
        self.logger.info("Phase 2: Fetching EPS/BPS from Naver Finance...")
        naver_fundamentals = self._fetch_naver_fundamentals(valid_tickers)
        self.logger.info(
            f"Fetched Naver fundamentals for {len(naver_fundamentals)} tickers"
        )

        # Phase 3: Bulk download history with retry loop
        self.logger.info("Phase 3: Downloading history for technical indicators...")
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
                remaining_history_tickers, period="2mo", batch_size=500
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

        # Phase 4: Batch yfinance metrics with retry loop for rate-limited tickers
        self.logger.info("Phase 4: Fetching yfinance metrics in batches...")

        retry_round = 0
        remaining_tickers = valid_tickers.copy()
        yf_metrics_all: dict[str, dict] = {}

        while remaining_tickers and retry_round <= MAX_RETRY_ROUNDS:
            if retry_round > 0:
                wait_time = RATE_LIMIT_WAIT_INFO + random.uniform(0, 60)
                self.logger.info(
                    f"Rate limit retry {retry_round}/{MAX_RETRY_ROUNDS}: "
                    f"{len(remaining_tickers)} tickers remaining. "
                    f"Waiting {wait_time / 60:.1f} minutes..."
                )
                time.sleep(wait_time)

            batch_result = self.fetch_yfinance_batch(
                remaining_tickers,
                history_data=history_data,
                batch_size=batch_size,
            )
            yf_metrics_all.update(batch_result)

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

        self.logger.info(f"Fetched yfinance metrics for {len(yf_metrics_all)} stocks")

        # Phase 5: Combine and save
        self.logger.info("Phase 5: Combining data and saving...")
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
                name = self._ticker_names.get(ticker, "")
                mkt = self._ticker_markets.get(ticker, "KOSPI")
                price_data = prices_all.get(ticker, {})
                market_cap = price_data.get("market_cap")

                # Get Naver fundamentals (PER, PBR, EPS, BPS)
                naver_data = naver_fundamentals.get(ticker, {})

                # Get yfinance metrics
                yf_metrics = yf_metrics_all.get(ticker, {})

                # Combine metrics: start with base, add naver, then yfinance
                combined_metrics = {
                    "name": name,
                    "market": mkt,
                    "market_cap": market_cap,
                }

                # Add Naver data (PER, PBR, EPS, BPS) - primary source for Korean stocks
                if naver_data:
                    combined_metrics.update(naver_data)

                # Add yfinance data (ROE, ROA, margins, technicals, etc.)
                # Note: yfinance may overwrite some values, but that's OK
                if yf_metrics:
                    # Technical indicators that should always use yfinance values
                    technical_keys = {
                        "rsi",
                        "mfi",
                        "macd",
                        "macd_signal",
                        "macd_histogram",
                        "bb_upper",
                        "bb_middle",
                        "bb_lower",
                        "bb_percent",
                        "volume_change",
                        "price_to_52w_high_pct",
                        "ma_trend",
                    }
                    for key, value in yf_metrics.items():
                        # Only overwrite if yfinance has a value and current is None,
                        # or if it's a technical indicator
                        if value is not None and (
                            key not in combined_metrics
                            or combined_metrics.get(key) is None
                            or key in technical_keys
                        ):
                            combined_metrics[key] = value

                # Calculate Graham Number from available EPS/BPS (pykrx or yfinance)
                eps_val = combined_metrics.get("eps")
                bvps_val = combined_metrics.get("book_value_per_share")
                if eps_val and bvps_val and "graham_number" not in combined_metrics:
                    eps_float = (
                        float(eps_val) if isinstance(eps_val, (int, float)) else None
                    )
                    bvps_float = (
                        float(bvps_val) if isinstance(bvps_val, (int, float)) else None
                    )
                    if eps_float and bvps_float:
                        combined_metrics["graham_number"] = calculate_graham_number(
                            eps_float, bvps_float
                        )

                # Validate metrics
                validated = self.validator.validate(combined_metrics, ticker)

                # Save to database
                if self.save_db and self.client:
                    company_id = self.storage.upsert_company(
                        ticker=ticker,
                        name=name,
                        market=mkt,
                        currency="KRW",
                    )
                    if company_id:
                        self.storage.upsert_metrics(
                            company_id=company_id,
                            metrics=validated,
                            data_source=self.DATA_SOURCE,
                        )
                        self.storage.upsert_price(
                            company_id=company_id,
                            price_data=price_data,
                            market_cap=market_cap,
                        )

                # Collect for CSV
                if self.save_csv:
                    all_companies.append(
                        {
                            "ticker": ticker,
                            "name": name,
                            "market": mkt,
                            "currency": "KRW",
                        }
                    )
                    all_metrics.append(
                        {
                            "ticker": ticker,
                            "date": price_data.get("date", date.today().isoformat()),
                            "market": mkt,
                            **{
                                k: v
                                for k, v in validated.items()
                                if k not in ["name", "market", "currency"]
                            },
                        }
                    )
                    if price_data:
                        all_prices.append(
                            {
                                "ticker": ticker,
                                **price_data,
                            }
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

    # Determine market
    if "--kospi" in args:
        market = "KOSPI"
    elif "--kosdaq" in args:
        market = "KOSDAQ"
    else:
        market = "ALL"

    if "--dry-run" in args:
        print("Dry run test with 3 tickers...")
        test_tickers = ["005930", "000660", "035720"]
        # Load names from CSV
        csv_path = COMPANIES_DIR / "kr_companies.csv"
        name_map = {}
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            name_map = dict(zip(df["ticker"].astype(str), df["name"], strict=False))
        for ticker in test_tickers:
            name = name_map.get(ticker, "Unknown")
            print(f"\n=== {ticker} ({name}) ===")
        return

    if "--list-tickers" in args:
        collector = KRCollector(market=market, save_db=False, save_csv=False)
        tickers = collector.get_tickers()
        print(f"\nTotal: {len(tickers)} tickers")
        for t in tickers[:20]:
            print(
                f"  {t}: {collector._ticker_names.get(t, '')} ({collector._ticker_markets.get(t, '')})"
            )
        return

    # Create collector
    collector = KRCollector(
        market=market,
        save_db=not csv_only,
        save_csv=True,
        log_level=log_level,
        quiet=quiet,
    )

    if is_test:
        print("Running in test mode (3 tickers)...")
        stats = collector.collect(
            tickers=["005930", "000660", "035720"],
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
        if market == "ALL":
            print("Running full KRX (KOSPI + KOSDAQ) collection...")
        else:
            print(f"Running {market} collection...")

        stats = collector.collect(resume=resume, batch_size=batch_size)

    print(f"\nCollection complete: {stats}")


if __name__ == "__main__":
    main()
