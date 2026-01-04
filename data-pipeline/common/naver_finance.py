"""
Naver Finance Client for Korean Stock Fundamentals

Extracts financial data from Naver Finance web pages:
- PER, PBR, EPS, BPS (existing functionality from kr_stocks.py)
- ROE, ROA, 부채비율, 유동비율 (new)
- 배당수익률, 시가총액 (new)

Usage:
    from common.naver_finance import NaverFinanceClient

    client = NaverFinanceClient()
    data = await client.get_all_data("005930")  # Samsung
    bulk_data = await client.fetch_bulk(["005930", "000660", "035720"])
"""

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NaverFinanceClient:
    """Naver Finance web scraper for Korean stock fundamentals."""

    BASE_URL = "https://finance.naver.com"
    MAIN_URL = f"{BASE_URL}/item/main.naver"
    SISE_URL = f"{BASE_URL}/item/sise.naver"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }

    def __init__(
        self,
        concurrency: int = 10,
        timeout: float = 15.0,
        delay_between_requests: float = 0.05,
    ):
        """
        Initialize Naver Finance client.

        Args:
            concurrency: Maximum concurrent requests (semaphore limit)
            timeout: Request timeout in seconds
            delay_between_requests: Delay between requests to be polite
        """
        self.concurrency = concurrency
        self.timeout = timeout
        self.delay = delay_between_requests
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=self.concurrency * 2)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                headers=self.DEFAULT_HEADERS,
                connector=connector,
                timeout=timeout,
            )
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "NaverFinanceClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def get_fundamentals(self, ticker: str) -> dict[str, float | None]:
        """
        Fetch basic fundamentals from Naver Finance main page.

        Returns:
            dict with keys: pe_ratio, eps, pb_ratio, book_value_per_share
        """
        session = await self._get_session()
        url = f"{self.MAIN_URL}?code={ticker}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.debug(f"Naver main page failed for {ticker}: HTTP {resp.status}")
                    return {}

                html = await resp.text()
                return self._parse_fundamentals(html)

        except Exception as e:
            logger.debug(f"Failed to fetch fundamentals for {ticker}: {e}")
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
            # Pattern: "PBR ... l BPS ... 배 l N원"
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

    async def get_financial_ratios(self, ticker: str) -> dict[str, float | None]:
        """
        Fetch financial ratios from Naver Finance.

        Returns:
            dict with keys: roe, roa, debt_equity, current_ratio
        """
        session = await self._get_session()

        # Try investment indicators page (투자지표)
        url = f"{self.BASE_URL}/item/coinfo.naver?code={ticker}&target=finsum_more"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {}

                html = await resp.text()
                return self._parse_financial_ratios(html)

        except Exception as e:
            logger.debug(f"Failed to fetch financial ratios for {ticker}: {e}")
            return {}

    def _parse_financial_ratios(self, html: str) -> dict[str, float | None]:
        """Parse ROE, ROA, debt ratio, current ratio from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        data: dict[str, float | None] = {}

        # Look for ROE in the page
        # Naver Finance shows these in various tables
        text = soup.get_text()

        # ROE pattern: "ROE(%) N.NN" or "ROE N.NN%"
        roe_match = re.search(r"ROE[^\d]*?([\d.]+)\s*%?", text, re.IGNORECASE)
        if roe_match:
            with contextlib.suppress(ValueError):
                data["roe"] = float(roe_match.group(1)) / 100  # Convert to decimal

        # ROA pattern
        roa_match = re.search(r"ROA[^\d]*?([\d.]+)\s*%?", text, re.IGNORECASE)
        if roa_match:
            with contextlib.suppress(ValueError):
                data["roa"] = float(roa_match.group(1)) / 100

        # 부채비율 (Debt to Equity)
        debt_match = re.search(r"부채비율[^\d]*?([\d.]+)\s*%?", text)
        if debt_match:
            with contextlib.suppress(ValueError):
                data["debt_equity"] = float(debt_match.group(1))  # Keep as percentage

        # 유동비율 (Current Ratio)
        current_match = re.search(r"유동비율[^\d]*?([\d.]+)\s*%?", text)
        if current_match:
            with contextlib.suppress(ValueError):
                data["current_ratio"] = float(current_match.group(1)) / 100

        return data

    async def get_market_data(self, ticker: str) -> dict[str, float | int | None]:
        """
        Fetch market data from Naver Finance sise page.

        Returns:
            dict with keys: market_cap, dividend_yield, volume
        """
        session = await self._get_session()
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

    def _parse_market_data(self, html: str) -> dict[str, float | int | None]:
        """Parse market cap, dividend yield from sise page."""
        soup = BeautifulSoup(html, "html.parser")
        data: dict[str, float | int | None] = {}

        # Market cap is usually in format "N조 N,NNN억원" or "N,NNN억원"
        text = soup.get_text()

        # 시가총액 (Market Cap)
        market_cap_match = re.search(
            r"시가총액[^\d]*([\d,]+)\s*억",
            text,
        )
        if market_cap_match:
            with contextlib.suppress(ValueError):
                # Convert 억원 to actual value (1억 = 100,000,000)
                cap_in_billion = int(market_cap_match.group(1).replace(",", ""))
                data["market_cap"] = cap_in_billion * 100_000_000

        # 배당수익률 (Dividend Yield)
        div_match = re.search(r"배당수익률[^\d]*([\d.]+)\s*%", text)
        if div_match:
            with contextlib.suppress(ValueError):
                data["dividend_yield"] = float(div_match.group(1)) / 100

        return data

    async def get_all_data(self, ticker: str) -> dict[str, Any]:
        """
        Fetch all available data for a single ticker.

        Combines: fundamentals + financial ratios + market data

        Returns:
            dict with all available fields
        """
        # Fetch all data concurrently
        fundamentals, ratios, market_data = await asyncio.gather(
            self.get_fundamentals(ticker),
            self.get_financial_ratios(ticker),
            self.get_market_data(ticker),
            return_exceptions=True,
        )

        result: dict[str, Any] = {}

        # Merge results, handling exceptions
        if isinstance(fundamentals, dict):
            result.update(fundamentals)
        if isinstance(ratios, dict):
            result.update(ratios)
        if isinstance(market_data, dict):
            result.update(market_data)

        return result

    async def fetch_bulk(
        self,
        tickers: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch data for multiple tickers in parallel with rate limiting.

        Args:
            tickers: List of KRX ticker codes (e.g., ["005930", "000660"])
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            dict mapping ticker to its data dict
        """
        results: dict[str, dict[str, Any]] = {}
        semaphore = asyncio.Semaphore(self.concurrency)
        completed = 0
        total = len(tickers)

        async def fetch_one(ticker: str) -> tuple[str, dict[str, Any]]:
            nonlocal completed
            async with semaphore:
                try:
                    data = await self.get_all_data(ticker)

                    # Small delay to be polite
                    await asyncio.sleep(self.delay)

                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

                    return ticker, data

                except Exception as e:
                    logger.debug(f"Failed to fetch {ticker}: {e}")
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)
                    return ticker, {}

        # Create session for all requests
        session = await self._get_session()

        # Run all requests
        tasks = [fetch_one(ticker) for ticker in tickers]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for response in responses:
            if isinstance(response, Exception):
                continue
            ticker, data = response
            if data:  # Only add if we got some data
                results[ticker] = data

        return results


# Convenience function for sync usage
def fetch_naver_fundamentals_sync(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """
    Synchronous wrapper for fetching Naver Finance data.

    Usage:
        results = fetch_naver_fundamentals_sync(["005930", "000660"])
    """
    async def _run():
        async with NaverFinanceClient() as client:
            return await client.fetch_bulk(tickers)

    return asyncio.run(_run())
