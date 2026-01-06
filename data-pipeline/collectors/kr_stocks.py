"""
Korean Stock Data Collector

Collects financial data for Korean stocks using FDR + KIS API.
Supports hybrid storage: Supabase for latest data, CSV for history.

Data sources:
- CSV (kr_companies.csv): ticker list
- FinanceDataReader (FDR): prices, OHLCV history, KOSPI index (via Naver Finance)
- KIS API (primary): PER, PBR, EPS, BPS, 52w high/low, market_cap
- Naver Finance (fallback): PER, PBR, EPS, BPS, ROE, ROA, market_cap (web scraping)
- Local calculation: RSI, MACD, Bollinger Bands, MFI, MA50/MA200, Beta (vs KOSPI)

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
import re
import socket
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta

import aiohttp
import FinanceDataReader as fdr
import pandas as pd
from bs4 import BeautifulSoup
from common.config import (
    COMPANIES_DIR,
    DATA_DIR,
    FDR_HISTORY_DAYS,
    FDR_REQUEST_TIMEOUT,
    KIS_RATE_LIMIT,
)
from common.indicators import (
    calculate_52_week_high_low,
    calculate_all_technicals,
    calculate_beta,
    calculate_graham_number,
    calculate_ma_trend,
    calculate_moving_averages,
    calculate_price_to_52w_high_pct,
)
from common.kis_client import KISClient
from common.logging import CollectionProgress, setup_logger
from common.naver_finance import NaverFinanceClient
from common.rate_limit import ProgressTracker
from common.retry import RetryQueue
from common.storage import StorageManager, get_supabase_client
from processors.validators import MetricsValidator
from tqdm import tqdm


class KRCollector:
    """Collector for Korean stock data using FDR + KIS API."""

    MARKET = "KOSPI"  # Will be overridden per ticker
    MARKET_PREFIX = "kr"
    DATA_SOURCE = "fdr+kis"

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
        self.market = market
        self.save_db = save_db
        self.save_csv = save_csv
        self.quiet = quiet

        # Setup logger
        effective_log_level = logging.WARNING if quiet else log_level
        self.logger = setup_logger(
            self.__class__.__name__,
            level=effective_log_level,
        )

        # Initialize components
        self.client = get_supabase_client() if save_db else None
        self.storage = StorageManager(
            client=self.client,
            data_dir=DATA_DIR,
            market_prefix=self.MARKET_PREFIX,
        )
        self.validator = MetricsValidator()
        self.progress_tracker = ProgressTracker(self.MARKET_PREFIX)
        self.retry_queue = RetryQueue()

        # KR-specific state
        self._ticker_markets: dict[str, str] = {}
        self._ticker_names: dict[str, str] = {}

    def get_tickers(self) -> list[str]:
        """Get list of KRX tickers from CSV file.

        Source: kr_companies.csv file.
        """
        tickers_data = []

        # Load from CSV file
        csv_path = COMPANIES_DIR / "kr_companies.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, dtype={"ticker": str})
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

        # Build mappings
        for item in tickers_data:
            self._ticker_markets[item["ticker"]] = item["market"]
            self._ticker_names[item["ticker"]] = item["name"]

        tickers = [item["ticker"] for item in tickers_data]
        self.logger.info(f"Found {len(tickers)} {self.market} tickers")
        return tickers

    async def _fetch_kis_fundamentals_async(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch PER, PBR, EPS, BPS, 52w high/low from KIS API.

        KIS API is faster and more reliable than Naver web scraping.
        Rate limit: ~15 requests/second - processes in batches to avoid memory issues.
        """
        results: dict[str, dict] = {}

        async with KISClient() as client:
            if not client.is_configured():
                self.logger.warning("KIS API not configured, will use Naver Finance fallback")
                return results

            self.logger.info(f"Fetching fundamentals from KIS API for {len(tickers)} tickers...")

            async def fetch_one(ticker: str) -> tuple[str, dict | None]:
                """Fetch data for a single ticker."""
                try:
                    quote = await client.get_domestic_quote(ticker)
                    if quote and quote.get("current_price") is not None:
                        data: dict = {}

                        # Map KIS fields to our schema
                        if quote.get("per") is not None:
                            data["pe_ratio"] = quote["per"]
                        if quote.get("pbr") is not None:
                            data["pb_ratio"] = quote["pbr"]
                        if quote.get("eps") is not None:
                            data["eps"] = quote["eps"]
                        if quote.get("bps") is not None:
                            data["book_value_per_share"] = quote["bps"]
                        if quote.get("high_52w") is not None:
                            data["fifty_two_week_high"] = quote["high_52w"]
                        if quote.get("low_52w") is not None:
                            data["fifty_two_week_low"] = quote["low_52w"]
                        if quote.get("market_cap") is not None:
                            # KIS returns in 억원, convert to 원
                            data["market_cap"] = quote["market_cap"] * 100_000_000

                        return ticker, data if data else None
                    return ticker, None
                except Exception as e:
                    self.logger.debug(f"KIS failed for {ticker}: {e}")
                    return ticker, None

            # Process in batches to avoid creating too many coroutines at once
            batch_size = KIS_RATE_LIMIT  # 15 concurrent requests
            progress_bar = tqdm(
                total=len(tickers),
                desc="KIS fundamentals",
                leave=False,
                disable=self.quiet,
            )

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                tasks = [fetch_one(ticker) for ticker in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Collect results from this batch
                for result in batch_results:
                    if isinstance(result, Exception):
                        continue
                    ticker, data = result
                    if data:
                        results[ticker] = data

                progress_bar.update(len(batch))

            progress_bar.close()

        self.logger.info(f"Fetched KIS fundamentals for {len(results)} tickers")
        return results

    def _fetch_naver_fundamentals(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch EPS, BPS, PER, PBR from Naver Finance via parallel web scraping.

        This is the fallback source for Korean stock fundamentals when KIS API
        is not configured. Naver Finance provides reliable data but is slower.

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
                if isinstance(response, BaseException):
                    continue
                if isinstance(response, tuple):
                    ticker, data = response
                    if data:
                        results[ticker] = data

        return results

    def fetch_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch price data using FinanceDataReader (primary) or pykrx (fallback).

        FinanceDataReader fetches from Naver Finance, which works even when KRX API is blocked.
        Uses ThreadPoolExecutor with batch-based timeout to skip slow tickers.
        """
        results: dict[str, dict] = {}
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        self.logger.info(
            f"Fetching prices for {len(tickers)} tickers via FinanceDataReader (parallel)..."
        )

        # Set socket timeout to prevent infinite hanging
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(FDR_REQUEST_TIMEOUT)

        def fetch_one(ticker: str) -> tuple[str, dict | None]:
            """Fetch price data for a single ticker."""
            try:
                df = fdr.DataReader(ticker, start_date, end_date)
                if df.empty:
                    return ticker, None

                # Get the most recent data
                latest = df.iloc[-1]
                latest_date = df.index[-1].strftime("%Y-%m-%d")

                # Note: market_cap comes from KIS/Naver (Phase 2), not here
                return ticker, {
                    "date": latest_date,
                    "close": int(latest["Close"])
                    if pd.notna(latest["Close"])
                    else None,
                    "volume": int(latest["Volume"])
                    if pd.notna(latest["Volume"])
                    else None,
                }

            except Exception as e:
                self.logger.debug(f"FDR failed for {ticker}: {e}")
                return ticker, None

        # Batch-based processing with timeout to skip slow tickers
        batch_size = 100
        per_ticker_timeout = FDR_REQUEST_TIMEOUT + 5  # 15 seconds per ticker
        batch_timeout = per_ticker_timeout * 1.5  # Allow some buffer for batch

        pbar = tqdm(
            total=len(tickers),
            desc="Fetching prices",
            leave=False,
            disable=self.quiet,
        )

        executor = ThreadPoolExecutor(max_workers=10)
        try:
            # Process in batches
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                futures = {executor.submit(fetch_one, t): t for t in batch}
                pending = set(futures.keys())
                skipped_in_batch = []

                # Process batch with timeout
                while pending:
                    done, pending = wait(pending, timeout=batch_timeout, return_when=FIRST_COMPLETED)

                    if not done and pending:
                        # Timeout: cancel remaining slow tickers in this batch
                        skipped_in_batch = [futures[f] for f in pending]
                        for future in pending:
                            future.cancel()
                        pbar.update(len(pending))
                        break

                    for future in done:
                        pbar.update(1)
                        try:
                            ticker, data = future.result(timeout=0)
                            if data:
                                results[ticker] = data
                        except Exception as e:
                            ticker = futures[future]
                            self.logger.debug(f"FDR failed for {ticker}: {e}")

                if skipped_in_batch:
                    self.logger.warning(
                        f"FDR batch {i // batch_size + 1}: skipped {len(skipped_in_batch)} slow tickers"
                    )

        finally:
            # Shutdown executor without waiting for pending tasks
            executor.shutdown(wait=False, cancel_futures=True)
            # Restore original socket timeout
            socket.setdefaulttimeout(old_timeout)
            pbar.close()

        self.logger.info(f"Fetched prices for {len(results)} tickers")

        # Note: pykrx fallback removed - KRX API often requires login/captcha and hangs
        # FDR (Naver Finance) is reliable enough as the sole source

        return results

    def fetch_fdr_history(
        self,
        tickers: list[str],
        days: int = 210,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch 7-month OHLCV history using FinanceDataReader.

        Uses FDR (Naver Finance) for stable Korean stock data.

        Args:
            tickers: List of KRX ticker codes
            days: Number of days of history (default 210 for MA200)

        Returns:
            dict mapping ticker to DataFrame with OHLCV columns
        """
        results: dict[str, pd.DataFrame] = {}
        today = datetime.now()
        start_date = (today - timedelta(days=days or FDR_HISTORY_DAYS)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        self.logger.info(
            f"Fetching {days}-day history for {len(tickers)} tickers via FDR..."
        )

        # Set socket timeout to prevent infinite hanging
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(FDR_REQUEST_TIMEOUT)

        def fetch_one(ticker: str) -> tuple[str, pd.DataFrame | None]:
            try:
                df = fdr.DataReader(ticker, start_date, end_date)
                if df.empty:
                    return ticker, None
                return ticker, df
            except Exception as e:
                self.logger.debug(f"FDR history failed for {ticker}: {e}")
                return ticker, None

        # Batch-based processing with timeout to skip slow tickers
        batch_size = 100
        per_ticker_timeout = FDR_REQUEST_TIMEOUT + 5  # 15 seconds per ticker
        batch_timeout = per_ticker_timeout * 1.5  # Allow some buffer for batch

        pbar = tqdm(
            total=len(tickers),
            desc="Fetching FDR history",
            leave=False,
            disable=self.quiet,
        )

        executor = ThreadPoolExecutor(max_workers=10)
        try:
            # Process in batches
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                futures = {executor.submit(fetch_one, t): t for t in batch}
                pending = set(futures.keys())
                skipped_in_batch = []

                # Process batch with timeout
                while pending:
                    done, pending = wait(pending, timeout=batch_timeout, return_when=FIRST_COMPLETED)

                    if not done and pending:
                        # Timeout: cancel remaining slow tickers in this batch
                        skipped_in_batch = [futures[f] for f in pending]
                        for future in pending:
                            future.cancel()
                        pbar.update(len(pending))
                        break

                    for future in done:
                        pbar.update(1)
                        try:
                            ticker, df = future.result(timeout=0)
                            if df is not None and not df.empty:
                                results[ticker] = df
                        except Exception as e:
                            ticker = futures[future]
                            self.logger.debug(f"FDR history failed for {ticker}: {e}")

                if skipped_in_batch:
                    self.logger.warning(
                        f"FDR history batch {i // batch_size + 1}: skipped {len(skipped_in_batch)} slow tickers"
                    )

        finally:
            # Shutdown executor without waiting for pending tasks
            executor.shutdown(wait=False, cancel_futures=True)
            # Restore original socket timeout
            socket.setdefaulttimeout(old_timeout)
            pbar.close()

        self.logger.info(f"Fetched history for {len(results)} tickers")
        return results

    def fetch_kospi_history(self, days: int = 210) -> pd.DataFrame:
        """
        Fetch KOSPI index history for Beta calculation.

        Uses FDR (FinanceDataReader) for KOSPI index data.

        Args:
            days: Number of days of history

        Returns:
            DataFrame with KOSPI OHLCV data
        """
        today = datetime.now()
        start_date = (today - timedelta(days=days or FDR_HISTORY_DAYS)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        try:
            kospi = fdr.DataReader("KS11", start_date, end_date)
            if kospi is not None and not kospi.empty:
                self.logger.info(f"Fetched KOSPI history: {len(kospi)} rows")
                return kospi
        except Exception as e:
            self.logger.warning(f"Failed to fetch KOSPI from FDR: {e}")

        return pd.DataFrame()

    def _print_phase_header(self, phase: int, description: str, total: int) -> None:
        """Print phase start header.

        Args:
            phase: Phase number (1-5)
            description: Short description of the phase
            total: Total items to process
        """
        if self.quiet:
            return

        phase_names = {
            1: "가격 수집 (FDR)",
            2: "기초지표 (KIS/Naver)",
            3: "히스토리 수집 (FDR)",
            4: "기술적 지표 계산",
            5: "데이터 저장",
        }
        name = phase_names.get(phase, description)

        print()
        print(f"{'═' * 60}")
        print(f"  📊 Phase {phase}/5: {name}")
        print(f"  처리 대상: {total:,}개")
        print(f"{'═' * 60}")

    def _print_phase_transition(
        self,
        from_phase: int,
        to_phase: int,
        input_count: int,
        output_count: int,
        details: dict | None = None,
    ) -> None:
        """Print phase transition summary.

        Args:
            from_phase: Source phase number
            to_phase: Target phase number
            input_count: Number of items going into the phase
            output_count: Number of items coming out
            details: Additional details to display
        """
        if self.quiet:
            return

        lost = input_count - output_count
        rate = (output_count / input_count * 100) if input_count > 0 else 0

        # 상태 아이콘
        if rate >= 99:
            status = "✅"
        elif rate >= 95:
            status = "⚠️"
        else:
            status = "❌"

        print()
        print(f"{'─' * 50}")
        print(f"  {status} Phase {from_phase} 완료 → Phase {to_phase} 시작")
        print(f"{'─' * 50}")
        print(f"  입력: {input_count:,}개")
        print(f"  출력: {output_count:,}개 ({rate:.1f}%)")
        if lost > 0:
            print(f"  손실: {lost:,}개 ({100 - rate:.1f}%)")

        if details:
            print()
            for key, value in details.items():
                if isinstance(value, float):
                    print(f"    • {key}: {value:.1f}%")
                elif isinstance(value, int):
                    print(f"    • {key}: {value:,}")
                else:
                    print(f"    • {key}: {value}")

        print(f"{'─' * 50}")

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
        Collect Korean stock data.

        Uses FDR + KIS API + Naver Finance for all data collection.

        Args:
            tickers: List of tickers to collect (default: all from CSV)
            resume: Resume from previous incomplete collection
            batch_size: Not used (kept for API compatibility)
            is_test: If True, run in test mode (3 tickers)
            check_rate_limit_first: Not used (kept for API compatibility)
            auto_retry: If True, retry missing tickers after quality check

        Phases:
        1. FDR: Fetch prices from FinanceDataReader
        2. Naver: Fetch fundamentals (PER, PBR, EPS, BPS, ROE, ROA, market_cap)
        3. FDR: Fetch 7-month OHLCV history (for technicals, MA, Beta)
        4. Local: Calculate all technical indicators from history
        5. Combine and save to DB/CSV
        """
        # batch_size is no longer used (kept for API compatibility)
        _ = batch_size

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
        self._print_phase_header(1, "가격 수집", len(tickers))
        self.logger.info("Phase 1: Fetching prices from FinanceDataReader...")
        prices_all = self.fetch_prices_batch(tickers)
        valid_tickers = list(prices_all.keys())
        self.logger.info(f"Found {len(valid_tickers)} tickers with valid prices")

        # Phase 1 → 2 전환 요약
        if not self.quiet:
            failed_tickers = set(tickers) - set(valid_tickers)
            self._print_phase_transition(
                from_phase=1,
                to_phase=2,
                input_count=len(tickers),
                output_count=len(valid_tickers),
                details={
                    "가격 수집 성공": len(valid_tickers),
                    "가격 없음 (거래정지/상폐 등)": len(failed_tickers),
                },
            )

        # Set up version directory (based on trading date from prices)
        if self.save_csv:
            trading_date = self._extract_trading_date_from_prices(prices_all)
            if resume:
                self.storage.resume_version_dir(target_date=trading_date)
            else:
                self.storage.get_or_create_version_dir(target_date=trading_date)

        # Phase 2: Fetch fundamentals from KIS API (primary) or Naver Finance (fallback)
        self._print_phase_header(2, "기초지표", len(valid_tickers))
        self.logger.info("Phase 2: Fetching fundamentals...")

        # Try KIS API first (faster, more reliable)
        kis_fundamentals: dict = {}
        try:
            kis_fundamentals = asyncio.run(self._fetch_kis_fundamentals_async(valid_tickers))
        except Exception as e:
            self.logger.warning(f"KIS API failed: {e}")

        # If KIS got less than 50% of tickers, supplement with Naver Finance
        naver_fundamentals: dict = {}
        if len(kis_fundamentals) < len(valid_tickers) * 0.5:
            self.logger.info("KIS coverage low, fetching from Naver Finance...")

            async def fetch_naver_async():
                async with NaverFinanceClient(concurrency=15) as client:
                    return await client.fetch_bulk(
                        valid_tickers,
                        progress_callback=lambda c, t: None if self.quiet else self.logger.info(
                            f"Naver: {c}/{t}"
                        ) if c % 500 == 0 else None
                    )

            try:
                naver_fundamentals = asyncio.run(fetch_naver_async())
            except Exception as e:
                self.logger.warning(f"NaverFinanceClient failed, using legacy method: {e}")
                naver_fundamentals = self._fetch_naver_fundamentals(valid_tickers)

        # Merge: KIS takes precedence, Naver fills gaps
        merged_fundamentals: dict = {}
        for ticker in valid_tickers:
            kis_data = kis_fundamentals.get(ticker, {})
            naver_data = naver_fundamentals.get(ticker, {})
            # Naver first, KIS overwrites (KIS is more accurate)
            merged = {**naver_data, **kis_data}
            if merged:
                merged_fundamentals[ticker] = merged

        self.logger.info(
            f"Fetched fundamentals: KIS={len(kis_fundamentals)}, Naver={len(naver_fundamentals)}, merged={len(merged_fundamentals)}"
        )

        # Phase 2 → 3 전환 요약
        if not self.quiet:
            tickers_with_fundamentals = len(merged_fundamentals)
            tickers_without = len(valid_tickers) - tickers_with_fundamentals
            self._print_phase_transition(
                from_phase=2,
                to_phase=3,
                input_count=len(valid_tickers),
                output_count=len(valid_tickers),  # 모든 티커가 Phase 3로 전달됨
                details={
                    "KIS API 성공": len(kis_fundamentals),
                    "Naver 크롤링 성공": len(naver_fundamentals),
                    "기초지표 있음": tickers_with_fundamentals,
                    "기초지표 없음": tickers_without,
                },
            )

        # Phase 3: Fetch 10-month FDR history (for MA200, Beta, technicals)
        self._print_phase_header(3, "히스토리 수집", len(valid_tickers))
        self.logger.info("Phase 3: Fetching 10-month history via FDR...")
        history_data = self.fetch_fdr_history(valid_tickers, days=FDR_HISTORY_DAYS)
        self.logger.info(f"Fetched history for {len(history_data)} tickers")

        # Fetch KOSPI history for Beta calculation
        kospi_history = self.fetch_kospi_history(days=FDR_HISTORY_DAYS)

        # Phase 3 → 4 전환 요약
        if not self.quiet:
            tickers_with_history = len(history_data)
            tickers_without_history = len(valid_tickers) - tickers_with_history
            avg_days = (
                sum(len(df) for df in history_data.values()) / len(history_data)
                if history_data
                else 0
            )
            self._print_phase_transition(
                from_phase=3,
                to_phase=4,
                input_count=len(valid_tickers),
                output_count=tickers_with_history,
                details={
                    "히스토리 수집 성공": tickers_with_history,
                    "히스토리 없음": tickers_without_history,
                    "평균 히스토리 일수": int(avg_days),
                    "KOSPI 히스토리": len(kospi_history) if not kospi_history.empty else 0,
                },
            )

        # Phase 4: Calculate technicals from FDR history
        self._print_phase_header(4, "기술적 지표 계산", len(history_data))
        self.logger.info("Phase 4: Calculating technicals from FDR history...")

        # Calculate all technical indicators locally
        calculated_technicals: dict[str, dict] = {}
        for ticker in tqdm(
            valid_tickers,
            desc="Calculating technicals",
            leave=False,
            disable=self.quiet,
        ):
            hist = history_data.get(ticker)
            if hist is None or hist.empty:
                continue

            # Calculate all technicals from indicators.py
            technicals = calculate_all_technicals(hist)

            # Calculate MA50, MA200
            ma50, ma200 = calculate_moving_averages(hist, short_period=50, long_period=200)

            # Calculate Beta vs KOSPI
            beta = None
            if not kospi_history.empty:
                beta = calculate_beta(hist, kospi_history, period=252)

            # Calculate 52-week high/low from history
            high_52w, low_52w = calculate_52_week_high_low(hist)

            # Get current price from history
            current_price = hist["Close"].iloc[-1] if "Close" in hist.columns else None

            # Calculate price_to_52w_high_pct and ma_trend
            price_to_52w_high_pct = calculate_price_to_52w_high_pct(current_price, high_52w)
            ma_trend = calculate_ma_trend(ma50, ma200)

            calculated_technicals[ticker] = {
                **technicals,
                "fifty_day_average": ma50,
                "two_hundred_day_average": ma200,
                "beta": beta,
                "fifty_two_week_high": high_52w,
                "fifty_two_week_low": low_52w,
                "price_to_52w_high_pct": price_to_52w_high_pct,
                "ma_trend": ma_trend,
            }

        self.logger.info(f"Calculated technicals for {len(calculated_technicals)} stocks")

        # Phase 4 → 5 전환 요약
        if not self.quiet:
            tickers_with_technicals = len(calculated_technicals)
            # 지표별 커버리지 계산
            rsi_count = sum(1 for t in calculated_technicals.values() if t.get("rsi") is not None)
            beta_count = sum(1 for t in calculated_technicals.values() if t.get("beta") is not None)
            ma200_count = sum(1 for t in calculated_technicals.values() if t.get("two_hundred_day_average") is not None)

            self._print_phase_transition(
                from_phase=4,
                to_phase=5,
                input_count=len(history_data),
                output_count=tickers_with_technicals,
                details={
                    "기술적 지표 계산 성공": tickers_with_technicals,
                    "RSI 계산됨": rsi_count,
                    "Beta 계산됨": beta_count,
                    "MA200 계산됨": ma200_count,
                },
            )

        # Phase 5: Combine and save
        self._print_phase_header(5, "데이터 저장", len(valid_tickers))
        self.logger.info("Phase 5: Combining data and saving...")
        progress = CollectionProgress(
            total=len(valid_tickers),
            logger=self.logger,
            desc="Processing",
        )

        all_companies: list[dict] = []
        all_metrics: list[dict] = []
        all_prices: list[dict] = []

        # Cache default date outside loop (optimization: avoid calling date.today() 2800 times)
        default_date = date.today().isoformat()

        for ticker in valid_tickers:
            try:
                name = self._ticker_names.get(ticker, "")
                mkt = self._ticker_markets.get(ticker, "KOSPI")
                price_data = prices_all.get(ticker, {})
                market_cap = price_data.get("market_cap")

                # Get fundamentals (PER, PBR, EPS, BPS, ROE, ROA, market_cap) from KIS/Naver
                fund_data = merged_fundamentals.get(ticker, {})

                # Get calculated technicals (RSI, MACD, BB, MFI, MA, Beta, 52w)
                tech_data = calculated_technicals.get(ticker, {})

                # Combine metrics: base + naver fundamentals + calculated technicals
                combined_metrics = {
                    "name": name,
                    "market": mkt,
                    "currency": "KRW",
                }

                # Add market_cap from fundamentals if available, fallback to price_data
                if fund_data.get("market_cap"):
                    combined_metrics["market_cap"] = fund_data["market_cap"]
                elif market_cap:
                    combined_metrics["market_cap"] = market_cap

                # Add fundamentals (PER, PBR, EPS, BPS, ROE, ROA, dividend_yield, 52w high/low)
                if fund_data:
                    for key in ["pe_ratio", "pb_ratio", "eps", "book_value_per_share",
                                "roe", "roa", "debt_equity", "current_ratio", "dividend_yield",
                                "fifty_two_week_high", "fifty_two_week_low"]:
                        if key in fund_data and fund_data[key] is not None:
                            combined_metrics[key] = fund_data[key]

                # Add all calculated technical indicators
                if tech_data:
                    combined_metrics.update(tech_data)

                # Calculate Graham Number from EPS/BPS
                eps_val = combined_metrics.get("eps")
                bvps_val = combined_metrics.get("book_value_per_share")
                if eps_val and bvps_val:
                    eps_float = float(eps_val) if isinstance(eps_val, (int, float)) else None
                    bvps_float = float(bvps_val) if isinstance(bvps_val, (int, float)) else None
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
                            "date": price_data.get("date") or default_date,
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
            df = pd.read_csv(csv_path, dtype={"ticker": str})
            name_map = dict(zip(df["ticker"], df["name"], strict=False))
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
