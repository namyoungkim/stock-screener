"""
Korean Stock Data Collector

Collects financial data for Korean stocks using pykrx and OpenDartReader,
and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.

Optimized for speed with:
- Batch yfinance calls (50 tickers at a time)
- Pre-fetched pykrx market data (single API call for all stocks)
- ThreadPoolExecutor for parallel processing
"""

import math
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import OpenDartReader  # type: ignore[import-untyped]
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from pykrx import stock as pykrx  # type: ignore[import-untyped]
from tqdm import tqdm

from supabase import Client, create_client


def calculate_graham_number(eps: float | None, bvps: float | None) -> float | None:
    """
    Calculate Graham Number = sqrt(22.5 * EPS * BVPS).

    Only valid when both EPS and BVPS are positive.
    """
    if eps is None or bvps is None:
        return None
    if eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)

if TYPE_CHECKING:
    from OpenDartReader.dart import OpenDartReader as OpenDartReaderType

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")

# Data directory for CSV exports
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
FINANCIALS_DIR = DATA_DIR / "financials"


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    return create_client(url, key)


def get_dart_reader() -> "OpenDartReaderType | None":
    """Get OpenDartReader instance. Returns None if API key not set."""
    if not DART_API_KEY:
        print("Warning: DART_API_KEY not set. Financial statements will be skipped.")
        return None
    return OpenDartReader(DART_API_KEY)  # type: ignore[call-non-callable]


def get_market_data_bulk(target_date: str | None = None) -> tuple[pd.DataFrame, str]:
    """
    Fetch all market data in bulk (single API call).

    get_market_cap returns: 종가, 시가총액, 거래량, 거래대금, 상장주식수

    Returns:
        Tuple of (market_df, trading_date) for all stocks.
    """
    # Find the most recent trading day with actual data (not weekend/holiday)
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        market_df = pykrx.get_market_cap(day)
        # Check if data has actual values (not all zeros)
        if not market_df.empty and market_df["시가총액"].sum() > 0:
            target_date = day
            break
    else:
        return pd.DataFrame(), ""

    print(f"Fetched bulk market data for {len(market_df)} stocks (date: {target_date})")
    return market_df, target_date


def get_single_yfinance_metrics(
    yf_ticker: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> dict | None:
    """
    Fetch yfinance metrics for a single ticker with exponential backoff.

    Args:
        yf_ticker: Yahoo Finance ticker (e.g., "005930.KS")
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
    """
    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(yf_ticker)
            info = stock.info
            if info and info.get("regularMarketPrice") is not None:
                eps = info.get("trailingEps")
                bvps = info.get("bookValue")
                return {
                    "gross_margin": info.get("grossMargins"),
                    "ev_ebitda": info.get("enterpriseToEbitda"),
                    "dividend_yield": info.get("dividendYield"),
                    "forward_pe": info.get("forwardPE"),
                    "beta": info.get("beta"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "trailing_pe": info.get("trailingPE"),
                    "price_to_book": info.get("priceToBook"),
                    "eps": eps,
                    "book_value_per_share": bvps,
                    "graham_number": calculate_graham_number(eps, bvps),
                }
            # No valid data, but not an error - don't retry
            return None
        except Exception:
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
                time.sleep(delay)
            # Last attempt failed
    return None


def get_yfinance_metrics_batch(
    tickers: list[str],
    markets: dict[str, str],
    batch_size: int = 30,
    with_fallback: bool = True,
    delay: float = 0.3,
) -> dict[str, dict]:
    """
    Fetch yfinance metrics for multiple tickers in batches.

    Args:
        tickers: List of KRX tickers (e.g., ["005930", "000660"])
        markets: Dict mapping ticker to market ("KOSPI" or "KOSDAQ")
        batch_size: Number of tickers per batch
        with_fallback: If True, retry failed tickers individually
        delay: Delay between individual fallback calls

    Returns:
        Dict mapping ticker to metrics dict.
    """
    results: dict[str, dict] = {}
    failed_tickers: list[tuple[str, str]] = []  # (yf_ticker, krx_ticker)

    # Convert to yfinance format
    yf_tickers = []
    ticker_map = {}  # yf_ticker -> krx_ticker
    for ticker in tickers:
        market = markets.get(ticker, "KOSPI")
        suffix = ".KS" if market == "KOSPI" else ".KQ"
        yf_ticker = f"{ticker}{suffix}"
        yf_tickers.append(yf_ticker)
        ticker_map[yf_ticker] = ticker

    # Process in batches
    for i in range(0, len(yf_tickers), batch_size):
        batch = yf_tickers[i : i + batch_size]
        try:
            # Use yf.Tickers for batch processing
            tickers_obj = yf.Tickers(" ".join(batch))

            for yf_ticker in batch:
                try:
                    info = tickers_obj.tickers[yf_ticker].info
                    if info and info.get("regularMarketPrice") is not None:
                        krx_ticker = ticker_map[yf_ticker]
                        eps = info.get("trailingEps")
                        bvps = info.get("bookValue")
                        results[krx_ticker] = {
                            "gross_margin": info.get("grossMargins"),
                            "ev_ebitda": info.get("enterpriseToEbitda"),
                            "dividend_yield": info.get("dividendYield"),
                            "forward_pe": info.get("forwardPE"),
                            "beta": info.get("beta"),
                            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                            "trailing_pe": info.get("trailingPE"),
                            "price_to_book": info.get("priceToBook"),
                            "eps": eps,
                            "book_value_per_share": bvps,
                            "graham_number": calculate_graham_number(eps, bvps),
                        }
                    else:
                        failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))
                except Exception:
                    failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))
        except Exception as e:
            print(f"Batch error: {e}")
            for yf_ticker in batch:
                failed_tickers.append((yf_ticker, ticker_map[yf_ticker]))

    # Fallback: retry failed tickers individually with exponential backoff
    if with_fallback and failed_tickers:
        print(f"  Retrying {len(failed_tickers)} failed tickers individually...")
        consecutive_failures = 0
        base_delay = 0.5

        for yf_ticker, krx_ticker in tqdm(
            failed_tickers, desc="  Fallback", leave=False
        ):
            data = get_single_yfinance_metrics(yf_ticker)
            if data:
                results[krx_ticker] = data
                consecutive_failures = 0  # Reset on success
            else:
                consecutive_failures += 1

            # Adaptive delay: increase if seeing consecutive failures
            if consecutive_failures >= 3:
                current_delay = min(
                    base_delay * (2 ** (consecutive_failures - 2)), 30.0
                )
                current_delay += random.uniform(0, 1)  # Jitter
            else:
                current_delay = base_delay

            time.sleep(current_delay)

    return results


def get_index_constituents() -> dict[str, set[str]]:
    """
    Get constituents of major Korean indices using pykrx.

    Returns:
        Dictionary mapping index name to set of tickers.
        Includes: KOSPI200, KOSDAQ150
    """
    today = datetime.now().strftime("%Y%m%d")
    indices: dict[str, set[str]] = {}

    try:
        # KOSPI200 (코스피200)
        kospi200 = pykrx.get_index_portfolio_deposit_file("1028", today)
        if kospi200 is not None and len(kospi200) > 0:
            indices["KOSPI200"] = set(kospi200)
            print(f"Fetched {len(indices['KOSPI200'])} KOSPI200 constituents")
    except Exception as e:
        print(f"Warning: Could not fetch KOSPI200: {e}")

    try:
        # KOSDAQ150 (코스닥150)
        kosdaq150 = pykrx.get_index_portfolio_deposit_file("2203", today)
        if kosdaq150 is not None and len(kosdaq150) > 0:
            indices["KOSDAQ150"] = set(kosdaq150)
            print(f"Fetched {len(indices['KOSDAQ150'])} KOSDAQ150 constituents")
    except Exception as e:
        print(f"Warning: Could not fetch KOSDAQ150: {e}")

    return indices


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
    try:
        market_cap = None
        volume = None

        # Try recent days to find market cap (handles weekends/holidays)
        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            df = pykrx.get_market_cap(day)

            if not df.empty and ticker in df.index:
                cap = df.loc[ticker, "시가총액"]
                vol = df.loc[ticker, "거래량"]
                if cap > 0:
                    market_cap = int(cap)
                    volume = int(vol) if vol > 0 else None
                    break

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


def get_yfinance_metrics(ticker: str, market: str) -> dict | None:
    """
    Get additional metrics from yfinance for Korean stocks.

    Args:
        ticker: KRX ticker (e.g., "005930")
        market: "KOSPI" or "KOSDAQ"

    Returns:
        Dictionary with yfinance metrics, or None if failed.
    """
    try:
        # Convert to yfinance format: 005930 -> 005930.KS (KOSPI) or .KQ (KOSDAQ)
        suffix = ".KS" if market == "KOSPI" else ".KQ"
        yf_ticker = f"{ticker}{suffix}"

        stock = yf.Ticker(yf_ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return None

        eps = info.get("trailingEps")
        bvps = info.get("bookValue")
        return {
            "gross_margin": info.get("grossMargins"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "dividend_yield": info.get("dividendYield"),
            "forward_pe": info.get("forwardPE"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "trailing_pe": info.get("trailingPE"),
            "price_to_book": info.get("priceToBook"),
            "eps": eps,
            "book_value_per_share": bvps,
            "graham_number": calculate_graham_number(eps, bvps),
        }
    except Exception as e:
        print(f"Error fetching yfinance metrics for {ticker}: {e}")
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
            "gross_profit": get_amount(["매출총이익", "매출 총이익"]),
            "operating_income": get_amount(["영업이익", "영업손익"]),
            "net_income": get_amount(["당기순이익", "분기순이익", "반기순이익"]),
            "total_assets": get_amount(["자산총계", "자산 총계"]),
            "current_assets": get_amount(["유동자산", "유동 자산"]),
            "total_liabilities": get_amount(["부채총계", "부채 총계"]),
            "current_liabilities": get_amount(["유동부채", "유동 부채"]),
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
        gross_profit = financials.get("gross_profit")
        net_income = financials.get("net_income")
        total_equity = financials.get("total_equity")
        total_assets = financials.get("total_assets")
        current_assets = financials.get("current_assets")
        total_liabilities = financials.get("total_liabilities")
        current_liabilities = financials.get("current_liabilities")

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

        # Gross Margin
        if revenue and revenue > 0 and gross_profit:
            metrics["gross_margin"] = gross_profit / revenue

        # Current Ratio
        if current_liabilities and current_liabilities > 0 and current_assets:
            metrics["current_ratio"] = current_assets / current_liabilities

        return metrics if metrics else None
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None


def upsert_company(
    client: Client, stock_info: dict, corp_code: str | None
) -> str | None:
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
            "eps": metrics.get("eps"),
            "book_value_per_share": metrics.get("book_value_per_share"),
            "graham_number": metrics.get("graham_number"),
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


def save_to_csv(
    companies: list[dict],
    metrics: list[dict],
    prices: list[dict],
    is_test: bool = False,
) -> None:
    """Save collected data to CSV files for local storage."""
    today = date.today().strftime("%Y%m%d")
    suffix = "_test" if is_test else ""

    # Ensure directories exist
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    FINANCIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Save companies (append to existing or create new)
    if companies:
        companies_df = pd.DataFrame(companies)
        companies_file = DATA_DIR / f"kr_companies{suffix}.csv"
        if not is_test and companies_file.exists():
            existing = pd.read_csv(companies_file)
            combined = pd.concat([existing, companies_df]).drop_duplicates(
                subset=["ticker"], keep="last"
            )
            combined.to_csv(companies_file, index=False)
        else:
            companies_df.to_csv(companies_file, index=False)
        print(f"Saved {len(companies)} companies to {companies_file}")

    # Save metrics with date
    if metrics:
        metrics_df = pd.DataFrame(metrics)
        metrics_file = FINANCIALS_DIR / f"kr_metrics_{today}{suffix}.csv"
        metrics_df.to_csv(metrics_file, index=False)
        print(f"Saved {len(metrics)} metrics to {metrics_file}")

    # Save prices with date
    if prices:
        prices_df = pd.DataFrame(prices)
        prices_file = PRICES_DIR / f"kr_prices_{today}{suffix}.csv"
        prices_df.to_csv(prices_file, index=False)
        print(f"Saved {len(prices)} prices to {prices_file}")


def _process_dart_ticker(
    dart: "OpenDartReaderType",
    ticker: str,
    fiscal_year: int,
    market_cap: int | None,
    price: dict | None,
) -> tuple[str, dict | None, dict | None]:
    """Process a single ticker's DART data (for parallel execution)."""
    corp_code = get_corp_code(dart, ticker)
    if not corp_code:
        return ticker, None, None

    financials = get_financial_statements(dart, corp_code, fiscal_year)
    if not financials:
        return ticker, None, None

    # Build stock_info for metrics calculation
    stock_info = {"market_cap": market_cap}
    metrics = calculate_metrics(financials, stock_info, price)

    return ticker, financials, metrics


def collect_and_save(
    market: str = "ALL",
    tickers: list[str] | None = None,
    delay: float = 0.1,
    fiscal_year: int | None = None,
    limit: int | None = None,
    save_csv: bool = True,
    save_db: bool = True,
    max_workers: int = 4,
    is_test: bool = False,
) -> dict:
    """
    Collect Korean stock data and save to Supabase and/or CSV.

    Optimized version with:
    - Bulk pykrx data fetching (single API call for all stocks)
    - Batch yfinance calls (50 tickers at a time)
    - Parallel DART processing with ThreadPoolExecutor

    Args:
        market: "KOSPI", "KOSDAQ", or "ALL" for both.
        tickers: List of specific tickers to collect. If None, collects all.
        delay: Delay between API calls in seconds (reduced due to batching).
        fiscal_year: Year for financial statements. Defaults to last year.
        limit: Maximum number of stocks to process (for testing).
        save_csv: Whether to save data to CSV files.
        save_db: Whether to save data to Supabase.
        max_workers: Number of parallel workers for DART processing.

    Returns:
        Dictionary with success/failure counts.
    """
    client = None
    if save_db:
        client = get_supabase_client()

    dart = get_dart_reader()

    if fiscal_year is None:
        fiscal_year = datetime.now().year - 1

    # === PHASE 1: Fetch bulk data ===
    print("Phase 1: Fetching bulk market data...")
    market_df, bulk_date = get_market_data_bulk()

    if market_df.empty:
        print("Error: Could not fetch market data")
        return {"success": 0, "failed": 0, "skipped": 0}

    # Format trading date
    trading_date = (
        f"{bulk_date[:4]}-{bulk_date[4:6]}-{bulk_date[6:8]}"
        if bulk_date
        else date.today().isoformat()
    )

    # Fetch index constituents
    print("Fetching index constituents...")
    index_members = get_index_constituents()

    # Get tickers
    print(f"Fetching {market} tickers...")
    df = get_krx_tickers(market)

    if tickers:
        df = df[df["ticker"].isin(tickers)]

    if limit:
        df = df.head(limit)

    print(f"Found {len(df)} tickers")

    # Build ticker -> market mapping
    ticker_markets = dict(zip(df["ticker"], df["market"], strict=True))
    ticker_names = dict(zip(df["ticker"], df["name"], strict=True))
    all_tickers = df["ticker"].tolist()

    # === PHASE 2: Batch yfinance metrics ===
    print("\nPhase 2: Fetching yfinance metrics in batches...")
    yf_metrics_all = get_yfinance_metrics_batch(
        all_tickers, ticker_markets, batch_size=30, with_fallback=True, delay=0.3
    )
    print(f"Fetched yfinance metrics for {len(yf_metrics_all)} stocks")

    # === PHASE 3: Process DART data in parallel ===
    print(f"\nPhase 3: Processing DART data with {max_workers} workers...")
    dart_results: dict[str, tuple[dict | None, dict | None]] = {}

    if dart:
        # Prepare data for parallel processing
        tasks = []
        for ticker in all_tickers:
            market_cap = None
            close_price = None
            if ticker in market_df.index:
                market_cap = int(market_df.loc[ticker, "시가총액"])
                close_price = int(market_df.loc[ticker, "종가"])

            price = (
                {"date": trading_date, "close": close_price} if close_price else None
            )
            tasks.append((ticker, market_cap, price))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _process_dart_ticker, dart, ticker, fiscal_year, market_cap, price
                ): ticker
                for ticker, market_cap, price in tasks
            }

            for future in tqdm(
                as_completed(futures), total=len(futures), desc="DART processing"
            ):
                try:
                    ticker, financials, metrics = future.result()
                    dart_results[ticker] = (financials, metrics)
                except Exception as e:
                    ticker = futures[future]
                    print(f"Error processing {ticker}: {e}")
                    dart_results[ticker] = (None, None)
                time.sleep(delay)  # Small delay to avoid rate limiting

    # === PHASE 4: Combine all data ===
    print("\nPhase 4: Combining data and saving...")
    stats = {"success": 0, "failed": 0, "skipped": 0}

    all_companies: list[dict] = []
    all_metrics: list[dict] = []
    all_prices: list[dict] = []

    for ticker in tqdm(all_tickers, desc="Combining data"):
        try:
            name = ticker_names.get(ticker, "")
            mkt = ticker_markets.get(ticker, "KOSPI")

            # Get market cap, volume, and close price from bulk data
            market_cap = None
            volume = None
            close_price = None
            if ticker in market_df.index:
                row = market_df.loc[ticker]
                market_cap = int(row["시가총액"])
                volume = int(row["거래량"])
                close_price = int(row["종가"])

            # Build price data (only close available from bulk, no OHLC)
            price_data = None
            if close_price:
                price_data = {
                    "date": trading_date,
                    "open": None,  # Not available in bulk
                    "high": None,
                    "low": None,
                    "close": close_price,
                    "volume": volume,
                }

            # Get DART metrics
            financials, dart_metrics = dart_results.get(ticker, (None, None))

            # Get yfinance metrics
            yf_metrics = yf_metrics_all.get(ticker, {})

            # Save to database
            if save_db and client:
                stock_info = {
                    "ticker": ticker,
                    "name": name,
                    "market": mkt,
                    "market_cap": market_cap,
                    "volume": volume,
                    "currency": "KRW",
                }
                corp_code = get_corp_code(dart, ticker) if dart else None
                company_id = upsert_company(client, stock_info, corp_code)
                if company_id:
                    if price_data:
                        upsert_price(client, company_id, price_data, market_cap)
                    if financials:
                        upsert_financials(client, company_id, financials, fiscal_year)
                    if dart_metrics:
                        upsert_metrics(client, company_id, dart_metrics)

            # Collect for CSV
            if save_csv:
                # Company data
                indices = []
                if ticker in index_members.get("KOSPI200", set()):
                    indices.append("KOSPI200")
                if ticker in index_members.get("KOSDAQ150", set()):
                    indices.append("KOSDAQ150")

                all_companies.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "market": mkt,
                        "currency": "KRW",
                        "market_cap": market_cap,
                        "indices": ",".join(indices) if indices else None,
                    }
                )

                # Price data
                if price_data:
                    all_prices.append(
                        {
                            "ticker": ticker,
                            **price_data,
                            "market_cap": market_cap,
                        }
                    )

                # Metrics data (combine DART + yfinance)
                metrics_data = {
                    "ticker": ticker,
                    "date": trading_date,
                    "market": mkt,
                }
                if dart_metrics:
                    metrics_data.update(dart_metrics)
                if yf_metrics:
                    for key, value in yf_metrics.items():
                        if value is not None:
                            metrics_data[key] = value
                all_metrics.append(metrics_data)

            stats["success"] += 1

        except Exception as e:
            print(f"Error combining {ticker}: {e}")
            stats["failed"] += 1

    # Save to CSV
    if save_csv:
        save_to_csv(all_companies, all_metrics, all_prices, is_test=is_test)

    print(f"\nCollection complete: {stats}")
    return stats


def dry_run_test(tickers: list[str] | None = None) -> None:
    """Test data collection without saving to database (no DART API needed)."""
    if tickers is None:
        tickers = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오

    print(f"Dry run test with {len(tickers)} tickers (pykrx only)...\n")

    # Get ticker names
    for ticker in tickers:
        print(f"=== {ticker} ===")

        try:
            name = pykrx.get_market_ticker_name(ticker)
            print(f"Name: {name}")

            # Determine market
            today = datetime.now().strftime("%Y%m%d")
            kospi_list = pykrx.get_market_ticker_list(today, market="KOSPI")
            market = "KOSPI" if ticker in kospi_list else "KOSDAQ"
            print(f"Market: {market}")

            # Get stock info
            stock_info = get_stock_info(ticker, name, market)
            if stock_info.get("market_cap"):
                print(f"Market Cap: {stock_info['market_cap']:,} KRW")

            # Get price
            price = get_stock_price(ticker)
            if price:
                print(f"Date: {price['date']}")
                print(
                    f"Close: {price['close']:,} KRW"
                    if price.get("close")
                    else "Close: N/A"
                )
                print(
                    f"Volume: {price['volume']:,}"
                    if price.get("volume")
                    else "Volume: N/A"
                )

        except Exception as e:
            print(f"Error: {e}")

        print()


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    csv_only = "--csv-only" in args

    if "--dry-run" in args:
        # Dry run: test data collection without database
        dry_run_test()
    elif "--test" in args:
        # Test mode: only a few tickers
        test_tickers = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오
        print(f"Running in test mode (csv_only={csv_only})...")
        collect_and_save(
            tickers=test_tickers,
            delay=0.2,
            save_csv=True,
            save_db=not csv_only,
            is_test=True,
        )
    elif "--kospi" in args:
        print(f"Running KOSPI collection (csv_only={csv_only})...")
        collect_and_save(market="KOSPI", save_csv=True, save_db=not csv_only)
    elif "--kosdaq" in args:
        print(f"Running KOSDAQ collection (csv_only={csv_only})...")
        collect_and_save(market="KOSDAQ", save_csv=True, save_db=not csv_only)
    elif csv_only:
        # CSV only: save to files without database
        print("Running full KRX collection (CSV only)...")
        collect_and_save(save_csv=True, save_db=False)
    else:
        # Full collection: both database and CSV
        print("Running full KRX (KOSPI + KOSDAQ) collection...")
        collect_and_save(save_csv=True, save_db=True)
