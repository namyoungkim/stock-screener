"""
US Stock Data Collector

Collects financial data for US stocks using yfinance and FMP.
"""

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()


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

        # Basic metrics
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


if __name__ == "__main__":
    # Test with a few tickers
    test_tickers = ["AAPL", "MSFT", "GOOGL"]

    for ticker in test_tickers:
        print(f"\n--- {ticker} ---")
        info = get_stock_info(ticker)
        print(f"Info: {info}")

        financials = get_financials(ticker)
        print(f"Financials: {financials}")
