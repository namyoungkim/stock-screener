"""
Korean Stock Data Collector

Collects financial data for Korean stocks using pykrx and OpenDartReader,
and saves to Supabase.
"""

import os
import time
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import OpenDartReader  # type: ignore[import-untyped]
import pandas as pd
from dotenv import load_dotenv
from pykrx import stock as pykrx  # type: ignore[import-untyped]
from supabase import Client, create_client
from tqdm import tqdm

if TYPE_CHECKING:
    from OpenDartReader.dart import OpenDartReader as OpenDartReaderType

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    return create_client(url, key)


def get_dart_reader() -> "OpenDartReaderType":
    """Get OpenDartReader instance."""
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY not set in environment variables")
    return OpenDartReader(DART_API_KEY)  # type: ignore[call-non-callable]


def get_krx_tickers(market: str = "ALL") -> pd.DataFrame:
    """
    Get KRX (KOSPI + KOSDAQ) tickers using pykrx.

    Args:
        market: "KOSPI", "KOSDAQ", or "ALL" for both.

    Returns:
        DataFrame with columns: ticker, name, market
    """
    today = datetime.now().strftime("%Y%m%d")

    tickers_data = []

    if market in ("KOSPI", "ALL"):
        kospi_tickers = pykrx.get_market_ticker_list(today, market="KOSPI")
        for ticker in kospi_tickers:
            name = pykrx.get_market_ticker_name(ticker)
            tickers_data.append({"ticker": ticker, "name": name, "market": "KOSPI"})

    if market in ("KOSDAQ", "ALL"):
        kosdaq_tickers = pykrx.get_market_ticker_list(today, market="KOSDAQ")
        for ticker in kosdaq_tickers:
            name = pykrx.get_market_ticker_name(ticker)
            tickers_data.append({"ticker": ticker, "name": name, "market": "KOSDAQ"})

    return pd.DataFrame(tickers_data)


def get_stock_info(ticker: str, name: str, market: str) -> dict:
    """Get stock info from pykrx."""
    today = datetime.now().strftime("%Y%m%d")

    try:
        # Get market cap and basic info
        df = pykrx.get_market_cap_by_date(today, today, ticker)

        market_cap = None
        volume = None

        if not df.empty:
            market_cap = int(df.iloc[-1]["시가총액"]) if "시가총액" in df.columns else None
            volume = int(df.iloc[-1]["거래량"]) if "거래량" in df.columns else None

        return {
            "ticker": ticker,
            "name": name,
            "market": market,
            "market_cap": market_cap,
            "volume": volume,
            "currency": "KRW",
        }
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return {
            "ticker": ticker,
            "name": name,
            "market": market,
            "market_cap": None,
            "volume": None,
            "currency": "KRW",
        }


def get_stock_price(ticker: str) -> dict | None:
    """Get latest stock price from pykrx."""
    today = datetime.now()
    start = (today - timedelta(days=7)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    try:
        df = pykrx.get_market_ohlcv(start, end, ticker)

        if df.empty:
            return None

        latest = df.iloc[-1]
        latest_date = df.index[-1]

        return {
            "date": latest_date.strftime("%Y-%m-%d"),
            "open": int(latest["시가"]) if pd.notna(latest["시가"]) else None,
            "high": int(latest["고가"]) if pd.notna(latest["고가"]) else None,
            "low": int(latest["저가"]) if pd.notna(latest["저가"]) else None,
            "close": int(latest["종가"]) if pd.notna(latest["종가"]) else None,
            "volume": int(latest["거래량"]) if pd.notna(latest["거래량"]) else None,
        }
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None


def get_corp_code(dart: "OpenDartReaderType", ticker: str) -> str | None:
    """Get DART corp_code from stock ticker."""
    try:
        # OpenDartReader has corp_codes property
        corp_list = dart.corp_codes

        if corp_list is None or corp_list.empty:
            return None

        # Find by stock_code
        match = corp_list[corp_list["stock_code"] == ticker]

        if match.empty:
            return None

        return match.iloc[0]["corp_code"]
    except Exception as e:
        print(f"Error finding corp_code for {ticker}: {e}")
        return None


def get_financial_statements(
    dart: "OpenDartReaderType", corp_code: str, year: int
) -> dict | None:
    """Get financial statements from DART."""
    try:
        # Get consolidated financial statements (연결재무제표)
        fs = dart.finstate(corp_code, year, reprt_code="11011")  # 사업보고서

        if fs is None or fs.empty:
            # Try individual financial statements
            fs = dart.finstate(corp_code, year)

        if fs is None or fs.empty:
            return None

        # DART finstate returns DataFrame with various account items
        # Extract key metrics by account name
        def get_amount(account_names: list[str]) -> float | None:
            for name in account_names:
                matches = fs[fs["account_nm"].str.contains(name, na=False, regex=False)]
                if not matches.empty:
                    # Get the first match, prefer 'thstrm_amount' (당기)
                    val = matches.iloc[0].get("thstrm_amount")
                    if pd.notna(val):
                        # Remove commas and convert to float
                        if isinstance(val, str):
                            val = val.replace(",", "")
                        return float(val)
            return None

        return {
            "corp_code": corp_code,
            "year": year,
            "revenue": get_amount(["매출액", "영업수익", "수익(매출액)"]),
            "operating_income": get_amount(["영업이익", "영업손익"]),
            "net_income": get_amount(["당기순이익", "분기순이익", "반기순이익"]),
            "total_assets": get_amount(["자산총계", "자산 총계"]),
            "total_liabilities": get_amount(["부채총계", "부채 총계"]),
            "total_equity": get_amount(["자본총계", "자본 총계"]),
        }
    except Exception as e:
        print(f"Error fetching financials for {corp_code}: {e}")
        return None


def calculate_metrics(
    financials: dict, stock_info: dict, price: dict | None
) -> dict | None:
    """Calculate investment metrics from financial data."""
    try:
        market_cap = stock_info.get("market_cap")
        if not market_cap or market_cap <= 0:
            return None

        revenue = financials.get("revenue")
        net_income = financials.get("net_income")
        total_equity = financials.get("total_equity")
        total_assets = financials.get("total_assets")
        total_liabilities = financials.get("total_liabilities")

        metrics = {}

        # P/E Ratio
        if net_income and net_income > 0:
            metrics["pe_ratio"] = market_cap / net_income

        # P/B Ratio
        if total_equity and total_equity > 0:
            metrics["pb_ratio"] = market_cap / total_equity

        # P/S Ratio
        if revenue and revenue > 0:
            metrics["ps_ratio"] = market_cap / revenue

        # ROE
        if total_equity and total_equity > 0 and net_income:
            metrics["roe"] = net_income / total_equity

        # ROA
        if total_assets and total_assets > 0 and net_income:
            metrics["roa"] = net_income / total_assets

        # Debt/Equity
        if total_equity and total_equity > 0 and total_liabilities:
            metrics["debt_equity"] = total_liabilities / total_equity

        # Net Margin
        if revenue and revenue > 0 and net_income:
            metrics["net_margin"] = net_income / revenue

        return metrics if metrics else None
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None


def upsert_company(client: Client, stock_info: dict, corp_code: str | None) -> str | None:
    """Insert or update company in Supabase, return company ID."""
    try:
        market_type = stock_info["market"]  # "KOSPI" or "KOSDAQ"

        data = {
            "ticker": stock_info["ticker"],
            "corp_code": corp_code,
            "name": stock_info["name"],
            "market": market_type,
            "currency": "KRW",
            "is_active": True,
        }

        result = (
            client.table("companies")
            .upsert(data, on_conflict="ticker,market")
            .execute()
        )

        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        print(f"Error upserting company {stock_info['ticker']}: {e}")
        return None


def upsert_financials(
    client: Client, company_id: str, financials: dict, year: int
) -> bool:
    """Insert or update financials in Supabase."""
    try:
        data = {
            "company_id": company_id,
            "fiscal_year": year,
            "quarter": "FY",
            "revenue": financials.get("revenue"),
            "operating_income": financials.get("operating_income"),
            "net_income": financials.get("net_income"),
            "total_assets": financials.get("total_assets"),
            "total_liabilities": financials.get("total_liabilities"),
            "total_equity": financials.get("total_equity"),
            "data_source": "dart",
        }

        client.table("financials").upsert(
            data, on_conflict="company_id,fiscal_year,quarter"
        ).execute()
        return True
    except Exception as e:
        print(f"Error upserting financials for company {company_id}: {e}")
        return False


def upsert_metrics(client: Client, company_id: str, metrics: dict) -> bool:
    """Insert or update metrics in Supabase."""
    try:
        today = date.today().isoformat()

        data = {
            "company_id": company_id,
            "date": today,
            "pe_ratio": metrics.get("pe_ratio"),
            "pb_ratio": metrics.get("pb_ratio"),
            "ps_ratio": metrics.get("ps_ratio"),
            "roe": metrics.get("roe"),
            "roa": metrics.get("roa"),
            "debt_equity": metrics.get("debt_equity"),
            "net_margin": metrics.get("net_margin"),
            "data_source": "calculated",
        }

        client.table("metrics").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting metrics for company {company_id}: {e}")
        return False


def upsert_price(
    client: Client, company_id: str, price: dict, market_cap: int | None
) -> bool:
    """Insert or update price in Supabase."""
    try:
        data = {
            "company_id": company_id,
            "date": price["date"],
            "open": price.get("open"),
            "high": price.get("high"),
            "low": price.get("low"),
            "close": price.get("close"),
            "volume": price.get("volume"),
            "market_cap": market_cap,
        }

        client.table("prices").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting price for company {company_id}: {e}")
        return False


def collect_and_save(
    market: str = "ALL",
    tickers: list[str] | None = None,
    delay: float = 0.3,
    fiscal_year: int | None = None,
    limit: int | None = None,
) -> dict:
    """
    Collect Korean stock data and save to Supabase.

    Args:
        market: "KOSPI", "KOSDAQ", or "ALL" for both.
        tickers: List of specific tickers to collect. If None, collects all.
        delay: Delay between API calls in seconds.
        fiscal_year: Year for financial statements. Defaults to last year.
        limit: Maximum number of stocks to process (for testing).

    Returns:
        Dictionary with success/failure counts.
    """
    client = get_supabase_client()
    dart = get_dart_reader()

    if fiscal_year is None:
        fiscal_year = datetime.now().year - 1

    print(f"Fetching {market} tickers...")
    df = get_krx_tickers(market)

    if tickers:
        df = df[df["ticker"].isin(tickers)]

    if limit:
        df = df.head(limit)

    print(f"Found {len(df)} tickers")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Collecting KR stocks"):
        ticker = row["ticker"]
        name = row["name"]
        mkt = row["market"]

        try:
            # Get stock info
            stock_info = get_stock_info(ticker, name, mkt)

            # Get corp_code for DART
            corp_code = get_corp_code(dart, ticker)

            # Upsert company
            company_id = upsert_company(client, stock_info, corp_code)
            if not company_id:
                stats["failed"] += 1
                continue

            # Get and save price
            price = get_stock_price(ticker)
            if price:
                upsert_price(client, company_id, price, stock_info.get("market_cap"))

            # Get financial statements if corp_code exists
            if corp_code:
                financials = get_financial_statements(dart, corp_code, fiscal_year)

                if financials:
                    upsert_financials(client, company_id, financials, fiscal_year)

                    # Calculate and save metrics
                    metrics = calculate_metrics(financials, stock_info, price)
                    if metrics:
                        upsert_metrics(client, company_id, metrics)

            stats["success"] += 1
            time.sleep(delay)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            stats["failed"] += 1

    print(f"\nCollection complete: {stats}")
    return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode: only a few tickers
        test_tickers = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오
        print("Running in test mode...")
        collect_and_save(tickers=test_tickers, delay=0.2)
    elif len(sys.argv) > 1 and sys.argv[1] == "--kospi":
        print("Running KOSPI collection...")
        collect_and_save(market="KOSPI")
    elif len(sys.argv) > 1 and sys.argv[1] == "--kosdaq":
        print("Running KOSDAQ collection...")
        collect_and_save(market="KOSDAQ")
    else:
        # Full collection
        print("Running full KRX (KOSPI + KOSDAQ) collection...")
        collect_and_save()
