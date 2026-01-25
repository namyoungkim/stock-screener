"""DART (Data Analysis, Retrieval and Transfer) API source.

DART provides official financial statements from Korean listed companies:
- Balance Sheet: Total assets, total liabilities, cash, debt
- Income Statement: Revenue, operating income, net income
- Calculated metrics: ROA, PS Ratio, EV/EBITDA

Requires DART API key (free registration at https://opendart.fss.or.kr).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from core.errors import DataNotFoundError
from core.types import BatchFetchResult, FetchResult, MetricsData
from observability.logger import get_logger, log_context

if TYPE_CHECKING:
    from kr.config import KRConfig

logger = get_logger(__name__)


@dataclass
class FinancialData:
    """Parsed financial statement data for metric calculation."""

    ticker: str
    corp_code: str | None = None

    # Balance Sheet items
    total_assets: float | None = None  # 자산총계
    total_liabilities: float | None = None  # 부채총계
    total_equity: float | None = None  # 자본총계
    cash_and_equivalents: float | None = None  # 현금및현금성자산
    short_term_debt: float | None = None  # 단기차입금
    long_term_debt: float | None = None  # 장기차입금

    # Income Statement items
    revenue: float | None = None  # 매출액
    operating_income: float | None = None  # 영업이익
    net_income: float | None = None  # 당기순이익
    depreciation: float | None = None  # 감가상각비 (for EBITDA)

    @property
    def total_debt(self) -> float | None:
        """Total debt (short + long term)."""
        if self.short_term_debt is None and self.long_term_debt is None:
            return None
        return (self.short_term_debt or 0) + (self.long_term_debt or 0)

    @property
    def net_debt(self) -> float | None:
        """Net debt (total debt - cash)."""
        debt = self.total_debt
        if debt is None:
            return None
        cash = self.cash_and_equivalents or 0
        return debt - cash

    @property
    def ebitda(self) -> float | None:
        """EBITDA (Operating Income + Depreciation)."""
        if self.operating_income is None:
            return None
        return self.operating_income + (self.depreciation or 0)


@dataclass
class DARTSource:
    """DART API source for Korean financial statements.

    Uses OpenDartReader library to fetch financial data and calculates:
    - ROA (Return on Assets)
    - PS Ratio (Price to Sales)
    - EV/EBITDA (Enterprise Value to EBITDA)
    """

    config: KRConfig

    # Lazy-loaded OpenDartReader instance
    _dart: Any = None
    _corp_codes: dict[str, str] | None = None  # ticker -> corp_code mapping

    @property
    def is_available(self) -> bool:
        """Check if DART API key is configured."""
        return self.config.dart_available

    def _get_dart(self) -> Any:
        """Get or create OpenDartReader instance."""
        if self._dart is None:
            try:
                import OpenDartReader

                self._dart = OpenDartReader(self.config.dart_api_key)
                logger.info("OpenDartReader initialized")
            except ImportError:
                logger.error("OpenDartReader not installed. Run: pip install opendartreader")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenDartReader: {e}")
                raise
        return self._dart

    async def fetch_financial_metrics(
        self,
        tickers: list[str],
        market_caps: dict[str, float | None],
        trading_date: date | None = None,
    ) -> BatchFetchResult[MetricsData]:
        """Fetch financial metrics from DART for multiple tickers.

        Args:
            tickers: List of KRX ticker codes
            market_caps: Dict of ticker -> market cap (needed for PS, EV/EBITDA)
            trading_date: Date for the metrics (default: today)

        Returns:
            BatchFetchResult containing MetricsData with ROA, ps_ratio, ev_ebitda
        """
        if trading_date is None:
            trading_date = date.today()

        results: list[FetchResult[MetricsData]] = []
        total_latency = 0.0

        if not tickers:
            return BatchFetchResult(results=results, source="dart")

        if not self.is_available:
            logger.warning("DART API not configured")
            for ticker in tickers:
                results.append(
                    FetchResult(
                        ticker=ticker,
                        error=DataNotFoundError(
                            "DART API not configured",
                            ticker=ticker,
                        ),
                        source="dart",
                    )
                )
            return BatchFetchResult(results=results, source="dart")

        # Initialize dart
        dart = self._get_dart()

        # Load corp codes mapping if not loaded
        if self._corp_codes is None:
            await self._load_corp_codes(dart)

        # Process tickers
        batch_size = self.config.metrics_batch_size
        delay = 0.2  # 200ms between calls (DART rate limit)

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_start = time.monotonic()

            with log_context(
                source="dart",
                phase="financials",
                batch_index=i // batch_size,
                batch_size=len(batch),
            ):
                for ticker in batch:
                    result = await self._fetch_single_metrics(
                        dart, ticker, market_caps.get(ticker), trading_date, delay
                    )
                    results.append(result)

                batch_latency = (time.monotonic() - batch_start) * 1000
                total_latency += batch_latency

                # Log batch completion
                batch_succeeded = sum(1 for r in results[i:] if r.is_success)
                logger.info(
                    "DART batch completed",
                    extra={
                        "success_count": batch_succeeded,
                        "failed_count": len(batch) - batch_succeeded,
                        "duration_ms": round(batch_latency, 2),
                    },
                )

        return BatchFetchResult(
            results=results,
            total_latency_ms=total_latency,
            source="dart",
        )

    async def _load_corp_codes(self, dart: Any) -> None:
        """Load corp code mapping from DART."""
        try:
            # Run in thread pool to avoid blocking
            # Note: dart.corp_codes is a property, not a method
            loop = asyncio.get_event_loop()
            corp_list = await loop.run_in_executor(None, lambda: dart.corp_codes)

            if corp_list is not None and not corp_list.empty:
                # Create mapping: stock_code -> corp_code
                self._corp_codes = {}
                for _, row in corp_list.iterrows():
                    stock_code = row.get("stock_code")
                    corp_code = row.get("corp_code")
                    if stock_code and corp_code and stock_code.strip():
                        # Normalize ticker (remove leading zeros for comparison)
                        self._corp_codes[stock_code.strip()] = corp_code
                logger.info(f"Loaded {len(self._corp_codes)} corp codes from DART")
            else:
                self._corp_codes = {}
                logger.warning("Failed to load corp codes from DART")
        except Exception as e:
            logger.error(f"Error loading corp codes: {e}")
            self._corp_codes = {}

    async def _fetch_single_metrics(
        self,
        dart: Any,
        ticker: str,
        market_cap: float | None,
        trading_date: date,
        delay: float,
    ) -> FetchResult[MetricsData]:
        """Fetch and calculate metrics for a single ticker."""
        fetch_start = time.monotonic()

        try:
            # Get corp code for ticker
            corp_code = self._corp_codes.get(ticker) if self._corp_codes else None
            if not corp_code:
                latency = (time.monotonic() - fetch_start) * 1000
                return FetchResult(
                    ticker=ticker,
                    error=DataNotFoundError(
                        f"Corp code not found for {ticker}",
                        ticker=ticker,
                    ),
                    latency_ms=latency,
                    source="dart",
                )

            # Fetch financial statements (run in thread pool)
            loop = asyncio.get_event_loop()
            financial_data = await loop.run_in_executor(
                None, self._fetch_financial_statements, dart, corp_code, ticker
            )

            latency = (time.monotonic() - fetch_start) * 1000

            if financial_data is None:
                return FetchResult(
                    ticker=ticker,
                    error=DataNotFoundError(
                        f"No financial data from DART for {ticker}",
                        ticker=ticker,
                    ),
                    latency_ms=latency,
                    source="dart",
                )

            # Calculate metrics
            metrics = self._calculate_metrics(financial_data, market_cap, trading_date)

            # Rate limiting delay
            await asyncio.sleep(delay)

            return FetchResult(
                ticker=ticker,
                data=metrics,
                latency_ms=latency,
                source="dart",
            )

        except Exception as e:
            latency = (time.monotonic() - fetch_start) * 1000
            logger.debug(f"DART fetch failed for {ticker}: {e}")
            return FetchResult(
                ticker=ticker,
                error=DataNotFoundError(str(e), ticker=ticker),
                latency_ms=latency,
                source="dart",
            )

    def _fetch_financial_statements(
        self, dart: Any, corp_code: str, ticker: str
    ) -> FinancialData | None:
        """Fetch financial statements from DART (synchronous).

        This method is called in a thread pool.
        """
        try:
            # Get the latest annual report year
            current_year = date.today().year
            report_year = current_year - 1  # Use last year's annual report

            # Fetch consolidated financial statements (연결재무제표)
            # reprt_code: 11011=1Q, 11012=반기, 11013=3Q, 11014=사업보고서(연간)
            fs = dart.finstate(corp_code, report_year, reprt_code="11014")

            if fs is None or fs.empty:
                # Try individual financial statements if consolidated not available
                fs = dart.finstate(corp_code, report_year, reprt_code="11014", fs_div="OFS")

            if fs is None or fs.empty:
                logger.debug(f"No financial statement for {ticker} ({report_year})")
                return None

            # Parse financial data
            return self._parse_financial_statements(ticker, corp_code, fs)

        except Exception as e:
            logger.debug(f"Error fetching financial statements for {ticker}: {e}")
            return None

    def _parse_financial_statements(
        self, ticker: str, corp_code: str, fs: Any
    ) -> FinancialData:
        """Parse financial statement DataFrame into FinancialData."""
        data = FinancialData(ticker=ticker, corp_code=corp_code)

        # Helper to find and parse value
        def find_value(keywords: list[str]) -> float | None:
            for keyword in keywords:
                # Search in account_nm column
                mask = fs["account_nm"].str.contains(keyword, na=False, regex=False)
                if mask.any():
                    row = fs[mask].iloc[0]
                    # Use thstrm_amount (당기금액) column
                    value = row.get("thstrm_amount")
                    if value:
                        try:
                            # Remove commas and convert to float
                            return float(str(value).replace(",", ""))
                        except (ValueError, TypeError):
                            pass
            return None

        # Balance Sheet items
        data.total_assets = find_value(["자산총계"])
        data.total_liabilities = find_value(["부채총계"])
        data.total_equity = find_value(["자본총계"])
        data.cash_and_equivalents = find_value(
            ["현금및현금성자산", "현금 및 현금성자산", "현금"]
        )
        data.short_term_debt = find_value(["단기차입금", "단기금융부채"])
        data.long_term_debt = find_value(["장기차입금", "장기금융부채", "사채"])

        # Income Statement items
        data.revenue = find_value(["매출액", "수익(매출액)", "영업수익"])
        data.operating_income = find_value(["영업이익", "영업이익(손실)"])
        data.net_income = find_value(
            ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"]
        )
        data.depreciation = find_value(["감가상각비", "유형자산상각비"])

        return data

    def _calculate_metrics(
        self, data: FinancialData, market_cap: float | None, trading_date: date
    ) -> MetricsData:
        """Calculate financial metrics from parsed data.

        Unit conversion:
        - market_cap from KIS API: 억원 (100 million KRW)
        - DART financial statements: 원 (KRW)
        - Convert market_cap: 억원 → 원 (multiply by 100,000,000)
        """
        # ROA = Net Income / Total Assets
        roa = None
        if data.net_income is not None and data.total_assets:
            roa = data.net_income / data.total_assets

        # Convert market_cap from 억원 to 원
        market_cap_krw = market_cap * 100_000_000 if market_cap else None

        # PS Ratio = Market Cap / Revenue
        ps_ratio = None
        if market_cap_krw and data.revenue and data.revenue > 0:
            ps_ratio = market_cap_krw / data.revenue

        # EV/EBITDA = (Market Cap + Net Debt) / EBITDA
        ev_ebitda = None
        if market_cap_krw and data.ebitda and data.ebitda > 0:
            net_debt = data.net_debt or 0
            enterprise_value = market_cap_krw + net_debt
            ev_ebitda = enterprise_value / data.ebitda

        return MetricsData(
            ticker=data.ticker,
            date=trading_date,
            roa=roa,
            ps_ratio=ps_ratio,
            ev_ebitda=ev_ebitda,
        )

    async def close(self) -> None:
        """Clean up resources."""
        self._dart = None
        self._corp_codes = None
