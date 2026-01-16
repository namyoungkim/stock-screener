"""Pure constants for data pipeline. No side effects at import time."""

from pathlib import Path

# === Directories ===
# Use absolute path relative to project root (parent of data-pipeline/)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _PROJECT_ROOT / "data"
COMPANIES_DIR = DATA_DIR / "companies"

# === Batch Sizes ===
# Reduced batch size to avoid Yahoo Finance rate limiting
DEFAULT_BATCH_SIZE = 10  # For metrics/info fetching (reduced from 20)
DEFAULT_HISTORY_BATCH_SIZE = 100  # For bulk history download (reduced from 500)
DEFAULT_PRICES_BATCH_SIZE = 50  # For price fetching (reduced from 100)

# === Concurrency ===
DEFAULT_MAX_WORKERS = 4  # ThreadPoolExecutor workers (reduced from 6)

# === Delays (seconds) ===
# Increased delays to avoid Yahoo Finance rate limiting
DEFAULT_BASE_DELAY = 3.0  # Base delay between batches (increased from 1.5)
DEFAULT_JITTER = 1.5  # Random jitter range (increased from 0.5)
HISTORY_RETRY_WAIT = 120  # Wait time for history retry (yfinance is lenient)
METRICS_RETRY_WAIT = 600  # Wait time for metrics retry (yfinance .info is strict)

# === Timeouts (seconds) ===
DEFAULT_REQUEST_TIMEOUT = 30
FDR_REQUEST_TIMEOUT = 10  # 10 seconds for history data (300 days needs more time)
KIS_REQUEST_TIMEOUT = 10

# === Rate Limit ===
MAX_RETRIES = 10  # Maximum retry rounds
MAX_CONSECUTIVE_FAILURES = 10  # Stop after this many consecutive failures
MAX_BACKOFFS = 5  # Maximum backoff attempts before giving up

# === History ===
DEFAULT_HISTORY_DAYS = 300  # ~10 months of history for technical indicators
HISTORY_PERIOD = "10mo"  # yfinance period string

# === Quality Check ===
MIN_COVERAGE_THRESHOLD = 0.95  # 95% coverage required

# === US Major Tickers (must not be missing) ===
US_MAJOR_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "BRK-B",
    "JPM",
    "JNJ",
    "V",
    "UNH",
    "XOM",
    "WMT",
    "PG",
]

# === KR Major Tickers (must not be missing) ===
KR_MAJOR_TICKERS = [
    "005930",  # Samsung
    "000660",  # SK Hynix
    "373220",  # LG Energy
    "207940",  # Samsung Biologics
    "005380",  # Hyundai Motor
    "006400",  # Samsung SDI
    "051910",  # LG Chem
    "035420",  # Naver
    "000270",  # Kia
    "035720",  # Kakao
]

# === Key Metrics for Quality Check ===
KEY_METRICS = [
    "pe_ratio",
    "pb_ratio",
    "roe",
    "roa",
    "dividend_yield",
    "market_cap",
    "rsi",
    "macd",
    "bb_percent",
    "volume_change",
    "graham_number",
]
