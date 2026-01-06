"""Tests for data_pipeline/common/naver_finance.py.

TDD approach: Testing Naver Finance client.
- Parsing functions: Direct testing with HTML fixtures
- HTTP functions: Mock aiohttp responses
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add data-pipeline to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "data-pipeline"))

from common.naver_finance import NaverFinanceClient, fetch_naver_fundamentals_sync

from .fixtures.naver_html import (
    NAVER_COINFO_PAGE_HTML,
    NAVER_COINFO_PAGE_HTML_PARTIAL,
    NAVER_MAIN_PAGE_HTML,
    NAVER_MAIN_PAGE_HTML_EMPTY,
    NAVER_MAIN_PAGE_HTML_MISSING,
    NAVER_SISE_PAGE_HTML,
    NAVER_SISE_PAGE_HTML_NO_DIVIDEND,
    NAVER_SISE_PAGE_HTML_SMALL_CAP,
)


# =============================================================================
# Parsing Function Tests (Pure Functions - No Mocking Required)
# =============================================================================


class TestParseFundamentals:
    """Tests for _parse_fundamentals() method."""

    def test_parse_all_values(self):
        """Parse PER, EPS, PBR, BPS from complete HTML."""
        client = NaverFinanceClient()
        result = client._parse_fundamentals(NAVER_MAIN_PAGE_HTML)

        assert result["pe_ratio"] == 12.34
        assert result["eps"] == 6789.0  # Comma removed
        assert result["pb_ratio"] == 1.45
        assert result["book_value_per_share"] == 55000.0

    def test_parse_with_missing_values(self):
        """Parse HTML where some values are dash (-)."""
        client = NaverFinanceClient()
        result = client._parse_fundamentals(NAVER_MAIN_PAGE_HTML_MISSING)

        # PER and EPS should be missing (dash)
        assert "pe_ratio" not in result
        assert "eps" not in result
        # PBR and BPS should be present
        assert result["pb_ratio"] == 0.85
        assert result["book_value_per_share"] == 12000.0

    def test_parse_empty_html(self):
        """Parse empty/invalid HTML returns empty dict."""
        client = NaverFinanceClient()
        result = client._parse_fundamentals(NAVER_MAIN_PAGE_HTML_EMPTY)

        assert result == {}

    def test_parse_completely_empty_string(self):
        """Parse empty string returns empty dict."""
        client = NaverFinanceClient()
        result = client._parse_fundamentals("")

        assert result == {}


class TestParseFinancialRatios:
    """Tests for _parse_financial_ratios() method."""

    def test_parse_all_ratios(self):
        """Parse ROE, ROA, debt ratio, current ratio from complete HTML."""
        client = NaverFinanceClient()
        result = client._parse_financial_ratios(NAVER_COINFO_PAGE_HTML)

        # ROE and ROA are converted to decimal (divided by 100)
        assert result["roe"] == pytest.approx(0.1532, rel=1e-3)
        assert result["roa"] == pytest.approx(0.0875, rel=1e-3)
        # Debt ratio stays as percentage
        assert result["debt_equity"] == 35.50
        # Current ratio is converted to decimal
        assert result["current_ratio"] == pytest.approx(2.458, rel=1e-3)

    def test_parse_partial_ratios(self):
        """Parse HTML with only some ratios present."""
        client = NaverFinanceClient()
        result = client._parse_financial_ratios(NAVER_COINFO_PAGE_HTML_PARTIAL)

        assert result["roe"] == pytest.approx(0.225, rel=1e-3)
        assert result["debt_equity"] == 120.30
        # ROA and current_ratio should be missing
        assert "roa" not in result
        assert "current_ratio" not in result

    def test_parse_empty_html(self):
        """Parse empty HTML returns empty dict."""
        client = NaverFinanceClient()
        result = client._parse_financial_ratios("")

        assert result == {}


class TestParseMarketData:
    """Tests for _parse_market_data() method."""

    def test_parse_large_market_cap(self):
        """Parse large market cap (억원 format)."""
        client = NaverFinanceClient()
        result = client._parse_market_data(NAVER_SISE_PAGE_HTML)

        # 4,500,000억 = 4,500,000 * 100,000,000 = 450조
        assert result["market_cap"] == 4_500_000 * 100_000_000
        assert result["dividend_yield"] == pytest.approx(0.0235, rel=1e-3)

    def test_parse_small_market_cap(self):
        """Parse smaller market cap."""
        client = NaverFinanceClient()
        result = client._parse_market_data(NAVER_SISE_PAGE_HTML_SMALL_CAP)

        # 1,234억 = 1,234 * 100,000,000
        assert result["market_cap"] == 1234 * 100_000_000
        assert result["dividend_yield"] == pytest.approx(0.005, rel=1e-3)

    def test_parse_no_dividend(self):
        """Parse HTML with no dividend (dash)."""
        client = NaverFinanceClient()
        result = client._parse_market_data(NAVER_SISE_PAGE_HTML_NO_DIVIDEND)

        assert result["market_cap"] == 500 * 100_000_000
        # dividend_yield should be missing
        assert "dividend_yield" not in result

    def test_parse_empty_html(self):
        """Parse empty HTML returns empty dict."""
        client = NaverFinanceClient()
        result = client._parse_market_data("")

        assert result == {}


# =============================================================================
# HTTP Request Tests (Mocking Required)
# =============================================================================


class TestGetFundamentals:
    """Tests for get_fundamentals() method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_successful_request(self):
        """Successful HTTP request returns parsed data."""
        client = NaverFinanceClient()

        # Create mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=NAVER_MAIN_PAGE_HTML)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create mock session
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.get_fundamentals("005930")

        assert result["pe_ratio"] == 12.34
        assert result["eps"] == 6789.0

    @pytest.mark.asyncio
    async def test_http_error(self):
        """HTTP error returns empty dict."""
        client = NaverFinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.get_fundamentals("INVALID")

        assert result == {}

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Exception during request returns empty dict."""
        client = NaverFinanceClient()

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Network error"))

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.get_fundamentals("005930")

        assert result == {}


class TestGetFinancialRatios:
    """Tests for get_financial_ratios() method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_successful_request(self):
        """Successful HTTP request returns parsed ratios."""
        client = NaverFinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=NAVER_COINFO_PAGE_HTML)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.get_financial_ratios("005930")

        assert result["roe"] == pytest.approx(0.1532, rel=1e-3)
        assert result["debt_equity"] == 35.50


class TestGetMarketData:
    """Tests for get_market_data() method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_successful_request(self):
        """Successful HTTP request returns parsed market data."""
        client = NaverFinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=NAVER_SISE_PAGE_HTML)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.get_market_data("005930")

        assert result["market_cap"] == 4_500_000 * 100_000_000
        assert result["dividend_yield"] == pytest.approx(0.0235, rel=1e-3)


class TestGetAllData:
    """Tests for get_all_data() method."""

    @pytest.mark.asyncio
    async def test_combines_all_data(self):
        """get_all_data combines fundamentals, ratios, and market data."""
        client = NaverFinanceClient()

        # Mock all three methods
        with (
            patch.object(
                client,
                "get_fundamentals",
                return_value={"pe_ratio": 12.34, "eps": 6789.0},
            ),
            patch.object(
                client,
                "get_financial_ratios",
                return_value={"roe": 0.1532, "debt_equity": 35.50},
            ),
            patch.object(
                client,
                "get_market_data",
                return_value={"market_cap": 450_000_000_000_000},
            ),
        ):
            result = await client.get_all_data("005930")

        assert result["pe_ratio"] == 12.34
        assert result["eps"] == 6789.0
        assert result["roe"] == 0.1532
        assert result["debt_equity"] == 35.50
        assert result["market_cap"] == 450_000_000_000_000

    @pytest.mark.asyncio
    async def test_handles_partial_failures(self):
        """get_all_data handles partial failures gracefully."""
        client = NaverFinanceClient()

        # One method returns exception
        with (
            patch.object(
                client,
                "get_fundamentals",
                return_value={"pe_ratio": 12.34},
            ),
            patch.object(
                client,
                "get_financial_ratios",
                side_effect=Exception("Failed"),
            ),
            patch.object(
                client,
                "get_market_data",
                return_value={"market_cap": 100_000_000_000},
            ),
        ):
            result = await client.get_all_data("005930")

        # Should still have data from successful calls
        assert result["pe_ratio"] == 12.34
        assert result["market_cap"] == 100_000_000_000
        # Failed method data should be missing
        assert "roe" not in result


class TestFetchBulk:
    """Tests for fetch_bulk() method."""

    @pytest.mark.asyncio
    async def test_fetches_multiple_tickers(self):
        """fetch_bulk fetches data for multiple tickers."""
        client = NaverFinanceClient()

        call_count = {"value": 0}

        async def mock_get_all_data(ticker: str):
            call_count["value"] += 1
            return {"pe_ratio": 10.0 + call_count["value"], "ticker": ticker}

        with patch.object(client, "get_all_data", side_effect=mock_get_all_data):
            with patch.object(client, "_get_session", return_value=MagicMock()):
                result = await client.fetch_bulk(["005930", "000660", "035720"])

        assert len(result) == 3
        assert "005930" in result
        assert "000660" in result
        assert "035720" in result

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """fetch_bulk calls progress callback."""
        client = NaverFinanceClient()
        progress_calls = []

        def progress_callback(completed: int, total: int):
            progress_calls.append((completed, total))

        async def mock_get_all_data(ticker: str):
            return {"pe_ratio": 10.0}

        with patch.object(client, "get_all_data", side_effect=mock_get_all_data):
            with patch.object(client, "_get_session", return_value=MagicMock()):
                await client.fetch_bulk(
                    ["005930", "000660"],
                    progress_callback=progress_callback,
                )

        # Should have 2 progress calls (one for each ticker)
        assert len(progress_calls) == 2
        # Final call should be (2, 2)
        assert (2, 2) in progress_calls

    @pytest.mark.asyncio
    async def test_handles_failures(self):
        """fetch_bulk handles individual ticker failures."""
        client = NaverFinanceClient()

        async def mock_get_all_data(ticker: str):
            if ticker == "FAIL":
                raise Exception("Failed")
            return {"pe_ratio": 10.0}

        with patch.object(client, "get_all_data", side_effect=mock_get_all_data):
            with patch.object(client, "_get_session", return_value=MagicMock()):
                result = await client.fetch_bulk(["005930", "FAIL", "000660"])

        # Should have 2 successful results (FAIL excluded)
        assert len(result) == 2
        assert "005930" in result
        assert "000660" in result
        assert "FAIL" not in result

    @pytest.mark.asyncio
    async def test_empty_data_excluded(self):
        """fetch_bulk excludes tickers with empty data."""
        client = NaverFinanceClient()

        async def mock_get_all_data(ticker: str):
            if ticker == "EMPTY":
                return {}  # Empty data
            return {"pe_ratio": 10.0}

        with patch.object(client, "get_all_data", side_effect=mock_get_all_data):
            with patch.object(client, "_get_session", return_value=MagicMock()):
                result = await client.fetch_bulk(["005930", "EMPTY"])

        # EMPTY should be excluded
        assert len(result) == 1
        assert "005930" in result
        assert "EMPTY" not in result


# =============================================================================
# Client Lifecycle Tests
# =============================================================================


class TestClientLifecycle:
    """Tests for client session management."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Client works as async context manager."""
        async with NaverFinanceClient() as client:
            assert client is not None
            assert isinstance(client, NaverFinanceClient)

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Client properly closes session."""
        client = NaverFinanceClient()

        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()
        assert client._session is None

    def test_default_configuration(self):
        """Client has sensible defaults."""
        client = NaverFinanceClient()

        assert client.concurrency == 10
        assert client.timeout == 15.0
        assert client.delay == 0.05

    def test_custom_configuration(self):
        """Client accepts custom configuration."""
        client = NaverFinanceClient(
            concurrency=5,
            timeout=30.0,
            delay_between_requests=0.1,
        )

        assert client.concurrency == 5
        assert client.timeout == 30.0
        assert client.delay == 0.1
