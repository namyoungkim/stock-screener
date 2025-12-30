"""
Korean Stock Data Collector

Collects financial data for Korean stocks using pykrx and yfinance.
Supports hybrid storage: Supabase for latest data, CSV for history.

Data sources:
- pykrx: prices, market cap, PER, PBR, EPS, BPS (bulk, fast)
- yfinance: ROE, ROA, margins, ratios, technical indicators (bulk)

Usage:
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kospi
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --test
    uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --resume
"""

import logging
import random
import time
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from common.indicators import calculate_all_technicals, calculate_graham_number
from common.logging import CollectionProgress
from common.retry import RetryConfig, with_retry
from pykrx import stock as pykrx  # type: ignore[import-untyped]
from tqdm import tqdm

from .base import BaseCollector


class KRCollector(BaseCollector):
    """Collector for Korean stock data using pykrx + yfinance."""

    MARKET = "KOSPI"  # Will be overridden per ticker
    MARKET_PREFIX = "kr"
    DATA_SOURCE = "yfinance+pykrx"

    def __init__(
        self,
        market: str = "ALL",
        save_db: bool = True,
        save_csv: bool = True,
        log_level: int = logging.INFO,
    ):
        """
        Initialize KR stock collector.

        Args:
            market: "KOSPI", "KOSDAQ", or "ALL"
            save_db: Whether to save to Supabase
            save_csv: Whether to save to CSV files
            log_level: Logging level
        """
        super().__init__(save_db=save_db, save_csv=save_csv, log_level=log_level)
        self.market = market
        self._ticker_markets: dict[str, str] = {}
        self._ticker_names: dict[str, str] = {}
        self._fundamentals: dict[str, dict] = {}  # PER, PBR, EPS, BPS from pykrx

    def get_tickers(self) -> list[str]:
        """Get list of KRX tickers based on market setting."""
        today = datetime.now().strftime("%Y%m%d")
        tickers_data = []

        if self.market in ("KOSPI", "ALL"):
            kospi_tickers = pykrx.get_market_ticker_list(today, market="KOSPI")
            for ticker in kospi_tickers:
                name = pykrx.get_market_ticker_name(ticker)
                tickers_data.append({"ticker": ticker, "name": name, "market": "KOSPI"})

        if self.market in ("KOSDAQ", "ALL"):
            kosdaq_tickers = pykrx.get_market_ticker_list(today, market="KOSDAQ")
            for ticker in kosdaq_tickers:
                name = pykrx.get_market_ticker_name(ticker)
                tickers_data.append(
                    {"ticker": ticker, "name": name, "market": "KOSDAQ"}
                )

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
        """Fetch yfinance metrics with retry."""
        stock = yf.Ticker(yf_ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return None

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")

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
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "eps": eps,
            "book_value_per_share": bvps,
            "graham_number": calculate_graham_number(eps, bvps),
        }

    def _fetch_pykrx_fundamentals(self, trading_date: str) -> dict[str, dict]:
        """Fetch PER, PBR, EPS, BPS from pykrx for all stocks."""
        results: dict[str, dict] = {}

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

    def fetch_prices_batch(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch price data and fundamentals from pykrx bulk market data."""
        results: dict[str, dict] = {}

        # Find the most recent trading day
        market_df = None
        trading_date = None

        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            df = pykrx.get_market_cap(day)
            if not df.empty and df["시가총액"].sum() > 0:
                market_df = df
                trading_date = day
                break

        if market_df is None or trading_date is None:
            self.logger.error("Could not fetch market data")
            return results

        self.logger.info(f"Fetched bulk market data for {len(market_df)} stocks")

        # Fetch fundamentals (PER, PBR, EPS, BPS)
        self._fundamentals = self._fetch_pykrx_fundamentals(trading_date)
        self.logger.info(f"Fetched fundamentals for {len(self._fundamentals)} stocks")

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
        batch_size: int = 300,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for all KR tickers in bulk using yf.download.

        Rate limit handling:
        - Batch size: 300 (reduced from 500)
        - Sleep between batches: 1-2 seconds
        - yf.download is more lenient than individual ticker.info calls
        """
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

                # Sleep between batches: 1-2 seconds
                time.sleep(1.0 + random.uniform(0, 1.0))

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
        batch_size: int = 5,
    ) -> dict[str, dict]:
        """Fetch yfinance metrics for multiple tickers in batches.

        Rate limit handling:
        - Batch size: 5 (conservative for large collections)
        - Sleep between batches: 3-5 seconds with jitter
        - Rate limit detection: Backoff 30-60s on consecutive failures
        - Max retries: 3 backoffs before stopping
        """
        results: dict[str, dict] = {}
        failed_tickers: list[tuple[str, str]] = []
        consecutive_failures = 0
        max_consecutive_failures = 10  # Allow more failures before backoff
        backoff_count = 0
        max_backoffs = 3  # Stop after 3 backoffs

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
            )
        ):
            batch = yf_tickers[i : i + batch_size]
            batch_success = 0

            try:
                tickers_obj = yf.Tickers(" ".join(batch))

                for yf_ticker in batch:
                    try:
                        stock = tickers_obj.tickers[yf_ticker]
                        info = stock.info

                        if info and info.get("regularMarketPrice") is not None:
                            krx_ticker = ticker_map[yf_ticker]
                            eps = info.get("trailingEps")
                            bvps = info.get("bookValue")

                            # Get technicals from pre-fetched history
                            hist = (
                                history_data.get(krx_ticker) if history_data else None
                            )
                            if hist is None or hist.empty:
                                hist = stock.history(period="2mo")
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
                                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                                "fifty_day_average": info.get("fiftyDayAverage"),
                                "two_hundred_day_average": info.get(
                                    "twoHundredDayAverage"
                                ),
                                "eps": eps,
                                "book_value_per_share": bvps,
                                "graham_number": calculate_graham_number(eps, bvps),
                                **technicals,
                            }
                            batch_success += 1
                        else:
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
            if consecutive_failures >= max_consecutive_failures:
                backoff_count += 1
                if backoff_count > max_backoffs:
                    self.logger.warning(
                        f"Stopping after {max_backoffs} backoffs. "
                        f"Completed {len(results)}/{len(tickers)} tickers."
                    )
                    break

                backoff_time = 300.0 + random.uniform(0, 60.0)  # 5-6 minutes
                self.logger.warning(
                    f"Rate limit detected. Backoff {backoff_count}/{max_backoffs}: "
                    f"waiting {backoff_time:.0f}s... "
                    f"(Completed {len(results)}/{len(tickers)} so far)"
                )
                time.sleep(backoff_time)
                consecutive_failures = 0  # Reset after backoff

            # Sleep between batches: 3-5 seconds with random jitter
            sleep_time = 3.0 + random.uniform(0, 2.0)
            time.sleep(sleep_time)

        # Retry failed tickers with longer delays (only if not stopped by backoff limit)
        if failed_tickers and backoff_count <= max_backoffs:
            self.logger.info(
                f"Retrying {len(failed_tickers)} failed tickers with longer delays..."
            )
            retry_failures = 0
            max_retry_failures = 20  # Allow more retries

            for yf_ticker, krx_ticker in tqdm(
                failed_tickers, desc="Fallback", leave=False
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
                            self.logger.warning(f"Fallback backoff: waiting {backoff_time:.0f}s...")
                            time.sleep(backoff_time)

                # Longer sleep for fallback: 5-8 seconds
                time.sleep(5.0 + random.uniform(0, 3.0))
        elif backoff_count > max_backoffs:
            self.logger.info("Skipping fallback retry due to rate limit.")

        return results

    def collect(
        self,
        tickers: list[str] | None = None,
        resume: bool = False,
        batch_size: int = 5,
        is_test: bool = False,
        check_rate_limit_first: bool = True,
        auto_retry: bool = True,
    ) -> dict:
        """
        Collect Korean stock data with optimized batch processing.

        Phases:
        1. Fetch prices + fundamentals from pykrx (bulk, ~2s)
        2. Download history for technical indicators (bulk, ~2min)
        3. Fetch yfinance metrics (bulk, ~3min)
        4. Combine and save

        Args:
            auto_retry: If True, retry missing tickers after quality check
        """
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

        # Phase 1: Fetch prices + fundamentals from pykrx
        self.logger.info("Phase 1: Fetching prices and fundamentals from pykrx...")
        prices_all = self.fetch_prices_batch(tickers)
        valid_tickers = list(prices_all.keys())
        self.logger.info(f"Found {len(valid_tickers)} tickers with valid prices")

        # Phase 2: Bulk download history
        self.logger.info("Phase 2: Downloading history for technical indicators...")
        history_data = self.fetch_history_bulk(
            valid_tickers, period="2mo", batch_size=500
        )

        # Phase 3: Batch yfinance metrics
        self.logger.info("Phase 3: Fetching yfinance metrics in batches...")
        yf_metrics_all = self.fetch_yfinance_batch(
            valid_tickers,
            history_data=history_data,
            batch_size=batch_size,
        )
        self.logger.info(f"Fetched yfinance metrics for {len(yf_metrics_all)} stocks")

        # Phase 4: Combine and save
        self.logger.info("Phase 4: Combining data and saving...")
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

                # Get pykrx fundamentals (PER, PBR, EPS, BPS)
                pykrx_data = self._fundamentals.get(ticker, {})

                # Get yfinance metrics
                yf_metrics = yf_metrics_all.get(ticker, {})

                # Combine metrics: pykrx first, then yfinance (yfinance overwrites if available)
                combined_metrics = {
                    "name": name,
                    "market": mkt,
                    "market_cap": market_cap,
                }

                # Add pykrx data (PER, PBR, EPS, BPS)
                if pykrx_data:
                    combined_metrics.update(pykrx_data)

                # Add yfinance data (overwrites eps/bvps if available)
                if yf_metrics:
                    for key, value in yf_metrics.items():
                        if value is not None:
                            combined_metrics[key] = value

                # Calculate Graham Number from available EPS/BPS (pykrx or yfinance)
                eps = combined_metrics.get("eps")
                bvps = combined_metrics.get("book_value_per_share")
                if eps and bvps and "graham_number" not in combined_metrics:
                    combined_metrics["graham_number"] = calculate_graham_number(
                        eps, bvps
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
    log_level = logging.DEBUG if "--verbose" in args else logging.INFO

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
        for ticker in test_tickers:
            name = pykrx.get_market_ticker_name(ticker)
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
    )

    if is_test:
        print("Running in test mode (3 tickers)...")
        stats = collector.collect(
            tickers=["005930", "000660", "035720"],
            is_test=True,
        )
    else:
        if market == "ALL":
            print("Running full KRX (KOSPI + KOSDAQ) collection...")
        else:
            print(f"Running {market} collection...")

        stats = collector.collect(resume=resume)

    print(f"\nCollection complete: {stats}")


if __name__ == "__main__":
    main()
