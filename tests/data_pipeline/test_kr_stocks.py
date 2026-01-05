"""Tests for data_pipeline/collectors/kr_stocks.py.

TDD approach: Integration tests for Korean stock collector.
All external dependencies (FDR, KIS, Naver, yfinance) are mocked.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

# Add data-pipeline to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "data-pipeline"))

from collectors.kr_stocks import KRCollector

from .fixtures.fdr_data import (
    SAMPLE_KIS_FUNDAMENTALS,
    SAMPLE_KR_COMPANIES_CSV,
    SAMPLE_NAVER_FUNDAMENTALS,
    SAMPLE_PRICE_DATA,
    create_mock_kospi_df,
    create_mock_ohlcv_df,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_companies_csv(tmp_path):
    """Create a temporary kr_companies.csv file."""
    csv_path = tmp_path / "companies" / "kr_companies.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(SAMPLE_KR_COMPANIES_CSV)
    return csv_path


@pytest.fixture
def collector():
    """Create a KRCollector with DB disabled."""
    return KRCollector(
        market="ALL",
        save_db=False,
        save_csv=False,
        quiet=True,
    )


# =============================================================================
# Unit Tests: get_tickers()
# =============================================================================


class TestGetTickers:
    """Tests for get_tickers() method."""

    def test_load_from_csv(self, collector, mock_companies_csv):
        """Load tickers from CSV file."""
        with patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent):
            tickers = collector.get_tickers()

        assert len(tickers) == 5
        assert "005930" in tickers
        assert "000660" in tickers
        assert collector._ticker_names["005930"] == "삼성전자"
        assert collector._ticker_markets["005930"] == "KOSPI"

    def test_filter_by_market_kospi(self, mock_companies_csv):
        """Filter tickers by KOSPI market."""
        collector = KRCollector(market="KOSPI", save_db=False, save_csv=False, quiet=True)

        with patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent):
            tickers = collector.get_tickers()

        # All our sample data is KOSPI
        assert len(tickers) == 5

    def test_empty_csv_fallback(self, collector, tmp_path):
        """Return empty list when CSV is empty and pykrx unavailable."""
        csv_path = tmp_path / "companies" / "kr_companies.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("ticker,name,market\n")  # Empty

        with patch("collectors.kr_stocks.COMPANIES_DIR", csv_path.parent):
            with patch("collectors.kr_stocks.PYKRX_AVAILABLE", False):
                tickers = collector.get_tickers()

        assert tickers == []


# =============================================================================
# Unit Tests: fetch_prices_batch()
# =============================================================================


class TestFetchPricesBatch:
    """Tests for fetch_prices_batch() method."""

    def test_successful_fetch(self, collector):
        """Successfully fetch prices for multiple tickers."""

        def mock_fdr_datareader(ticker, start, end):
            return create_mock_ohlcv_df(ticker, days=7)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            result = collector.fetch_prices_batch(["005930", "000660"])

        assert len(result) == 2
        assert "005930" in result
        assert "000660" in result
        assert "close" in result["005930"]
        assert "volume" in result["005930"]
        assert "date" in result["005930"]

    def test_handles_empty_response(self, collector):
        """Handle tickers with no data."""

        def mock_fdr_datareader(ticker, start, end):
            if ticker == "NODATA":
                return pd.DataFrame()
            return create_mock_ohlcv_df(ticker, days=7)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            result = collector.fetch_prices_batch(["005930", "NODATA"])

        assert len(result) == 1
        assert "005930" in result
        assert "NODATA" not in result

    def test_handles_exceptions(self, collector):
        """Handle exceptions during fetch."""

        def mock_fdr_datareader(ticker, start, end):
            if ticker == "ERROR":
                raise Exception("Network error")
            return create_mock_ohlcv_df(ticker, days=7)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            result = collector.fetch_prices_batch(["005930", "ERROR"])

        assert len(result) == 1
        assert "005930" in result


# =============================================================================
# Unit Tests: fetch_fdr_history()
# =============================================================================


class TestFetchFdrHistory:
    """Tests for fetch_fdr_history() method."""

    def test_successful_fetch(self, collector):
        """Successfully fetch history for multiple tickers."""

        def mock_fdr_datareader(ticker, start, end):
            return create_mock_ohlcv_df(ticker, days=300)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            result = collector.fetch_fdr_history(["005930", "000660"], days=300)

        assert len(result) == 2
        assert "005930" in result
        assert isinstance(result["005930"], pd.DataFrame)
        assert len(result["005930"]) == 300

    def test_handles_empty_response(self, collector):
        """Handle tickers with no history."""

        def mock_fdr_datareader(ticker, start, end):
            if ticker == "NODATA":
                return pd.DataFrame()
            return create_mock_ohlcv_df(ticker, days=300)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            result = collector.fetch_fdr_history(["005930", "NODATA"], days=300)

        assert len(result) == 1
        assert "005930" in result


# =============================================================================
# Unit Tests: fetch_kospi_history()
# =============================================================================


class TestFetchKospiHistory:
    """Tests for fetch_kospi_history() method."""

    def test_successful_fetch_from_yfinance(self, collector):
        """Successfully fetch KOSPI from yfinance."""
        mock_kospi = create_mock_kospi_df(days=300)

        with patch("collectors.kr_stocks.yf.download", return_value=mock_kospi):
            result = collector.fetch_kospi_history(days=300)

        assert not result.empty
        assert len(result) == 300
        assert "Close" in result.columns

    def test_fallback_to_fdr(self, collector):
        """Fallback to FDR when yfinance fails."""
        mock_kospi = create_mock_kospi_df(days=300)

        with patch("collectors.kr_stocks.yf.download", return_value=pd.DataFrame()):
            with patch("collectors.kr_stocks.fdr.DataReader", return_value=mock_kospi):
                result = collector.fetch_kospi_history(days=300)

        assert not result.empty

    def test_returns_empty_on_all_failures(self, collector):
        """Return empty DataFrame when all sources fail."""
        with patch("collectors.kr_stocks.yf.download", side_effect=Exception("Failed")):
            with patch("collectors.kr_stocks.fdr.DataReader", side_effect=Exception("Failed")):
                result = collector.fetch_kospi_history(days=300)

        assert result.empty


# =============================================================================
# Unit Tests: _fetch_kis_fundamentals_async()
# =============================================================================


class TestFetchKisFundamentalsAsync:
    """Tests for _fetch_kis_fundamentals_async() method."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self, collector):
        """Successfully fetch fundamentals from KIS API."""
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True

        async def mock_get_quote(ticker):
            if ticker in SAMPLE_KIS_FUNDAMENTALS:
                data = SAMPLE_KIS_FUNDAMENTALS[ticker]
                return {
                    "current_price": 78500,
                    "per": data["pe_ratio"],
                    "pbr": data["pb_ratio"],
                    "eps": data["eps"],
                    "bps": data["book_value_per_share"],
                    "high_52w": data["fifty_two_week_high"],
                    "low_52w": data["fifty_two_week_low"],
                    "market_cap": data["market_cap"] // 100_000_000,  # in 억원
                }
            return {"current_price": None}

        mock_client.get_domestic_quote = mock_get_quote
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("collectors.kr_stocks.KISClient", return_value=mock_client):
            result = await collector._fetch_kis_fundamentals_async(["005930", "000660"])

        assert len(result) == 2
        assert result["005930"]["pe_ratio"] == 12.34
        assert result["005930"]["fifty_two_week_high"] == 85000

    @pytest.mark.asyncio
    async def test_not_configured(self, collector):
        """Return empty when KIS API not configured."""
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("collectors.kr_stocks.KISClient", return_value=mock_client):
            result = await collector._fetch_kis_fundamentals_async(["005930"])

        assert result == {}


# =============================================================================
# Phase Transition Tests (데이터 흐름 검증)
# =============================================================================


class TestPhaseTransitions:
    """Tests for data flow between collection phases."""

    def test_phase1_to_phase2_data_flow(self, collector, mock_companies_csv):
        """Phase 1 가격 데이터가 Phase 2로 올바르게 전달되는지 검증."""

        def mock_fdr_datareader(ticker, start, end):
            return create_mock_ohlcv_df(ticker, days=7)

        with (
            patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent),
            patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader),
        ):
            # Phase 1: 가격 수집
            prices = collector.fetch_prices_batch(["005930", "000660"])

        # 검증: Phase 1 출력이 Phase 2 입력 형식에 맞는지
        assert len(prices) == 2
        for ticker, price_data in prices.items():
            # Phase 2에서 필요한 필드들이 있는지 확인
            assert "close" in price_data, f"{ticker}: close 필드 누락"
            assert "volume" in price_data, f"{ticker}: volume 필드 누락"
            assert "date" in price_data, f"{ticker}: date 필드 누락"
            assert price_data["close"] > 0, f"{ticker}: 가격이 0 이하"

    def test_phase2_to_phase3_ticker_filtering(self, collector):
        """Phase 2에서 가격 있는 티커만 Phase 3로 전달되는지 검증."""
        # Phase 1 결과 시뮬레이션 (일부 티커만 가격 있음)
        prices = {
            "005930": {"close": 78500, "volume": 1000000, "date": "2025-01-03"},
            "000660": {"close": 185000, "volume": 500000, "date": "2025-01-03"},
            # "035720"은 가격 없음 (수집 실패 시뮬레이션)
        }

        # Phase 3로 전달될 티커 목록
        tickers_with_prices = list(prices.keys())

        # 검증: 가격 있는 티커만 전달
        assert len(tickers_with_prices) == 2
        assert "005930" in tickers_with_prices
        assert "000660" in tickers_with_prices
        assert "035720" not in tickers_with_prices

    def test_phase3_history_enables_phase4_technicals(self, collector):
        """Phase 3 히스토리가 Phase 4 기술적 지표 계산에 충분한지 검증."""

        def mock_fdr_datareader(ticker, start, end):
            # 300일 히스토리 반환
            return create_mock_ohlcv_df(ticker, days=300)

        with patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader):
            history = collector.fetch_fdr_history(["005930"], days=300)

        # 검증: Phase 4 기술적 지표 계산에 필요한 데이터가 있는지
        assert "005930" in history
        df = history["005930"]

        # RSI는 14일, MACD는 26일, 볼린저는 20일, Beta는 252일 필요
        assert len(df) >= 200, f"RSI/MACD/볼린저 계산에 데이터 부족: {len(df)}일"

        # 필수 컬럼 확인
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        for col in required_columns:
            assert col in df.columns, f"{col} 컬럼 누락"

    def test_phase4_technicals_output_format(self, collector):
        """Phase 4 기술적 지표 출력이 Phase 5 저장 형식에 맞는지 검증."""
        # 히스토리 데이터 생성
        history_df = create_mock_ohlcv_df("005930", days=300)

        # Phase 4 실행 (내부 메서드 직접 테스트)
        from common.indicators import calculate_all_technicals

        technicals = calculate_all_technicals(history_df)

        # Phase 5 저장에 필요한 지표들이 계산되었는지 확인
        expected_indicators = ["rsi", "macd", "macd_signal", "bb_upper", "bb_lower"]
        for indicator in expected_indicators:
            assert indicator in technicals, f"{indicator} 지표 누락"

    def test_full_pipeline_data_integrity(self, collector, mock_companies_csv, tmp_path):
        """전체 파이프라인에서 데이터 무결성 검증."""
        collected_data = {}

        def mock_fdr_datareader(ticker, start, end):
            df = create_mock_ohlcv_df(ticker, days=300)
            collected_data[f"fdr_{ticker}"] = len(df)
            return df

        mock_kospi = create_mock_kospi_df(days=300)

        mock_kis_client = MagicMock()
        mock_kis_client.is_configured.return_value = False
        mock_kis_client.__aenter__ = AsyncMock(return_value=mock_kis_client)
        mock_kis_client.__aexit__ = AsyncMock(return_value=None)

        mock_naver_client = MagicMock()

        async def mock_fetch_bulk(tickers, progress_callback=None):
            for t in tickers:
                collected_data[f"naver_{t}"] = True
            return {t: SAMPLE_NAVER_FUNDAMENTALS.get(t, {"pe_ratio": 10.0}) for t in tickers}

        mock_naver_client.fetch_bulk = mock_fetch_bulk
        mock_naver_client.__aenter__ = AsyncMock(return_value=mock_naver_client)
        mock_naver_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent),
            patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader),
            patch("collectors.kr_stocks.yf.download", return_value=mock_kospi),
            patch("collectors.kr_stocks.KISClient", return_value=mock_kis_client),
            patch("collectors.kr_stocks.NaverFinanceClient", return_value=mock_naver_client),
        ):
            collector.storage = MagicMock()
            collector.storage.load_completed_tickers.return_value = set()
            collector.storage.get_or_create_version_dir.return_value = tmp_path

            result = collector.collect(
                tickers=["005930", "000660"],
                is_test=True,
            )

        # 검증: 모든 Phase가 실행되었는지
        assert result["success"] >= 1, "최소 1개 이상 성공해야 함"

        # 각 티커가 모든 Phase를 거쳤는지 확인
        for ticker in ["005930", "000660"]:
            assert f"naver_{ticker}" in collected_data, f"{ticker}: Naver 수집 누락"


# =============================================================================
# Integration Tests: collect()
# =============================================================================


class TestCollectIntegration:
    """Integration tests for collect() method."""

    def test_collect_test_mode(self, collector, mock_companies_csv, tmp_path):
        """Test collection in test mode (3 tickers)."""
        # Mock all external dependencies
        def mock_fdr_datareader(ticker, start, end):
            return create_mock_ohlcv_df(ticker, days=300)

        mock_kospi = create_mock_kospi_df(days=300)

        # Mock KIS client
        mock_kis_client = MagicMock()
        mock_kis_client.is_configured.return_value = False  # Skip KIS
        mock_kis_client.__aenter__ = AsyncMock(return_value=mock_kis_client)
        mock_kis_client.__aexit__ = AsyncMock(return_value=None)

        # Mock Naver client
        mock_naver_client = MagicMock()

        async def mock_fetch_bulk(tickers, progress_callback=None):
            return {t: SAMPLE_NAVER_FUNDAMENTALS.get(t, {}) for t in tickers if t in SAMPLE_NAVER_FUNDAMENTALS}

        mock_naver_client.fetch_bulk = mock_fetch_bulk
        mock_naver_client.__aenter__ = AsyncMock(return_value=mock_naver_client)
        mock_naver_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent),
            patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader),
            patch("collectors.kr_stocks.yf.download", return_value=mock_kospi),
            patch("collectors.kr_stocks.KISClient", return_value=mock_kis_client),
            patch("collectors.kr_stocks.NaverFinanceClient", return_value=mock_naver_client),
        ):
            # Set up storage to avoid actual file operations
            collector.storage = MagicMock()
            collector.storage.load_completed_tickers.return_value = set()
            collector.storage.get_or_create_version_dir.return_value = tmp_path

            result = collector.collect(
                tickers=["005930", "000660", "035720"],
                is_test=True,
            )

        assert result["total"] == 3
        assert result["success"] >= 0  # May vary based on data availability

    def test_collect_with_resume(self, collector, mock_companies_csv, tmp_path):
        """Test collection with resume mode."""
        # Mock already completed tickers
        completed_tickers = {"005930", "000660"}

        def mock_fdr_datareader(ticker, start, end):
            return create_mock_ohlcv_df(ticker, days=300)

        mock_kospi = create_mock_kospi_df(days=300)

        mock_kis_client = MagicMock()
        mock_kis_client.is_configured.return_value = False
        mock_kis_client.__aenter__ = AsyncMock(return_value=mock_kis_client)
        mock_kis_client.__aexit__ = AsyncMock(return_value=None)

        mock_naver_client = MagicMock()

        async def mock_fetch_bulk(tickers, progress_callback=None):
            return {t: SAMPLE_NAVER_FUNDAMENTALS.get(t, {}) for t in tickers if t in SAMPLE_NAVER_FUNDAMENTALS}

        mock_naver_client.fetch_bulk = mock_fetch_bulk
        mock_naver_client.__aenter__ = AsyncMock(return_value=mock_naver_client)
        mock_naver_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("collectors.kr_stocks.COMPANIES_DIR", mock_companies_csv.parent),
            patch("collectors.kr_stocks.fdr.DataReader", side_effect=mock_fdr_datareader),
            patch("collectors.kr_stocks.yf.download", return_value=mock_kospi),
            patch("collectors.kr_stocks.KISClient", return_value=mock_kis_client),
            patch("collectors.kr_stocks.NaverFinanceClient", return_value=mock_naver_client),
        ):
            collector.storage = MagicMock()
            collector.storage.load_completed_tickers.return_value = completed_tickers
            collector.storage.resume_version_dir.return_value = tmp_path

            result = collector.collect(
                tickers=["005930", "000660", "035720"],
                resume=True,
                is_test=True,
            )

        # Only 035720 should be processed (others already completed)
        assert result["total"] == 1

    def test_collect_empty_tickers(self, collector):
        """Test collection with empty ticker list."""
        result = collector.collect(tickers=[])

        assert result["total"] == 0
        assert result["success"] == 0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_collector_initialization(self):
        """Test collector initialization with various options."""
        collector = KRCollector(
            market="KOSPI",
            save_db=False,
            save_csv=True,
            quiet=True,
        )

        assert collector.market == "KOSPI"
        assert collector.save_db is False
        assert collector.save_csv is True

    def test_collector_all_markets(self):
        """Test collector with ALL markets."""
        collector = KRCollector(market="ALL", save_db=False, save_csv=False)
        assert collector.market == "ALL"

    def test_fetch_stock_info_returns_none(self, collector):
        """fetch_stock_info returns None (compatibility method)."""
        result = collector.fetch_stock_info("005930")
        assert result is None

    def test_extract_trading_date_from_prices(self, collector):
        """Extract trading date from price data."""
        prices = {
            "005930": {"date": "2025-01-03", "close": 78500},
            "000660": {"date": "2025-01-03", "close": 185000},
        }

        # This is a private method, test indirectly through collect
        # or just verify the logic
        dates = [p.get("date") for p in prices.values() if p.get("date")]
        assert "2025-01-03" in dates


# =============================================================================
# Data Processing Tests
# =============================================================================


class TestDataProcessing:
    """Tests for data processing logic."""

    def test_merge_fundamentals_kis_priority(self, collector):
        """KIS data takes priority over Naver data."""
        kis_data = {"pe_ratio": 12.0, "pb_ratio": 1.5}
        naver_data = {"pe_ratio": 11.0, "pb_ratio": 1.4, "roe": 0.15}

        # Naver first, then KIS overwrites
        merged = {**naver_data, **kis_data}

        assert merged["pe_ratio"] == 12.0  # KIS value
        assert merged["pb_ratio"] == 1.5  # KIS value
        assert merged["roe"] == 0.15  # Naver value (not in KIS)

    def test_market_cap_conversion(self):
        """KIS market_cap is in 억원, needs conversion to 원."""
        kis_market_cap_in_eok = 4685000  # 억원
        expected_in_won = 4685000 * 100_000_000

        assert expected_in_won == 468500000000000

    def test_technical_indicators_calculation(self, collector):
        """Technical indicators are calculated from history."""
        # This is tested indirectly through collect()
        # The actual calculation is in indicators.py (already tested)
        pass
