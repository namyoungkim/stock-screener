"""Naver Finance source for Korean stock fundamentals.

Scrapes Naver Finance web pages to extract:
- PER, PBR, EPS, BPS (from main page)
- ROE, ROA, Debt/Equity (from financial analysis table)
- Dividend yield, Market cap (from sise page)

This is a fallback source when KIS API is not available.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import aiohttp
from bs4 import BeautifulSoup

from core.errors import DataNotFoundError, NetworkError, TimeoutError, classify_exception
from core.types import BatchFetchResult, FetchResult, MetricsData
from observability.logger import get_logger, log_context

if TYPE_CHECKING:
    from datetime import date

    from kr.config import KRConfig

logger = get_logger(__name__)


@dataclass
class NaverSource:
    """Naver Finance web scraper for Korean stock fundamentals.

    Provides fundamental metrics for Korean stocks via web scraping.
    Use with caution - respect rate limits.
    """

    config: KRConfig

    BASE_URL: ClassVar[str] = "https://finance.naver.com"
    MAIN_URL: ClassVar[str] = f"{BASE_URL}/item/main.naver"
    SISE_URL: ClassVar[str] = f"{BASE_URL}/item/sise.naver"

    DEFAULT_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }

    async def fetch_metrics(
        self,
        tickers: list[str],
        trading_date: date | None = None,
    ) -> BatchFetchResult[MetricsData]:
        """Fetch fundamental metrics for multiple tickers.

        Args:
            tickers: List of KRX ticker codes
            trading_date: Date for the metrics (default: today)

        Returns:
            BatchFetchResult containing MetricsData for each ticker
        """
        from datetime import date as date_type

        if trading_date is None:
            trading_date = date_type.today()

        results: list[FetchResult[MetricsData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="naver")

        # Create session for all requests
        connector = aiohttp.TCPConnector(limit=self.config.metrics_batch_size * 2)
        timeout = aiohttp.ClientTimeout(total=self.config.naver_timeout)

        async with aiohttp.ClientSession(
            headers=self.DEFAULT_HEADERS,
            connector=connector,
            timeout=timeout,
        ) as session:
            # Process in batches
            batch_size = self.config.metrics_batch_size
            semaphore = asyncio.Semaphore(self.config.metrics_batch_size)

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                batch_start = time.monotonic()

                with log_context(
                    source="naver",
                    phase="metrics",
                    batch_index=i // batch_size,
                    batch_size=len(batch),
                ):
                    # Fetch all tickers in batch concurrently
                    tasks = [
                        self._fetch_single_metrics(session, semaphore, ticker, trading_date)
                        for ticker in batch
                    ]

                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results
                    for ticker, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            results.append(
                                FetchResult(
                                    ticker=ticker,
                                    error=classify_exception(result, source="naver"),
                                    source="naver",
                                )
                            )
                        else:
                            results.append(result)

                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency

                    # Log batch completion
                    batch_succeeded = sum(
                        1 for r in results[i:] if isinstance(r, FetchResult) and r.is_success
                    )
                    logger.info(
                        "Batch completed",
                        extra={
                            "success_count": batch_succeeded,
                            "failed_count": len(batch) - batch_succeeded,
                            "duration_ms": round(batch_latency, 2),
                        },
                    )

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="naver",
        )

    async def _fetch_single_metrics(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        ticker: str,
        trading_date: date,
    ) -> FetchResult[MetricsData]:
        """Fetch metrics for a single ticker.

        Args:
            session: aiohttp session
            semaphore: Concurrency limiter
            ticker: KRX ticker code
            trading_date: Date for the metrics

        Returns:
            FetchResult containing MetricsData or error
        """
        fetch_start = time.monotonic()

        async with semaphore:
            try:
                # Fetch fundamentals and market data concurrently
                fundamentals, market_data = await asyncio.gather(
                    self._fetch_fundamentals(session, ticker),
                    self._fetch_market_data(session, ticker),
                )

                latency = (time.monotonic() - fetch_start) * 1000

                # Merge results
                data: dict[str, Any] = {}
                if fundamentals:
                    data.update(fundamentals)
                if market_data:
                    data.update(market_data)

                if not data:
                    return FetchResult(
                        ticker=ticker,
                        error=DataNotFoundError(
                            "No metrics data from Naver",
                            ticker=ticker,
                        ),
                        latency_ms=latency,
                        source="naver",
                    )

                # Convert to MetricsData
                metrics = MetricsData(
                    ticker=ticker,
                    date=trading_date,
                    pe_ratio=data.get("pe_ratio"),
                    pb_ratio=data.get("pb_ratio"),
                    eps=data.get("eps"),
                    bps=data.get("book_value_per_share"),
                    roe=data.get("roe"),
                    roa=data.get("roa"),
                    gross_margin=data.get("gross_margin"),
                    net_margin=data.get("net_margin"),
                    debt_equity=data.get("debt_equity"),
                    current_ratio=data.get("current_ratio"),
                    dividend_yield=data.get("dividend_yield"),
                    market_cap=data.get("market_cap"),
                )

                return FetchResult(
                    ticker=ticker,
                    data=metrics,
                    latency_ms=latency,
                    source="naver",
                )

            except asyncio.TimeoutError:
                latency = (time.monotonic() - fetch_start) * 1000
                return FetchResult(
                    ticker=ticker,
                    error=TimeoutError(
                        f"Timeout after {self.config.naver_timeout}s",
                        timeout=self.config.naver_timeout,
                        ticker=ticker,
                    ),
                    latency_ms=latency,
                    source="naver",
                )

            except aiohttp.ClientError as e:
                latency = (time.monotonic() - fetch_start) * 1000
                return FetchResult(
                    ticker=ticker,
                    error=NetworkError(str(e), ticker=ticker),
                    latency_ms=latency,
                    source="naver",
                )

            except Exception as e:
                latency = (time.monotonic() - fetch_start) * 1000
                return FetchResult(
                    ticker=ticker,
                    error=classify_exception(e, source="naver"),
                    latency_ms=latency,
                    source="naver",
                )

    async def _fetch_fundamentals(
        self,
        session: aiohttp.ClientSession,
        ticker: str,
    ) -> dict[str, float | None]:
        """Fetch basic fundamentals from Naver Finance main page.

        Returns:
            dict with keys: pe_ratio, eps, pb_ratio, book_value_per_share,
                           roe, roa, debt_equity, dividend_yield
        """
        url = f"{self.MAIN_URL}?code={ticker}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.debug(f"Naver main page failed for {ticker}: HTTP {resp.status}")
                    return {}

                html = await resp.text()
                result = self._parse_fundamentals(html)
                result.update(self._parse_financial_analysis_table(html))
                return result

        except Exception as e:
            logger.debug(f"Failed to fetch fundamentals for {ticker}: {e}")
            return {}

    async def _fetch_market_data(
        self,
        session: aiohttp.ClientSession,
        ticker: str,
    ) -> dict[str, float | int | None]:
        """Fetch market data from Naver Finance sise page.

        Returns:
            dict with keys: market_cap, dividend_yield, volume
        """
        url = f"{self.SISE_URL}?code={ticker}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {}

                html = await resp.text()
                return self._parse_market_data(html)

        except Exception as e:
            logger.debug(f"Failed to fetch market data for {ticker}: {e}")
            return {}

    def _parse_fundamentals(self, html: str) -> dict[str, float | None]:
        """Parse PER, EPS, PBR, BPS from main page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        data: dict[str, float | None] = {}

        # Extract PER from em#_per
        per_em = soup.find("em", id="_per")
        if per_em:
            with contextlib.suppress(ValueError, TypeError):
                text = per_em.get_text().replace(",", "").strip()
                if text and text != "-":
                    data["pe_ratio"] = float(text)

        # Extract EPS from em#_eps
        eps_em = soup.find("em", id="_eps")
        if eps_em:
            with contextlib.suppress(ValueError, TypeError):
                text = eps_em.get_text().replace(",", "").strip()
                if text and text != "-":
                    data["eps"] = float(text)

        # Extract PBR from em#_pbr
        pbr_em = soup.find("em", id="_pbr")
        if pbr_em:
            with contextlib.suppress(ValueError, TypeError):
                text = pbr_em.get_text().replace(",", "").strip()
                if text and text != "-":
                    data["pb_ratio"] = float(text)

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

        return data

    def _parse_financial_analysis_table(self, html: str) -> dict[str, float | None]:
        """Parse ROE, ROA, debt ratio, dividend yield from cop_analysis table."""
        soup = BeautifulSoup(html, "html.parser")
        data: dict[str, float | None] = {}

        # Find the financial analysis table (주요재무정보)
        roe_th = soup.find("th", class_="th_cop_anal13")
        if not roe_th:
            return data

        table = roe_th.find_parent("table")
        if not table:
            return data

        # Parse all rows
        rows = table.find_all("tr")
        row_data: dict[str, list[str]] = {}

        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            row_name = cells[0].get_text(strip=True)
            values = [c.get_text(strip=True) for c in cells[1:]]

            if row_name and values:
                row_data[row_name] = values

        def get_latest_value(row_name: str) -> float | None:
            """Get the most recent non-empty value from a row."""
            values = row_data.get(row_name, [])
            for val in values:
                if val and val not in ["-", "", "IFRS연결", "IFRS별도"]:
                    try:
                        return float(val.replace(",", ""))
                    except ValueError:
                        continue
            return None

        # Extract ROE (as percentage, convert to decimal)
        roe_val = get_latest_value("ROE(지배주주)")
        if roe_val is not None:
            data["roe"] = roe_val / 100

        # Extract ROA
        roa_val = get_latest_value("ROA")
        if roa_val is not None:
            data["roa"] = roa_val / 100

        # Extract debt ratio (부채비율)
        debt_val = get_latest_value("부채비율")
        if debt_val is not None:
            data["debt_equity"] = debt_val

        # Extract dividend yield (시가배당률)
        div_val = get_latest_value("시가배당률(%)")
        if div_val is not None:
            data["dividend_yield"] = div_val / 100

        # Extract current ratio (당좌비율)
        quick_val = get_latest_value("당좌비율")
        if quick_val is not None:
            data["current_ratio"] = quick_val / 100

        # Extract gross margin (매출총이익률)
        gross_margin_val = get_latest_value("매출총이익률")
        if gross_margin_val is not None:
            data["gross_margin"] = gross_margin_val / 100

        # Extract operating margin (영업이익률) as proxy for net margin
        op_margin_val = get_latest_value("영업이익률")
        if op_margin_val is not None:
            data["operating_margin"] = op_margin_val / 100

        # Extract net margin (순이익률)
        net_margin_val = get_latest_value("순이익률")
        if net_margin_val is not None:
            data["net_margin"] = net_margin_val / 100

        return data

    def _parse_market_data(self, html: str) -> dict[str, float | int | None]:
        """Parse market cap, dividend yield from sise page."""
        soup = BeautifulSoup(html, "html.parser")
        data: dict[str, float | int | None] = {}

        text = soup.get_text()

        # 시가총액 (Market Cap)
        market_cap_match = re.search(
            r"시가총액[^\d]*([\d,]+)\s*억",
            text,
        )
        if market_cap_match:
            with contextlib.suppress(ValueError):
                cap_in_billion = int(market_cap_match.group(1).replace(",", ""))
                data["market_cap"] = cap_in_billion * 100_000_000

        # 배당수익률 (Dividend Yield) - may override fundamentals
        div_match = re.search(r"배당수익률[^\d]*([\d.]+)\s*%", text)
        if div_match:
            with contextlib.suppress(ValueError):
                data["dividend_yield"] = float(div_match.group(1)) / 100

        return data

    async def close(self) -> None:
        """No persistent resources to clean up."""
        pass
