"""
Korean Stock Data Collector

Collects financial data for Korean stocks using pykrx and OpenDartReader,
and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.
"""

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import OpenDartReader  # type: ignore[import-untyped]
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from pykrx import stock as pykrx  # type: ignore[import-untyped]
from supabase import Client, create_client
from tqdm import tqdm

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


def save_to_csv(
    companies: list[dict],
    metrics: list[dict],
    prices: list[dict],
) -> None:
    """Save collected data to CSV files for local storage."""
    today = date.today().strftime("%Y%m%d")

    # Ensure directories exist
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    FINANCIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Save companies (append to existing or create new)
    if companies:
        companies_df = pd.DataFrame(companies)
        companies_file = DATA_DIR / "kr_companies.csv"
        if companies_file.exists():
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
        metrics_file = FINANCIALS_DIR / f"kr_metrics_{today}.csv"
        metrics_df.to_csv(metrics_file, index=False)
        print(f"Saved {len(metrics)} metrics to {metrics_file}")

    # Save prices with date
    if prices:
        prices_df = pd.DataFrame(prices)
        prices_file = PRICES_DIR / f"kr_prices_{today}.csv"
        prices_df.to_csv(prices_file, index=False)
        print(f"Saved {len(prices)} prices to {prices_file}")


def collect_and_save(
    market: str = "ALL",
    tickers: list[str] | None = None,
    delay: float = 0.3,
    fiscal_year: int | None = None,
    limit: int | None = None,
    save_csv: bool = True,
    save_db: bool = True,
) -> dict:
    """
    Collect Korean stock data and save to Supabase and/or CSV.

    Args:
        market: "KOSPI", "KOSDAQ", or "ALL" for both.
        tickers: List of specific tickers to collect. If None, collects all.
        delay: Delay between API calls in seconds.
        fiscal_year: Year for financial statements. Defaults to last year.
        limit: Maximum number of stocks to process (for testing).
        save_csv: Whether to save data to CSV files.
        save_db: Whether to save data to Supabase.

    Returns:
        Dictionary with success/failure counts.
    """
    client = None
    if save_db:
        client = get_supabase_client()

    dart = get_dart_reader()

    if fiscal_year is None:
        fiscal_year = datetime.now().year - 1

    # Fetch index constituents for membership tracking
    print("Fetching index constituents...")
    index_members = get_index_constituents()

    print(f"Fetching {market} tickers...")
    df = get_krx_tickers(market)

    if tickers:
        df = df[df["ticker"].isin(tickers)]

    if limit:
        df = df.head(limit)

    print(f"Found {len(df)} tickers")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    # Lists for CSV export
    all_companies: list[dict] = []
    all_metrics: list[dict] = []
    all_prices: list[dict] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Collecting KR stocks"):
        ticker = row["ticker"]
        name = row["name"]
        mkt = row["market"]

        try:
            # Get stock info
            stock_info = get_stock_info(ticker, name, mkt)

            # Get corp_code for DART (only if dart is available)
            corp_code = get_corp_code(dart, ticker) if dart else None

            company_id = None

            # Save to database
            if save_db and client:
                company_id = upsert_company(client, stock_info, corp_code)
                if not company_id:
                    stats["failed"] += 1
                    continue

            # Collect for CSV (with index membership)
            if save_csv:
                # Determine index membership
                indices = []
                if ticker in index_members.get("KOSPI200", set()):
                    indices.append("KOSPI200")
                if ticker in index_members.get("KOSDAQ150", set()):
                    indices.append("KOSDAQ150")

                all_companies.append({
                    "ticker": stock_info["ticker"],
                    "name": stock_info.get("name"),
                    "market": mkt,
                    "currency": "KRW",
                    "market_cap": stock_info.get("market_cap"),
                    "indices": ",".join(indices) if indices else None,
                })

            # Get price
            price = get_stock_price(ticker)
            if price:
                if save_db and client and company_id:
                    upsert_price(client, company_id, price, stock_info.get("market_cap"))
                if save_csv:
                    all_prices.append({
                        "ticker": ticker,
                        "date": price["date"],
                        "open": price.get("open"),
                        "high": price.get("high"),
                        "low": price.get("low"),
                        "close": price.get("close"),
                        "volume": price.get("volume"),
                        "market_cap": stock_info.get("market_cap"),
                    })

            # Get financial statements if corp_code exists and dart is available
            metrics = None
            if dart and corp_code:
                financials = get_financial_statements(dart, corp_code, fiscal_year)

                if financials:
                    if save_db and client and company_id:
                        upsert_financials(client, company_id, financials, fiscal_year)

                    # Calculate metrics
                    metrics = calculate_metrics(financials, stock_info, price)
                    if metrics:
                        if save_db and client and company_id:
                            upsert_metrics(client, company_id, metrics)

            # Get additional metrics from yfinance
            yf_metrics = get_yfinance_metrics(ticker, mkt)

            # Save metrics to CSV (even without DART data, save basic info)
            # Use trading date from price data for consistency
            if save_csv:
                trading_date = price["date"] if price else date.today().isoformat()
                metrics_data = {
                    "ticker": ticker,
                    "date": trading_date,
                    "market": mkt,
                }
                # Add DART-calculated metrics
                if metrics:
                    metrics_data.update(metrics)
                # Add/override with yfinance metrics (yfinance values take precedence)
                if yf_metrics:
                    # Only override if yfinance has actual values
                    for key, value in yf_metrics.items():
                        if value is not None:
                            metrics_data[key] = value
                all_metrics.append(metrics_data)

            stats["success"] += 1
            time.sleep(delay)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            stats["failed"] += 1

    # Save to CSV
    if save_csv:
        save_to_csv(all_companies, all_metrics, all_prices)

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
                print(f"Close: {price['close']:,} KRW" if price.get('close') else "Close: N/A")
                print(f"Volume: {price['volume']:,}" if price.get('volume') else "Volume: N/A")

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
