"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.
"""

import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from supabase import Client, create_client
from tqdm import tqdm

load_dotenv()

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


def get_sp500_tickers() -> list[str]:
    """Get S&P 500 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    return df["Symbol"].str.replace(".", "-").tolist()


def get_stock_info(ticker: str) -> dict | None:
    """Get stock info using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


def get_financials(ticker: str) -> dict | None:
    """Get financial data using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "gross_margin": info.get("grossMargins"),
            "net_margin": info.get("profitMargins"),
            "fcf": info.get("freeCashflow"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception as e:
        print(f"Error fetching financials for {ticker}: {e}")
        return None


def upsert_company(client: Client, stock_info: dict) -> str | None:
    """Insert or update company in Supabase, return company ID."""
    try:
        data = {
            "ticker": stock_info["ticker"],
            "name": stock_info["name"],
            "market": "US",
            "sector": stock_info.get("sector"),
            "industry": stock_info.get("industry"),
            "currency": stock_info.get("currency", "USD"),
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


def upsert_metrics(client: Client, company_id: str, financials: dict) -> bool:
    """Insert or update metrics in Supabase."""
    try:
        today = date.today().isoformat()

        data = {
            "company_id": company_id,
            "date": today,
            "pe_ratio": financials.get("pe_ratio"),
            "pb_ratio": financials.get("pb_ratio"),
            "ps_ratio": financials.get("ps_ratio"),
            "ev_ebitda": financials.get("ev_ebitda"),
            "roe": financials.get("roe"),
            "roa": financials.get("roa"),
            "debt_equity": financials.get("debt_equity"),
            "current_ratio": financials.get("current_ratio"),
            "gross_margin": financials.get("gross_margin"),
            "net_margin": financials.get("net_margin"),
            "dividend_yield": financials.get("dividend_yield"),
            "data_source": "yfinance",
        }

        client.table("metrics").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting metrics for company {company_id}: {e}")
        return False


def upsert_price(client: Client, company_id: str, stock_info: dict) -> bool:
    """Insert or update price/market_cap in Supabase."""
    try:
        today = date.today().isoformat()

        # Get current price
        stock = yf.Ticker(stock_info["ticker"])
        hist = stock.history(period="1d")

        if hist.empty:
            return False

        latest = hist.iloc[-1]

        data = {
            "company_id": company_id,
            "date": today,
            "open": float(latest["Open"]) if pd.notna(latest["Open"]) else None,
            "high": float(latest["High"]) if pd.notna(latest["High"]) else None,
            "low": float(latest["Low"]) if pd.notna(latest["Low"]) else None,
            "close": float(latest["Close"]) if pd.notna(latest["Close"]) else None,
            "volume": int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,
            "market_cap": stock_info.get("market_cap"),
        }

        client.table("prices").upsert(data, on_conflict="company_id,date").execute()
        return True
    except Exception as e:
        print(f"Error upserting price for company {company_id}: {e}")
        return False


def collect_and_save(
    tickers: list[str] | None = None,
    delay: float = 0.5,
    save_csv: bool = True,
    save_db: bool = True,
) -> dict:
    """
    Collect US stock data and save to Supabase and/or CSV.

    Args:
        tickers: List of tickers to collect. If None, collects all S&P 500.
        delay: Delay between API calls in seconds.
        save_csv: Whether to save data to CSV files.
        save_db: Whether to save data to Supabase.

    Returns:
        Dictionary with success/failure counts.
    """
    client = None
    if save_db:
        client = get_supabase_client()

    if tickers is None:
        print("Fetching S&P 500 tickers...")
        tickers = get_sp500_tickers()
        print(f"Found {len(tickers)} tickers")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    # Lists for CSV export
    all_companies: list[dict] = []
    all_metrics: list[dict] = []
    all_prices: list[dict] = []

    for ticker in tqdm(tickers, desc="Collecting US stocks"):
        try:
            # Get stock info
            stock_info = get_stock_info(ticker)
            if not stock_info or not stock_info.get("name"):
                stats["skipped"] += 1
                continue

            company_id = None

            # Save to database
            if save_db and client:
                company_id = upsert_company(client, stock_info)
                if not company_id:
                    stats["failed"] += 1
                    continue

            # Collect for CSV
            if save_csv:
                all_companies.append({
                    "ticker": stock_info["ticker"],
                    "name": stock_info.get("name"),
                    "market": "US",
                    "sector": stock_info.get("sector"),
                    "industry": stock_info.get("industry"),
                    "currency": stock_info.get("currency", "USD"),
                })

            # Get and save financials
            financials = get_financials(ticker)
            if financials:
                if save_db and client and company_id:
                    upsert_metrics(client, company_id, financials)
                if save_csv:
                    all_metrics.append({
                        "ticker": ticker,
                        "date": date.today().isoformat(),
                        **{k: v for k, v in financials.items() if k != "ticker"},
                    })

            # Get and save price data
            if save_db and client and company_id:
                upsert_price(client, company_id, stock_info)

            if save_csv:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1d")
                    if not hist.empty:
                        latest = hist.iloc[-1]
                        all_prices.append({
                            "ticker": ticker,
                            "date": date.today().isoformat(),
                            "open": float(latest["Open"]) if pd.notna(latest["Open"]) else None,
                            "high": float(latest["High"]) if pd.notna(latest["High"]) else None,
                            "low": float(latest["Low"]) if pd.notna(latest["Low"]) else None,
                            "close": float(latest["Close"]) if pd.notna(latest["Close"]) else None,
                            "volume": int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,
                            "market_cap": stock_info.get("market_cap"),
                        })
                except Exception:
                    pass

            stats["success"] += 1

            # Rate limiting
            time.sleep(delay)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            stats["failed"] += 1

    # Save to CSV
    if save_csv:
        save_to_csv(all_companies, all_metrics, all_prices)

    print(f"\nCollection complete: {stats}")
    return stats


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
        companies_file = DATA_DIR / "us_companies.csv"
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
        metrics_file = FINANCIALS_DIR / f"us_metrics_{today}.csv"
        metrics_df.to_csv(metrics_file, index=False)
        print(f"Saved {len(metrics)} metrics to {metrics_file}")

    # Save prices with date
    if prices:
        prices_df = pd.DataFrame(prices)
        prices_file = PRICES_DIR / f"us_prices_{today}.csv"
        prices_df.to_csv(prices_file, index=False)
        print(f"Saved {len(prices)} prices to {prices_file}")


def dry_run_test(tickers: list[str] | None = None) -> None:
    """Test data collection without saving to database."""
    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOGL"]

    print(f"Dry run test with {len(tickers)} tickers...\n")

    for ticker in tickers:
        print(f"=== {ticker} ===")

        # Get stock info
        stock_info = get_stock_info(ticker)
        if stock_info:
            print(f"Name: {stock_info.get('name')}")
            print(f"Sector: {stock_info.get('sector')}")
            print(f"Industry: {stock_info.get('industry')}")
            print(f"Market Cap: {stock_info.get('market_cap'):,}" if stock_info.get('market_cap') else "Market Cap: N/A")

        # Get financials
        financials = get_financials(ticker)
        if financials:
            print(f"P/E: {financials.get('pe_ratio')}")
            print(f"P/B: {financials.get('pb_ratio')}")
            print(f"ROE: {financials.get('roe')}")
            print(f"Dividend Yield: {financials.get('dividend_yield')}")

        print()


if __name__ == "__main__":
    import sys

    if "--dry-run" in sys.argv:
        # Dry run: test data collection without database
        dry_run_test()
    elif "--test" in sys.argv:
        # Test mode: only a few tickers
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        csv_only = "--csv-only" in sys.argv
        print(f"Running in test mode (csv_only={csv_only})...")
        collect_and_save(
            tickers=test_tickers,
            delay=0.2,
            save_csv=True,
            save_db=not csv_only,
        )
    elif "--csv-only" in sys.argv:
        # CSV only: save to files without database
        print("Running full S&P 500 collection (CSV only)...")
        collect_and_save(save_csv=True, save_db=False)
    else:
        # Full collection: both database and CSV
        print("Running full S&P 500 collection...")
        collect_and_save(save_csv=True, save_db=True)
