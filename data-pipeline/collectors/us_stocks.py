"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and saves to Supabase.
Supports hybrid storage: Supabase for latest data, CSV for history.

Optimized for speed with:
- Batch yfinance calls (50 tickers at a time)
- ThreadPoolExecutor for parallel processing
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _fetch_wiki_tickers(url: str, index_name: str) -> list[str]:
    """Fetch tickers from Wikipedia table."""
    import requests
    from io import StringIO

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers)
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]

    # Column name might be 'Symbol' or 'Ticker'
    col = "Symbol" if "Symbol" in df.columns else "Ticker"
    tickers = df[col].str.replace(".", "-").tolist()
    print(f"Fetched {len(tickers)} {index_name} tickers")
    return tickers


def get_sp500_tickers() -> list[str]:
    """Get S&P 500 tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            "S&P 500",
        )
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        return []


def get_sp400_tickers() -> list[str]:
    """Get S&P 400 Mid Cap tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
            "S&P 400",
        )
    except Exception as e:
        print(f"Error fetching S&P 400: {e}")
        return []


def get_sp600_tickers() -> list[str]:
    """Get S&P 600 Small Cap tickers from Wikipedia."""
    try:
        return _fetch_wiki_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
            "S&P 600",
        )
    except Exception as e:
        print(f"Error fetching S&P 600: {e}")
        return []


def get_russell2000_tickers() -> list[str]:
    """Get Russell 2000 tickers from iShares IWM ETF holdings."""
    try:
        # iShares Russell 2000 ETF holdings
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
        df = pd.read_csv(url, skiprows=9)

        # Filter to stocks only (exclude cash, futures, etc.)
        if "Asset Class" in df.columns:
            df = df[df["Asset Class"] == "Equity"]

        tickers = df["Ticker"].dropna().str.strip().tolist()
        # Clean up tickers
        tickers = [t for t in tickers if t and isinstance(t, str) and len(t) <= 5]
        print(f"Fetched {len(tickers)} Russell 2000 tickers")
        return tickers
    except Exception as e:
        print(f"Error fetching Russell 2000 from iShares: {e}")
        # Fallback: try alternative source
        try:
            # Alternative: use a static list or another source
            print("Trying alternative source for Russell 2000...")
            # For now, return empty - will implement alternative later
            return []
        except Exception:
            return []


def get_all_us_tickers() -> dict[str, list[str]]:
    """
    Get all US tickers with index membership.

    Returns:
        Dictionary mapping ticker to list of indices it belongs to.
        Example: {"AAPL": ["SP500"], "ACAD": ["SP600", "RUSSELL2000"]}
    """
    print("Fetching all US index tickers...")

    # Fetch from all indices
    sp500 = set(get_sp500_tickers())
    sp400 = set(get_sp400_tickers())
    sp600 = set(get_sp600_tickers())
    russell2000 = set(get_russell2000_tickers())

    # Build membership dictionary
    all_tickers: dict[str, list[str]] = {}

    for ticker in sp500:
        all_tickers.setdefault(ticker, []).append("SP500")

    for ticker in sp400:
        all_tickers.setdefault(ticker, []).append("SP400")

    for ticker in sp600:
        all_tickers.setdefault(ticker, []).append("SP600")

    for ticker in russell2000:
        all_tickers.setdefault(ticker, []).append("RUSSELL2000")

    print(f"\nTotal unique tickers: {len(all_tickers)}")
    print(f"  - S&P 500: {len(sp500)}")
    print(f"  - S&P 400: {len(sp400)}")
    print(f"  - S&P 600: {len(sp600)}")
    print(f"  - Russell 2000: {len(russell2000)}")

    return all_tickers


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


def get_stock_data_batch(tickers: list[str], batch_size: int = 50) -> dict[str, dict]:
    """
    Fetch stock info and financials for multiple tickers in batches.

    Args:
        tickers: List of ticker symbols
        batch_size: Number of tickers per batch

    Returns:
        Dict mapping ticker to combined stock info and financials dict.
    """
    results: dict[str, dict] = {}

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            # Use yf.Tickers for batch processing
            tickers_obj = yf.Tickers(" ".join(batch))

            for ticker in batch:
                try:
                    info = tickers_obj.tickers[ticker].info
                    if info and info.get("regularMarketPrice") is not None:
                        results[ticker] = {
                            # Stock info
                            "name": info.get("longName"),
                            "sector": info.get("sector"),
                            "industry": info.get("industry"),
                            "market_cap": info.get("marketCap"),
                            "currency": info.get("currency", "USD"),
                            # Financials
                            "pe_ratio": info.get("trailingPE"),
                            "forward_pe": info.get("forwardPE"),
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
                            "beta": info.get("beta"),
                            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                        }
                except Exception:
                    pass
        except Exception as e:
            print(f"Batch error: {e}")

    return results


def get_prices_batch(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch price data for multiple tickers using yf.download.

    Args:
        tickers: List of ticker symbols

    Returns:
        Dict mapping ticker to price dict.
    """
    results: dict[str, dict] = {}

    try:
        # Download all prices at once
        df = yf.download(tickers, period="1d", group_by="ticker", progress=False)

        if df.empty:
            return results

        today = date.today().isoformat()

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    # Single ticker: no multi-level columns
                    row = df.iloc[-1]
                else:
                    # Multiple tickers: access by ticker name
                    if ticker not in df.columns.get_level_values(0):
                        continue
                    row = df[ticker].iloc[-1]

                if pd.notna(row.get("Close")):
                    results[ticker] = {
                        "date": today,
                        "open": float(row["Open"]) if pd.notna(row.get("Open")) else None,
                        "high": float(row["High"]) if pd.notna(row.get("High")) else None,
                        "low": float(row["Low"]) if pd.notna(row.get("Low")) else None,
                        "close": float(row["Close"]) if pd.notna(row.get("Close")) else None,
                        "volume": int(row["Volume"]) if pd.notna(row.get("Volume")) else None,
                    }
            except Exception:
                pass

    except Exception as e:
        print(f"Price batch error: {e}")

    return results


def upsert_company(
    client: Client, stock_info: dict, index_membership: list[str] | None = None
) -> str | None:
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

        # Note: index_membership stored in separate tracking for now
        # Could add a column later if needed

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
    ticker_membership: dict[str, list[str]] | None = None,
    delay: float = 0.1,
    save_csv: bool = True,
    save_db: bool = True,
    universe: str = "sp500",
    batch_size: int = 50,
) -> dict:
    """
    Collect US stock data and save to Supabase and/or CSV.

    Optimized version with:
    - Batch yfinance calls (50 tickers at a time)
    - Bulk price download using yf.download

    Args:
        tickers: List of tickers to collect. If None, uses universe param.
        ticker_membership: Dict mapping ticker to index membership list.
        delay: Delay between batches in seconds (reduced due to batching).
        save_csv: Whether to save data to CSV files.
        save_db: Whether to save data to Supabase.
        universe: Which universe to collect: "sp500", "full" (all indices).
        batch_size: Number of tickers per batch.

    Returns:
        Dictionary with success/failure counts.
    """
    client = None
    if save_db:
        client = get_supabase_client()

    # Determine tickers to collect
    if tickers is None:
        if universe == "full":
            print("Fetching full US universe (S&P 500 + 400 + 600 + Russell 2000)...")
            ticker_membership = get_all_us_tickers()
            tickers = list(ticker_membership.keys())
        else:
            print("Fetching S&P 500 tickers...")
            tickers = get_sp500_tickers()
            ticker_membership = {t: ["SP500"] for t in tickers}

        print(f"Found {len(tickers)} unique tickers")

    if ticker_membership is None:
        ticker_membership = {t: [] for t in tickers}

    # === PHASE 1: Batch fetch stock data ===
    print(f"\nPhase 1: Fetching stock data in batches of {batch_size}...")
    stock_data_all: dict[str, dict] = {}

    for i in tqdm(range(0, len(tickers), batch_size), desc="Fetching stock data"):
        batch = tickers[i:i + batch_size]
        batch_data = get_stock_data_batch(batch, batch_size=len(batch))
        stock_data_all.update(batch_data)
        time.sleep(delay)

    print(f"Fetched data for {len(stock_data_all)} stocks")

    # === PHASE 2: Batch fetch prices ===
    print(f"\nPhase 2: Fetching prices...")
    prices_all = get_prices_batch(tickers)
    print(f"Fetched prices for {len(prices_all)} stocks")

    # === PHASE 3: Combine and save ===
    print(f"\nPhase 3: Combining data and saving...")
    stats = {"success": 0, "failed": 0, "skipped": 0}

    all_companies: list[dict] = []
    all_metrics: list[dict] = []
    all_prices: list[dict] = []

    for ticker in tqdm(tickers, desc="Processing"):
        try:
            data = stock_data_all.get(ticker)
            if not data or not data.get("name"):
                stats["skipped"] += 1
                continue

            membership = ticker_membership.get(ticker, [])
            company_id = None

            # Save to database
            if save_db and client:
                stock_info = {
                    "ticker": ticker,
                    "name": data.get("name"),
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "market_cap": data.get("market_cap"),
                    "currency": data.get("currency", "USD"),
                }
                company_id = upsert_company(client, stock_info, membership)
                if company_id:
                    upsert_metrics(client, company_id, data)
                    if ticker in prices_all:
                        # Need to create price entry with proper structure
                        price_data = prices_all[ticker]
                        upsert_price(client, company_id, {"ticker": ticker, "market_cap": data.get("market_cap")})

            # Collect for CSV
            if save_csv:
                all_companies.append({
                    "ticker": ticker,
                    "name": data.get("name"),
                    "market": "US",
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "currency": data.get("currency", "USD"),
                    "market_cap": data.get("market_cap"),
                    "index_membership": ",".join(membership),
                })

                # Metrics
                all_metrics.append({
                    "ticker": ticker,
                    "date": date.today().isoformat(),
                    "pe_ratio": data.get("pe_ratio"),
                    "forward_pe": data.get("forward_pe"),
                    "pb_ratio": data.get("pb_ratio"),
                    "ps_ratio": data.get("ps_ratio"),
                    "ev_ebitda": data.get("ev_ebitda"),
                    "roe": data.get("roe"),
                    "roa": data.get("roa"),
                    "debt_equity": data.get("debt_equity"),
                    "current_ratio": data.get("current_ratio"),
                    "gross_margin": data.get("gross_margin"),
                    "net_margin": data.get("net_margin"),
                    "dividend_yield": data.get("dividend_yield"),
                    "beta": data.get("beta"),
                    "fifty_two_week_high": data.get("fifty_two_week_high"),
                    "fifty_two_week_low": data.get("fifty_two_week_low"),
                })

                # Prices
                if ticker in prices_all:
                    price = prices_all[ticker]
                    all_prices.append({
                        "ticker": ticker,
                        **price,
                        "market_cap": data.get("market_cap"),
                    })

            stats["success"] += 1

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

    args = sys.argv[1:]
    csv_only = "--csv-only" in args
    full_universe = "--full" in args

    if "--dry-run" in args:
        # Dry run: test data collection without database
        dry_run_test()
    elif "--test" in args:
        # Test mode: only a few tickers
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        print(f"Running in test mode (csv_only={csv_only})...")
        collect_and_save(
            tickers=test_tickers,
            delay=0.2,
            save_csv=True,
            save_db=not csv_only,
        )
    elif "--list-tickers" in args:
        # Just list tickers without collecting
        if full_universe:
            tickers = get_all_us_tickers()
            print(f"\nSample tickers with membership:")
            for i, (t, m) in enumerate(list(tickers.items())[:20]):
                print(f"  {t}: {m}")
        else:
            tickers = get_sp500_tickers()
    elif full_universe:
        # Full universe: S&P 500 + 400 + 600 + Russell 2000
        print("Running FULL US universe collection...")
        print("This will take 3-4 hours. Press Ctrl+C to cancel.\n")
        collect_and_save(
            save_csv=True,
            save_db=not csv_only,
            universe="full",
        )
    elif csv_only:
        # CSV only: save to files without database
        print("Running S&P 500 collection (CSV only)...")
        collect_and_save(save_csv=True, save_db=False, universe="sp500")
    else:
        # S&P 500 only: both database and CSV
        print("Running S&P 500 collection...")
        collect_and_save(save_csv=True, save_db=True, universe="sp500")
