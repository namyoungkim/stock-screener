"""Tests for data_pipeline/common/kis_client.py.

TDD approach: Testing KIS API client.
- Utility methods: Direct testing (pure functions)
- API methods: Mock aiohttp responses
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add data-pipeline to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "data-pipeline"))

from common.kis_client import KISAuthError, KISClient, KISRateLimitError

from .fixtures.kis_responses import (
    KIS_DOMESTIC_QUOTE_RESPONSE,
    KIS_DOMESTIC_QUOTE_RESPONSE_ERROR,
    KIS_DOMESTIC_QUOTE_RESPONSE_MINIMAL,
    KIS_FOREIGN_QUOTE_RESPONSE,
    KIS_FOREIGN_QUOTE_RESPONSE_MINIMAL,
    KIS_TOKEN_RESPONSE_SUCCESS,
)


# =============================================================================
# Utility Method Tests (Pure Functions - No Mocking Required)
# =============================================================================


class TestParseInt:
    """Tests for _parse_int() static method."""

    def test_parse_valid_int(self):
        """Parse valid integer string."""
        assert KISClient._parse_int("12345") == 12345

    def test_parse_int_with_comma(self):
        """Parse integer with comma separator."""
        assert KISClient._parse_int("1,234,567") == 1234567

    def test_parse_empty_string(self):
        """Empty string returns None."""
        assert KISClient._parse_int("") is None

    def test_parse_dash(self):
        """Dash returns None."""
        assert KISClient._parse_int("-") is None

    def test_parse_zero_string(self):
        """Zero string returns None (treated as no data)."""
        assert KISClient._parse_int("0") is None

    def test_parse_none(self):
        """None returns None."""
        assert KISClient._parse_int(None) is None

    def test_parse_invalid(self):
        """Invalid string returns None."""
        assert KISClient._parse_int("invalid") is None


class TestParseFloat:
    """Tests for _parse_float() static method."""

    def test_parse_valid_float(self):
        """Parse valid float string."""
        assert KISClient._parse_float("12.34") == 12.34

    def test_parse_float_with_comma(self):
        """Parse float with comma separator."""
        assert KISClient._parse_float("1,234.56") == 1234.56

    def test_parse_integer_as_float(self):
        """Parse integer string as float."""
        assert KISClient._parse_float("100") == 100.0

    def test_parse_empty_string(self):
        """Empty string returns None."""
        assert KISClient._parse_float("") is None

    def test_parse_dash(self):
        """Dash returns None."""
        assert KISClient._parse_float("-") is None

    def test_parse_zero_string(self):
        """Zero string returns None (treated as no data)."""
        assert KISClient._parse_float("0") is None

    def test_parse_none(self):
        """None returns None."""
        assert KISClient._parse_float(None) is None

    def test_parse_invalid(self):
        """Invalid string returns None."""
        assert KISClient._parse_float("invalid") is None


class TestIsConfigured:
    """Tests for is_configured() method."""

    def test_configured_with_credentials(self):
        """Returns True when both app_key and app_secret are set."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        assert client.is_configured() is True

    def test_not_configured_missing_key(self):
        """Returns False when app_key is missing."""
        # Patch _get_kis_defaults to return None for defaults
        with patch("common.kis_client._get_kis_defaults", return_value=(None, None, False)):
            client = KISClient(app_key=None, app_secret="test_secret")
            assert client.is_configured() is False

    def test_not_configured_missing_secret(self):
        """Returns False when app_secret is missing."""
        with patch("common.kis_client._get_kis_defaults", return_value=(None, None, False)):
            client = KISClient(app_key="test_key", app_secret=None)
            assert client.is_configured() is False

    def test_not_configured_empty_strings(self):
        """Returns False when credentials are empty strings."""
        with patch("common.kis_client._get_kis_defaults", return_value=(None, None, False)):
            client = KISClient(app_key=None, app_secret=None)
            assert client.is_configured() is False


class TestClientConfiguration:
    """Tests for client configuration."""

    def test_default_rate_limit(self):
        """Default rate limit is 15 requests per second."""
        client = KISClient(app_key="key", app_secret="secret")
        assert client._rate_limit == 15.0

    def test_custom_rate_limit(self):
        """Custom rate limit can be set."""
        client = KISClient(app_key="key", app_secret="secret", rate_limit=10.0)
        assert client._rate_limit == 10.0

    def test_real_url_default(self):
        """Default URL is real trading API."""
        client = KISClient(app_key="key", app_secret="secret", is_paper=False)
        assert client.base_url == KISClient.REAL_URL

    def test_paper_url_when_paper_trading(self):
        """Paper trading URL when is_paper is True."""
        client = KISClient(app_key="key", app_secret="secret", is_paper=True)
        assert client.base_url == KISClient.PAPER_URL


# =============================================================================
# Token Management Tests (Mocking Required)
# =============================================================================


class TestGetAccessToken:
    """Tests for _get_access_token() method."""

    @pytest.mark.asyncio
    async def test_successful_token_acquisition(self):
        """Successfully acquire access token."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=KIS_TOKEN_RESPONSE_SUCCESS)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            token = await client._get_access_token()

        assert token == KIS_TOKEN_RESPONSE_SUCCESS["access_token"]
        assert client._access_token == token
        assert client._token_expires is not None

    @pytest.mark.asyncio
    async def test_reuses_valid_token(self):
        """Reuses existing token if not expired."""
        from datetime import datetime, timedelta

        client = KISClient(app_key="test_key", app_secret="test_secret")

        # Set existing valid token
        client._access_token = "existing_token"
        client._token_expires = datetime.now() + timedelta(hours=1)

        # Should not make HTTP request
        with patch.object(client, "_get_session") as mock_session:
            token = await client._get_access_token()

        mock_session.assert_not_called()
        assert token == "existing_token"

    @pytest.mark.asyncio
    async def test_token_error_raises_exception(self):
        """HTTP error raises KISAuthError."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(client, "_get_session", return_value=mock_session):
            with pytest.raises(KISAuthError):
                await client._get_access_token()


# =============================================================================
# Domestic Stock API Tests (Mocking Required)
# =============================================================================


class TestGetDomesticQuote:
    """Tests for get_domestic_quote() method."""

    @pytest.mark.asyncio
    async def test_successful_quote(self):
        """Successfully get domestic stock quote."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        # Pre-set token to skip token acquisition
        client._access_token = "test_token"
        from datetime import datetime, timedelta

        client._token_expires = datetime.now() + timedelta(hours=1)

        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=KIS_DOMESTIC_QUOTE_RESPONSE)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch.object(client, "_acquire_rate_limit", return_value=None):
                result = await client.get_domestic_quote("005930")

        assert result["ticker"] == "005930"
        assert result["current_price"] == 78500
        assert result["high_52w"] == 85000
        assert result["low_52w"] == 65000
        assert result["market_cap"] == 4685000
        assert result["per"] == 12.34
        assert result["pbr"] == 1.45
        assert result["eps"] == 6361
        assert result["bps"] == 54138

    @pytest.mark.asyncio
    async def test_quote_with_minimal_data(self):
        """Handle quote with minimal data (some fields empty)."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        client._access_token = "test_token"
        from datetime import datetime, timedelta

        client._token_expires = datetime.now() + timedelta(hours=1)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=KIS_DOMESTIC_QUOTE_RESPONSE_MINIMAL)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch.object(client, "_acquire_rate_limit", return_value=None):
                result = await client.get_domestic_quote("TEST")

        assert result["current_price"] == 50000
        assert result["high_52w"] is None  # Empty string
        assert result["low_52w"] is None
        assert result["per"] is None  # Dash
        assert result["pbr"] is None  # Zero string


class TestGetDomesticQuotesBulk:
    """Tests for get_domestic_quotes_bulk() method."""

    @pytest.mark.asyncio
    async def test_bulk_quotes(self):
        """Fetch multiple domestic stock quotes."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        call_count = {"value": 0}

        async def mock_get_quote(ticker: str):
            call_count["value"] += 1
            return {
                "ticker": ticker,
                "current_price": 50000 + call_count["value"] * 1000,
            }

        with patch.object(client, "get_domestic_quote", side_effect=mock_get_quote):
            result = await client.get_domestic_quotes_bulk(["005930", "000660"])

        assert len(result) == 2
        assert "005930" in result
        assert "000660" in result

    @pytest.mark.asyncio
    async def test_bulk_with_progress_callback(self):
        """Progress callback is called for each ticker."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        progress_calls = []

        def progress_callback(completed: int, total: int):
            progress_calls.append((completed, total))

        async def mock_get_quote(ticker: str):
            return {"ticker": ticker, "current_price": 50000}

        with patch.object(client, "get_domestic_quote", side_effect=mock_get_quote):
            await client.get_domestic_quotes_bulk(
                ["005930", "000660"],
                progress_callback=progress_callback,
            )

        assert len(progress_calls) == 2
        assert (2, 2) in progress_calls

    @pytest.mark.asyncio
    async def test_bulk_handles_failures(self):
        """Handle individual ticker failures gracefully."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        async def mock_get_quote(ticker: str):
            if ticker == "FAIL":
                raise Exception("Network error")
            return {"ticker": ticker, "current_price": 50000}

        with patch.object(client, "get_domestic_quote", side_effect=mock_get_quote):
            result = await client.get_domestic_quotes_bulk(["005930", "FAIL", "000660"])

        # Should have 2 successful results
        assert len(result) == 2
        assert "005930" in result
        assert "000660" in result
        assert "FAIL" not in result

    @pytest.mark.asyncio
    async def test_bulk_excludes_null_prices(self):
        """Exclude results with null current_price."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        async def mock_get_quote(ticker: str):
            if ticker == "NODATA":
                return {"ticker": ticker, "current_price": None}
            return {"ticker": ticker, "current_price": 50000}

        with patch.object(client, "get_domestic_quote", side_effect=mock_get_quote):
            result = await client.get_domestic_quotes_bulk(["005930", "NODATA"])

        assert len(result) == 1
        assert "005930" in result
        assert "NODATA" not in result


# =============================================================================
# Foreign Stock API Tests (Mocking Required)
# =============================================================================


class TestGetForeignQuote:
    """Tests for get_foreign_quote() method."""

    @pytest.mark.asyncio
    async def test_successful_quote(self):
        """Successfully get foreign stock quote."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        client._access_token = "test_token"
        from datetime import datetime, timedelta

        client._token_expires = datetime.now() + timedelta(hours=1)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=KIS_FOREIGN_QUOTE_RESPONSE)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch.object(client, "_acquire_rate_limit", return_value=None):
                result = await client.get_foreign_quote("AAPL", "NAS")

        assert result["ticker"] == "AAPL"
        assert result["exchange"] == "NAS"
        assert result["current_price"] == 195.25
        assert result["high_52w"] == 199.62
        assert result["low_52w"] == 164.08
        assert result["per"] == 30.15
        assert result["pbr"] == 45.20

    @pytest.mark.asyncio
    async def test_exchange_code_normalization(self):
        """Exchange codes are normalized."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        client._access_token = "test_token"
        from datetime import datetime, timedelta

        client._token_expires = datetime.now() + timedelta(hours=1)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=KIS_FOREIGN_QUOTE_RESPONSE)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            with patch.object(client, "_acquire_rate_limit", return_value=None):
                # Test with "NASDAQ" instead of "NAS"
                result = await client.get_foreign_quote("AAPL", "NASDAQ")

        # Exchange should be normalized to "NAS"
        assert result["exchange"] == "NAS"


class TestGetForeignQuotesBulk:
    """Tests for get_foreign_quotes_bulk() method."""

    @pytest.mark.asyncio
    async def test_bulk_quotes(self):
        """Fetch multiple foreign stock quotes."""
        client = KISClient(app_key="test_key", app_secret="test_secret")

        async def mock_get_quote(ticker: str, exchange: str):
            return {
                "ticker": ticker,
                "exchange": exchange,
                "current_price": 100.0,
            }

        with patch.object(client, "get_foreign_quote", side_effect=mock_get_quote):
            result = await client.get_foreign_quotes_bulk([
                ("AAPL", "NAS"),
                ("IBM", "NYS"),
            ])

        assert len(result) == 2
        assert "AAPL" in result
        assert "IBM" in result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Rate limit response raises KISRateLimitError."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        client._access_token = "test_token"
        from datetime import datetime, timedelta

        client._token_expires = datetime.now() + timedelta(hours=1)

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(return_value={"error": "rate_limit"})

        with patch.object(
            client, "_handle_response", side_effect=KISRateLimitError("Rate limit")
        ):
            with pytest.raises(KISRateLimitError):
                await client._handle_response(mock_response)

    def test_get_headers_without_token(self):
        """Getting headers without token raises KISAuthError."""
        client = KISClient(app_key="test_key", app_secret="test_secret")
        client._access_token = None

        with pytest.raises(KISAuthError):
            client._get_headers("FHKST01010100")


# =============================================================================
# Client Lifecycle Tests
# =============================================================================


class TestClientLifecycle:
    """Tests for client session management."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Client works as async context manager."""
        async with KISClient(app_key="key", app_secret="secret") as client:
            assert client is not None
            assert isinstance(client, KISClient)

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Client properly closes session."""
        client = KISClient(app_key="key", app_secret="secret")

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()
        assert client._session is None

    def test_exchange_codes_mapping(self):
        """Exchange codes are properly mapped."""
        assert KISClient.EXCHANGE_CODES["NYSE"] == "NYS"
        assert KISClient.EXCHANGE_CODES["NASDAQ"] == "NAS"
        assert KISClient.EXCHANGE_CODES["AMEX"] == "AMS"
        assert KISClient.EXCHANGE_CODES["US"] == "NAS"
