"""Data quality checker for stock collection results.

This module provides quality assessment for collected stock data,
checking universe coverage, missing tickers, and metric completeness.
"""

import functools
import logging
from dataclasses import dataclass, field

import pandas as pd
from common.config import DATA_DIR


# Module-level universe cache (avoid repeated NASDAQ FTP requests)
@functools.lru_cache(maxsize=4)
def _get_cached_universe(market: str) -> tuple[str, ...]:
    """Get cached universe for a market (returns tuple for hashability)."""
    if market.upper() == "US":
        from collectors.us_stocks import get_all_us_tickers

        all_data = get_all_us_tickers()
        return tuple(all_data.keys())
    elif market.upper() == "KR":
        from collectors.kr_stocks import KRCollector

        collector = KRCollector(save_db=False, save_csv=False, quiet=True)
        return tuple(collector.get_tickers())
    else:
        return tuple()

logger = logging.getLogger(__name__)

# Key metrics to check for coverage
KEY_METRICS = [
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "roe",
    "roa",
    "debt_equity",
    "current_ratio",
    "rsi",
    "mfi",
    "macd",
    "bb_percent",
]

# Major tickers by market (top companies by market cap)
# These critical tickers must be collected regardless of universe setting
US_MAJOR_TICKERS = [
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
    "NVDA",   # NVIDIA
    "META",   # Meta
    "TSLA",   # Tesla
    "BRK",    # Berkshire Hathaway (BRK-A or BRK-B)
    "JPM",    # JPMorgan Chase
    "V",      # Visa
    "UNH",    # UnitedHealth
    "XOM",    # Exxon Mobil
    "LLY",    # Eli Lilly
    "MA",     # Mastercard
    "JNJ",    # Johnson & Johnson
]

# KR: Top companies by market cap (code only, without suffix)
KR_MAJOR_TICKERS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "035720",  # 카카오
    "005490",  # POSCO홀딩스
    "028260",  # 삼성물산
    "068270",  # 셀트리온
]

# Minimum coverage threshold for passing quality check
MIN_COVERAGE_THRESHOLD = 0.95  # 95%


@dataclass
class QualityReport:
    """Quality assessment report for collected data."""

    market: str
    universe_count: int
    collected_count: int
    missing_count: int
    missing_tickers: list[str] = field(default_factory=list)
    missing_major: list[str] = field(default_factory=list)
    metric_coverage: dict[str, float] = field(default_factory=dict)
    passed: bool = False

    @property
    def coverage_rate(self) -> float:
        """Calculate overall coverage rate."""
        if self.universe_count == 0:
            return 0.0
        return self.collected_count / self.universe_count


class DataQualityChecker:
    """Checker for data collection quality assessment."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_universe(self, market: str) -> list[str]:
        """Get the full ticker universe for a market.

        Uses module-level cache to avoid repeated NASDAQ FTP requests.

        Args:
            market: Market identifier ("US" or "KR")

        Returns:
            List of all tickers in the universe
        """
        cached = _get_cached_universe(market.upper())
        if not cached and market.upper() not in ("US", "KR"):
            self.logger.warning(f"Unknown market: {market}")
        return list(cached)

    def check(
        self,
        market: str,
        collected_tickers: list[str],
        metrics_df: pd.DataFrame | None = None,
    ) -> QualityReport:
        """Check data quality for collected results.

        Args:
            market: Market identifier ("US" or "KR")
            collected_tickers: List of successfully collected tickers
            metrics_df: DataFrame with collected metrics (optional)

        Returns:
            QualityReport with assessment results
        """
        # Get universe
        universe = self.get_universe(market)
        universe_set = set(universe)
        collected_set = set(collected_tickers)

        # For KR, also check without suffix
        if market.upper() == "KR":
            normalized_collected = set()
            for t in collected_tickers:
                normalized_collected.add(t)
                # Remove .KS or .KQ suffix if present
                if ".KS" in t or ".KQ" in t:
                    normalized_collected.add(t.replace(".KS", "").replace(".KQ", ""))
            collected_set = normalized_collected

        # Find missing tickers
        missing_tickers = []
        for t in universe:
            base = (
                t.replace(".KS", "").replace(".KQ", "") if market.upper() == "KR" else t
            )
            if t not in collected_set and base not in collected_set:
                missing_tickers.append(t)

        # Find missing major tickers
        major_tickers = US_MAJOR_TICKERS if market.upper() == "US" else KR_MAJOR_TICKERS
        missing_major = []
        for t in major_tickers:
            # For KR, major tickers are codes without suffix
            if market.upper() == "KR":
                found = any(t in ct for ct in collected_set)
            else:
                # For US, check exact match or prefix match (e.g., BRK matches BRK-B, BRKA, BRKB)
                found = t in collected_set or any(ct.startswith(t) for ct in collected_set)
            if not found:
                missing_major.append(t)

        # Calculate metric coverage
        metric_coverage = {}
        if metrics_df is not None and len(metrics_df) > 0:
            for metric in KEY_METRICS:
                if metric in metrics_df.columns:
                    non_null = metrics_df[metric].notna().sum()
                    coverage = non_null / len(metrics_df)
                    metric_coverage[metric] = coverage

        # Determine if passed
        coverage_rate = len(collected_set) / len(universe_set) if universe_set else 0
        passed = coverage_rate >= MIN_COVERAGE_THRESHOLD and len(missing_major) == 0

        return QualityReport(
            market=market.upper(),
            universe_count=len(universe_set),
            collected_count=len(collected_set),
            missing_count=len(missing_tickers),
            missing_tickers=missing_tickers,
            missing_major=missing_major,
            metric_coverage=metric_coverage,
            passed=passed,
        )

    def print_report(self, report: QualityReport) -> None:
        """Print quality report to console.

        Args:
            report: QualityReport to print
        """
        coverage_pct = report.coverage_rate * 100

        print()
        print("=" * 60)
        print(f"Data Quality Report: {report.market}")
        print("=" * 60)
        print()
        print("Universe Coverage:")
        print(f"  - Universe:  {report.universe_count:,}")
        print(f"  - Collected: {report.collected_count:,} ({coverage_pct:.1f}%)")
        print(f"  - Missing:   {report.missing_count:,}")

        if report.missing_major:
            print()
            major_label = "US Major" if report.market == "US" else "KOSPI Top"
            print(f"Missing Major Tickers ({major_label}): {len(report.missing_major)}")
            print(f"  {report.missing_major}")
        else:
            major_label = "US Major" if report.market == "US" else "KOSPI Top"
            print()
            print(f"Missing Major Tickers ({major_label}): 0 ✓")

        if report.metric_coverage:
            print()
            print("Metric Coverage:")
            for metric, coverage in sorted(report.metric_coverage.items()):
                count = int(coverage * report.collected_count)
                print(
                    f"  - {metric:20s} {coverage * 100:5.1f}% ({count:,}/{report.collected_count:,})"
                )

        print()
        if report.passed:
            print("Status: ✓ PASS (Coverage > 95%, No major tickers missing)")
        else:
            reasons = []
            if report.coverage_rate < MIN_COVERAGE_THRESHOLD:
                reasons.append(f"Coverage {coverage_pct:.1f}% < 95%")
            if report.missing_major:
                reasons.append(f"{len(report.missing_major)} major tickers missing")
            print(f"Status: ✗ FAIL ({', '.join(reasons)})")
        print("=" * 60)
        print()

    def merge_results(
        self,
        market: str,
        new_metrics: list[dict],
        new_prices: list[dict],
    ) -> None:
        """Merge new collection results into existing CSV files.

        Uses the 'latest' symlink to find the current version directory.

        Args:
            market: Market identifier ("US" or "KR")
            new_metrics: List of new metrics records
            new_prices: List of new price records
        """
        if not new_metrics and not new_prices:
            self.logger.info("No new data to merge")
            return

        prefix = market.lower()

        # Find the current version directory via 'latest' symlink
        latest_link = DATA_DIR / "latest"
        if not latest_link.is_symlink():
            self.logger.warning("No 'latest' symlink found, skipping merge")
            return

        version_dir = latest_link.resolve()
        if not version_dir.exists():
            self.logger.warning(f"Version directory not found: {version_dir}")
            return

        # Merge metrics (optimized: use drop_duplicates instead of set operations)
        metrics_file = version_dir / f"{prefix}_metrics.csv"
        if metrics_file.exists() and new_metrics:
            existing_df = pd.read_csv(metrics_file)
            new_df = pd.DataFrame(new_metrics)

            # Concat and drop duplicates (keep last = keep new data)
            merged_df = pd.concat([existing_df, new_df], ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=["ticker"], keep="last")
            merged_df.to_csv(metrics_file, index=False)
            self.logger.info(
                f"Merged {len(new_metrics)} metrics into {metrics_file.name} "
                f"(total: {len(merged_df)})"
            )

        # Merge prices (optimized: use drop_duplicates instead of set operations)
        prices_file = version_dir / f"{prefix}_prices.csv"
        if prices_file.exists() and new_prices:
            existing_df = pd.read_csv(prices_file)
            new_df = pd.DataFrame(new_prices)

            # Concat and drop duplicates (keep last = keep new data)
            merged_df = pd.concat([existing_df, new_df], ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=["ticker"], keep="last")
            merged_df.to_csv(prices_file, index=False)
            self.logger.info(
                f"Merged {len(new_prices)} prices into {prices_file.name} "
                f"(total: {len(merged_df)})"
            )
