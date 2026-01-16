"""Korea Investment & Securities API source.

KIS API provides accurate fundamental metrics from official source:
- PER, PBR, EPS, BPS
- 52-week high/low
- Market cap
- ROE, ROA, Debt ratio (from financial ratio endpoint)

Requires API credentials (KIS_APP_KEY, KIS_APP_SECRET).
This is the primary source for KR metrics; NaverSource is the fallback.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

import aiohttp

from core.errors import DataNotFoundError, NetworkError, RateLimitError, TimeoutError
from core.types import BatchFetchResult, FetchResult, MetricsData
from observability.logger import get_logger, log_context

if TYPE_CHECKING:
    from datetime import date

    from kr.config import KRConfig

logger = get_logger(__name__)


class KISAuthError(Exception):
    """KIS API authentication error."""

    pass


@dataclass
class KISSource:
    """Korea Investment & Securities API source.

    Provides fundamental metrics for Korean stocks from the official API.
    Requires valid API credentials.
    """

    config: KRConfig

    # API endpoints
    REAL_URL: ClassVar[str] = "https://openapi.koreainvestment.com:9443"
    PAPER_URL: ClassVar[str] = "https://openapivts.koreainvestment.com:29443"

    # API paths
    TOKEN_PATH: ClassVar[str] = "/oauth2/tokenP"
    DOMESTIC_PRICE_PATH: ClassVar[str] = "/uapi/domestic-stock/v1/quotations/inquire-price"
    FINANCIAL_RATIO_PATH: ClassVar[str] = "/uapi/domestic-stock/v1/finance/financial-ratio"

    def __post_init__(self) -> None:
        """Initialize KIS client state."""
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
        self._session: aiohttp.ClientSession | None = None
        self._rate_limit = 15.0  # requests per second
        self._tokens = self._rate_limit
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        """Check if KIS API credentials are configured."""
        return self.config.kis_available

    @property
    def base_url(self) -> str:
        """Get API base URL."""
        return self.REAL_URL

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
            return BatchFetchResult(results=results, source="kis")

        if not self.is_available:
            logger.warning("KIS API not configured")
            for ticker in tickers:
                results.append(
                    FetchResult(
                        ticker=ticker,
                        error=DataNotFoundError(
                            "KIS API not configured",
                            ticker=ticker,
                        ),
                        source="kis",
                    )
                )
            return BatchFetchResult(results=results, source="kis")

        # Create session
        await self._ensure_session()

        try:
            # Get access token first
            await self._get_access_token()

            # Process tickers with rate limiting
            batch_size = self.config.metrics_batch_size
            delay = 0.1  # 100ms between calls

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                batch_start = time.monotonic()

                with log_context(
                    source="kis",
                    phase="metrics",
                    batch_index=i // batch_size,
                    batch_size=len(batch),
                ):
                    for ticker in batch:
                        result = await self._fetch_single_metrics(ticker, trading_date, delay)
                        results.append(result)

                    batch_latency = (time.monotonic() - batch_start) * 1000
                    total_latency += batch_latency

                    # Log batch completion
                    batch_succeeded = sum(
                        1 for r in results[i:] if r.is_success
                    )
                    logger.info(
                        "Batch completed",
                        extra={
                            "success_count": batch_succeeded,
                            "failed_count": len(batch) - batch_succeeded,
                            "duration_ms": round(batch_latency, 2),
                        },
                    )

        finally:
            await self.close()

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="kis",
        )

    async def _fetch_single_metrics(
        self,
        ticker: str,
        trading_date: date,
        delay: float,
    ) -> FetchResult[MetricsData]:
        """Fetch metrics for a single ticker.

        Args:
            ticker: KRX ticker code
            trading_date: Date for the metrics
            delay: Delay after request

        Returns:
            FetchResult containing MetricsData or error
        """
        fetch_start = time.monotonic()

        try:
            # Fetch quote data (PER, PBR, EPS, BPS, 52w high/low)
            quote = await self._get_quote(ticker)

            # Fetch financial ratios (ROE, ROA, debt ratio)
            ratio = await self._get_financial_ratio(ticker)

            latency = (time.monotonic() - fetch_start) * 1000

            # Merge data
            if not quote.get("current_price"):
                return FetchResult(
                    ticker=ticker,
                    error=DataNotFoundError(
                        "No quote data from KIS",
                        ticker=ticker,
                    ),
                    latency_ms=latency,
                    source="kis",
                )

            # Convert to MetricsData
            metrics = MetricsData(
                ticker=ticker,
                date=trading_date,
                pe_ratio=quote.get("per"),
                pb_ratio=quote.get("pbr"),
                eps=quote.get("eps"),
                bps=quote.get("bps"),
                fifty_two_week_high=quote.get("high_52w"),
                fifty_two_week_low=quote.get("low_52w"),
                market_cap=quote.get("market_cap"),
                # From financial ratio (values are already percentages, convert to decimal)
                roe=self._to_decimal(ratio.get("roe")),
                gross_margin=self._to_decimal(ratio.get("gross_margin")),
                net_margin=self._to_decimal(ratio.get("net_margin")),
                debt_equity=ratio.get("debt_ratio"),
            )

            # Rate limiting delay
            await asyncio.sleep(delay)

            return FetchResult(
                ticker=ticker,
                data=metrics,
                latency_ms=latency,
                source="kis",
            )

        except asyncio.TimeoutError:
            latency = (time.monotonic() - fetch_start) * 1000
            return FetchResult(
                ticker=ticker,
                error=TimeoutError(
                    f"Timeout after {self.config.kis_timeout}s",
                    timeout=self.config.kis_timeout,
                    ticker=ticker,
                ),
                latency_ms=latency,
                source="kis",
            )

        except aiohttp.ClientError as e:
            latency = (time.monotonic() - fetch_start) * 1000
            return FetchResult(
                ticker=ticker,
                error=NetworkError(str(e), ticker=ticker),
                latency_ms=latency,
                source="kis",
            )

        except Exception as e:
            latency = (time.monotonic() - fetch_start) * 1000
            logger.debug(f"KIS fetch failed for {ticker}: {e}")
            return FetchResult(
                ticker=ticker,
                error=DataNotFoundError(str(e), ticker=ticker),
                latency_ms=latency,
                source="kis",
            )

    async def _get_quote(self, ticker: str) -> dict[str, Any]:
        """Get current quote for a Korean stock."""
        tr_id = "FHKST01010100"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }

        data = await self._request("GET", self.DOMESTIC_PRICE_PATH, tr_id, params=params)
        output = data.get("output", {})

        return {
            "ticker": ticker,
            "current_price": self._parse_int(output.get("stck_prpr")),
            "high_52w": self._parse_int(output.get("stck_dryy_hgpr")),
            "low_52w": self._parse_int(output.get("stck_dryy_lwpr")),
            "market_cap": self._parse_int(output.get("hts_avls")),
            "per": self._parse_float(output.get("per")),
            "pbr": self._parse_float(output.get("pbr")),
            "eps": self._parse_int(output.get("eps")),
            "bps": self._parse_int(output.get("bps")),
        }

    async def _get_financial_ratio(self, ticker: str) -> dict[str, Any]:
        """Get financial ratios for a Korean stock."""
        tr_id = "FHKST66430300"

        params = {
            "FID_DIV_CLS_CODE": "0",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            data = await self._request("GET", self.FINANCIAL_RATIO_PATH, tr_id, params=params)
            output = data.get("output", {})

            if isinstance(output, list) and output:
                output = output[0]

            # KIS API financial-ratio fields:
            # - grs: 매출총이익률 (gross margin)
            # - bsop_prfi_inrt: 영업이익률 (operating margin)
            # - ntin_inrt: 순이익률 (net margin)
            # - roe_val: ROE
            # - lblt_rate: 부채비율 (debt ratio)
            # - ROA is NOT provided by this endpoint

            return {
                "ticker": ticker,
                "roe": self._parse_float(output.get("roe_val")),
                "gross_margin": self._parse_float(output.get("grs")),
                "operating_margin": self._parse_float(output.get("bsop_prfi_inrt")),
                "net_margin": self._parse_float(output.get("ntin_inrt")),
                "debt_ratio": self._parse_float(output.get("lblt_rate")),
            }

        except Exception as e:
            logger.debug(f"Financial ratio failed for {ticker}: {e}")
            return {"ticker": ticker}

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.kis_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        # Check if we have a valid token
        if (
            self._access_token
            and self._token_expires
            and datetime.now() < self._token_expires - timedelta(minutes=5)
        ):
            return self._access_token

        assert self._session is not None, "Session not initialized"
        url = f"{self.base_url}{self.TOKEN_PATH}"

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.kis_app_key,
            "appsecret": self.config.kis_app_secret,
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise KISAuthError(f"Failed to get access token: {resp.status} {text}")

                data = await resp.json()

                if "access_token" not in data:
                    raise KISAuthError(f"No access token in response: {data}")

                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 86400)
                self._token_expires = datetime.now() + timedelta(seconds=expires_in)

                logger.info("KIS API access token acquired")
                return self._access_token

        except aiohttp.ClientError as e:
            raise KISAuthError(f"Network error getting access token: {e}") from e

    async def _acquire_rate_limit(self) -> None:
        """Acquire a token from the rate limiter."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self._rate_limit
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1

    async def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make API request with rate limiting."""
        await self._acquire_rate_limit()

        assert self._session is not None, "Session not initialized"
        assert self._access_token is not None, "No access token"

        url = f"{self.base_url}{path}"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self.config.kis_app_key or "",
            "appsecret": self.config.kis_app_secret or "",
            "tr_id": tr_id,
            "custtype": "P",
        }

        async with self._session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()

            if resp.status == 429:
                raise RateLimitError("KIS API rate limit exceeded")

            return data

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        """Parse integer from string."""
        if not value or value in ("", "-", "0"):
            return None
        try:
            return int(value.replace(",", ""))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        """Parse float from string."""
        if not value or value in ("", "-", "0"):
            return None
        try:
            return float(value.replace(",", ""))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_decimal(value: float | None) -> float | None:
        """Convert percentage to decimal (e.g., 9.03 -> 0.0903)."""
        if value is None:
            return None
        return value / 100

    async def close(self) -> None:
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
