"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
"""

import os
import time
from datetime import date

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from supabase import Client, create_client
from tqdm import tqdm

load_dotenv()


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
    batch_size: int = 50,
) -> dict:
    """
    Collect US stock data and save to Supabase.

    Args:
        tickers: List of tickers to collect. If None, collects all S&P 500.
        delay: Delay between API calls in seconds.
        batch_size: Number of stocks to process before printing progress.

    Returns:
        Dictionary with success/failure counts.
    """
    client = get_supabase_client()

    if tickers is None:
        print("Fetching S&P 500 tickers...")
        tickers = get_sp500_tickers()
        print(f"Found {len(tickers)} tickers")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    for ticker in tqdm(tickers, desc="Collecting US stocks"):
        try:
            # Get stock info
            stock_info = get_stock_info(ticker)
            if not stock_info or not stock_info.get("name"):
                stats["skipped"] += 1
                continue

            # Upsert company
            company_id = upsert_company(client, stock_info)
            if not company_id:
                stats["failed"] += 1
                continue

            # Get and save financials
            financials = get_financials(ticker)
            if financials:
                upsert_metrics(client, company_id, financials)

            # Save price data
            upsert_price(client, company_id, stock_info)

            stats["success"] += 1

            # Rate limiting
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
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        print("Running in test mode...")
        collect_and_save(tickers=test_tickers, delay=0.2)
    else:
        # Full collection
        print("Running full S&P 500 collection...")
        collect_and_save()
