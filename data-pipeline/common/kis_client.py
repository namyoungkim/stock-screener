"""
Korea Investment & Securities (KIS) API Client

REST API client for Korean and US stock data.
Supports: quotes, 52-week high/low, financial indicators

API Documentation: https://apiportal.koreainvestment.com

Usage:
    from common.kis_client import KISClient

    client = KISClient(app_key="...", app_secret="...")
    quote = await client.get_domestic_quote("005930")  # Samsung
    us_quote = await client.get_foreign_quote("AAPL", "NAS")  # Apple on NASDAQ

Rate Limits:
    - 초당 약 15-20 요청 (토큰 버킷으로 관리)
    - API 호출 실패 시 자동 백오프
"""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from common.config import KIS_APP_KEY, KIS_APP_SECRET, KIS_PAPER_TRADING

logger = logging.getLogger(__name__)


class KISAuthError(Exception):
    """KIS API authentication error."""

    pass


class KISRateLimitError(Exception):
    """KIS API rate limit error."""

    pass


class KISClient:
    """Korea Investment & Securities Open API Client."""

    # API endpoints
    REAL_URL = "https://openapi.koreainvestment.com:9443"
    PAPER_URL = "https://openapivts.koreainvestment.com:29443"

    # API paths
    TOKEN_PATH = "/oauth2/tokenP"
    DOMESTIC_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
    DOMESTIC_DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    FOREIGN_PRICE_PATH = "/uapi/overseas-price/v1/quotations/price"
    FOREIGN_DAILY_PATH = "/uapi/overseas-price/v1/quotations/dailyprice"

    # Exchange codes for foreign stocks
    EXCHANGE_CODES = {
        "NYSE": "NYS",
        "NASDAQ": "NAS",
        "AMEX": "AMS",
        "US": "NAS",  # Default to NASDAQ for US
    }

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        is_paper: bool | None = None,
        rate_limit: float = 15.0,  # Requests per second
    ):
        """
        Initialize KIS API client.

        Args:
            app_key: KIS API app key (or use KIS_APP_KEY env var)
            app_secret: KIS API app secret (or use KIS_APP_SECRET env var)
            is_paper: Use paper trading API (or use KIS_PAPER_TRADING env var)
            rate_limit: Maximum requests per second
        """
        self.app_key = app_key or KIS_APP_KEY
        self.app_secret = app_secret or KIS_APP_SECRET
        self.is_paper = is_paper if is_paper is not None else KIS_PAPER_TRADING

        if not self.app_key or not self.app_secret:
            logger.warning(
                "KIS API credentials not configured. "
                "Set KIS_APP_KEY and KIS_APP_SECRET environment variables."
            )

        self.base_url = self.PAPER_URL if self.is_paper else self.REAL_URL

        # Token management
        self._access_token: str | None = None
        self._token_expires: datetime | None = None

        # Rate limiting (token bucket)
        self._rate_limit = rate_limit
        self._tokens = rate_limit
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

        # Session
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "KISClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _acquire_rate_limit(self) -> None:
        """Acquire a token from the rate limiter (token bucket algorithm)."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            # Refill tokens based on elapsed time
            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens < 1:
                # Wait for token to be available
                wait_time = (1 - self._tokens) / self._rate_limit
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1

    async def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        # Check if we have a valid token
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires - timedelta(minutes=5):
                return self._access_token

        # Request new token
        session = await self._get_session()
        url = f"{self.base_url}{self.TOKEN_PATH}"

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise KISAuthError(f"Failed to get access token: {resp.status} {text}")

                data = await resp.json()

                if "access_token" not in data:
                    raise KISAuthError(f"No access token in response: {data}")

                self._access_token = data["access_token"]

                # Token expires in ~24 hours, but we refresh early
                expires_in = data.get("expires_in", 86400)
                self._token_expires = datetime.now() + timedelta(seconds=expires_in)

                logger.info("KIS API access token acquired")
                return self._access_token

        except aiohttp.ClientError as e:
            raise KISAuthError(f"Network error getting access token: {e}") from e

    def _get_headers(self, tr_id: str) -> dict[str, str]:
        """Build request headers with authentication."""
        if not self._access_token:
            raise KISAuthError("No access token. Call _get_access_token() first.")

        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # Personal
        }

    async def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict[str, Any]:
        """Make API request with rate limiting and error handling."""
        await self._acquire_rate_limit()
        await self._get_access_token()

        session = await self._get_session()
        url = f"{self.base_url}{path}"
        headers = self._get_headers(tr_id)

        try:
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params) as resp:
                    return await self._handle_response(resp)
            else:
                async with session.post(url, headers=headers, json=json_body) as resp:
                    return await self._handle_response(resp)

        except aiohttp.ClientError as e:
            logger.error(f"KIS API request failed: {e}")
            raise

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> dict[str, Any]:
        """Handle API response and errors."""
        data = await resp.json()

        # Check for rate limit
        if resp.status == 429:
            raise KISRateLimitError("KIS API rate limit exceeded")

        # Check for API errors
        rt_cd = data.get("rt_cd")
        if rt_cd and rt_cd != "0":
            msg = data.get("msg1", "Unknown error")
            msg_cd = data.get("msg_cd", "")
            logger.warning(f"KIS API error: [{msg_cd}] {msg}")

        return data

    # ==================== Domestic (Korean) Stock APIs ====================

    async def get_domestic_quote(self, ticker: str) -> dict[str, Any]:
        """
        Get current quote for a Korean stock.

        Args:
            ticker: KRX stock code (e.g., "005930" for Samsung)

        Returns:
            dict with: current_price, high_52w, low_52w, volume, market_cap, etc.
        """
        tr_id = "FHKST01010100"  # 주식현재가 시세

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": ticker,
        }

        data = await self._request("GET", self.DOMESTIC_PRICE_PATH, tr_id, params=params)

        output = data.get("output", {})

        return {
            "ticker": ticker,
            "current_price": self._parse_int(output.get("stck_prpr")),
            "change": self._parse_int(output.get("prdy_vrss")),
            "change_pct": self._parse_float(output.get("prdy_ctrt")),
            "volume": self._parse_int(output.get("acml_vol")),
            "high_52w": self._parse_int(output.get("stck_dryy_hgpr")),  # 52주 최고가
            "low_52w": self._parse_int(output.get("stck_dryy_lwpr")),  # 52주 최저가
            "market_cap": self._parse_int(output.get("hts_avls")),  # 시가총액 (억원)
            "per": self._parse_float(output.get("per")),
            "pbr": self._parse_float(output.get("pbr")),
            "eps": self._parse_int(output.get("eps")),
            "bps": self._parse_int(output.get("bps")),
        }

    async def get_domestic_quotes_bulk(
        self,
        tickers: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Get quotes for multiple Korean stocks.

        Args:
            tickers: List of KRX stock codes
            progress_callback: Optional callback(completed, total)

        Returns:
            dict mapping ticker to quote data
        """
        results: dict[str, dict[str, Any]] = {}
        completed = 0
        total = len(tickers)

        for ticker in tickers:
            try:
                quote = await self.get_domestic_quote(ticker)
                if quote.get("current_price") is not None:
                    results[ticker] = quote

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

            except Exception as e:
                logger.debug(f"Failed to fetch {ticker}: {e}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        return results

    # ==================== Foreign (US) Stock APIs ====================

    async def get_foreign_quote(
        self,
        ticker: str,
        exchange: str = "NAS",
    ) -> dict[str, Any]:
        """
        Get current quote for a foreign (US) stock.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            exchange: Exchange code ("NYS", "NAS", "AMS")

        Returns:
            dict with: current_price, high_52w, low_52w, per, pbr, eps, bps
        """
        tr_id = "HHDFS00000300"  # 해외주식 현재가

        # Normalize exchange code
        exchange = self.EXCHANGE_CODES.get(exchange.upper(), exchange)

        params = {
            "AUTH": "",
            "EXCD": exchange,
            "SYMB": ticker,
        }

        data = await self._request("GET", self.FOREIGN_PRICE_PATH, tr_id, params=params)

        output = data.get("output", {})

        return {
            "ticker": ticker,
            "exchange": exchange,
            "current_price": self._parse_float(output.get("last")),
            "change": self._parse_float(output.get("diff")),
            "change_pct": self._parse_float(output.get("rate")),
            "volume": self._parse_int(output.get("tvol")),
            "high_52w": self._parse_float(output.get("h52p")),  # 52주 최고가
            "low_52w": self._parse_float(output.get("l52p")),  # 52주 최저가
            "per": self._parse_float(output.get("perx")),
            "pbr": self._parse_float(output.get("pbrx")),
            "eps": self._parse_float(output.get("epsx")),
            "bps": self._parse_float(output.get("bpsx")),
        }

    async def get_foreign_quotes_bulk(
        self,
        tickers: list[tuple[str, str]],  # (ticker, exchange) pairs
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Get quotes for multiple foreign stocks.

        Args:
            tickers: List of (ticker, exchange) tuples, e.g., [("AAPL", "NAS"), ("IBM", "NYS")]
            progress_callback: Optional callback(completed, total)

        Returns:
            dict mapping ticker to quote data
        """
        results: dict[str, dict[str, Any]] = {}
        completed = 0
        total = len(tickers)

        for ticker, exchange in tickers:
            try:
                quote = await self.get_foreign_quote(ticker, exchange)
                if quote.get("current_price") is not None:
                    results[ticker] = quote

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

            except Exception as e:
                logger.debug(f"Failed to fetch {ticker}: {e}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        return results

    # ==================== Utility Methods ====================

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        """Parse integer from string, handling empty/invalid values."""
        if not value or value in ("", "-", "0"):
            return None
        try:
            return int(value.replace(",", ""))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        """Parse float from string, handling empty/invalid values."""
        if not value or value in ("", "-", "0"):
            return None
        try:
            return float(value.replace(",", ""))
        except (ValueError, TypeError):
            return None

    def is_configured(self) -> bool:
        """Check if KIS API credentials are configured."""
        return bool(self.app_key and self.app_secret)


# Convenience function for sync usage
def get_domestic_quotes_sync(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """
    Synchronous wrapper for fetching Korean stock quotes.

    Usage:
        results = get_domestic_quotes_sync(["005930", "000660"])
    """

    async def _run():
        async with KISClient() as client:
            return await client.get_domestic_quotes_bulk(tickers)

    return asyncio.run(_run())
