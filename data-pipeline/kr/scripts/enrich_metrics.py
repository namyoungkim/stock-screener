"""Enrich KR metrics with missing EPS, BPS, and Graham Number.

This script supplements existing metrics.csv files with data from:
1. KIS API (primary source) - EPS, BPS
2. Naver Finance (fallback) - EPS, BPS
3. Local calculation - Graham Number = sqrt(22.5 * EPS * BPS)

Usage:
    from kr.scripts.enrich_metrics import enrich_kr_metrics
    await enrich_kr_metrics(date_str="2026-01-23", version="v3")
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from common.indicators import calculate_graham_number
from kr.config import KRConfig
from kr.sources import KISSource, NaverSource
from observability.logger import get_logger, log_context

logger = get_logger(__name__)


@dataclass
class EnrichmentResult:
    """Result of the enrichment process."""

    total_tickers: int = 0
    enriched_eps: int = 0
    enriched_bps: int = 0
    enriched_graham: int = 0
    kis_success: int = 0
    naver_success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


async def enrich_kr_metrics(
    date_str: str | None = None,
    version: str | None = None,
    data_dir: Path | None = None,
    dry_run: bool = False,
    batch_size: int = 50,
) -> EnrichmentResult:
    """Enrich KR metrics with missing EPS, BPS, and Graham Number.

    Args:
        date_str: Date string (YYYY-MM-DD). Uses latest if None.
        version: Version string (v1, v2, ...). Uses current if None.
        data_dir: Base data directory (e.g., data/kr). Uses default if None.
        dry_run: If True, don't save changes.
        batch_size: Batch size for API requests.

    Returns:
        EnrichmentResult with counts of enriched metrics.
    """
    result = EnrichmentResult()

    # Determine data directory - use default if not provided
    if data_dir is None:
        # Default to data/kr relative to repo root
        repo_root = Path(__file__).parent.parent.parent.parent
        data_dir = repo_root / "data" / "kr"

    # Find metrics file
    metrics_file = _find_metrics_file(data_dir, date_str, version)
    if metrics_file is None:
        result.errors.append("No metrics file found")
        return result

    logger.info(f"Loading metrics from {metrics_file}")

    # Load existing metrics
    rows = _load_csv(metrics_file)
    if not rows:
        result.errors.append("No data in metrics file")
        return result

    result.total_tickers = len(rows)
    logger.info(f"Loaded {result.total_tickers} tickers")

    # Find tickers with missing EPS or BPS
    tickers_need_enrichment = []
    ticker_to_row: dict[str, dict[str, Any]] = {}

    for row in rows:
        ticker = row.get("ticker", "")
        if not ticker:
            continue

        ticker_to_row[ticker] = row

        # Check if EPS or BPS is missing
        eps = _parse_float(row.get("eps"))
        bps = _parse_float(row.get("bps"))

        if eps is None or bps is None:
            tickers_need_enrichment.append(ticker)

    logger.info(f"Found {len(tickers_need_enrichment)} tickers needing enrichment")

    if not tickers_need_enrichment:
        logger.info("All tickers already have EPS and BPS")
        return result

    # Get trading date from first row
    trading_date = date.today()
    first_row = rows[0]
    if first_row.get("date"):
        try:
            trading_date = date.fromisoformat(first_row["date"])
        except ValueError:
            pass

    # Fetch metrics from KIS and Naver
    config = KRConfig(metrics_batch_size=batch_size)
    enriched_data = await _fetch_enrichment_data(
        tickers_need_enrichment, trading_date, config
    )

    # Update rows with enriched data
    for ticker, data in enriched_data.items():
        row = ticker_to_row.get(ticker)
        if row is None:
            continue

        updated = False
        original_eps = _parse_float(row.get("eps"))
        original_bps = _parse_float(row.get("bps"))

        # Update EPS
        if original_eps is None and data.get("eps") is not None:
            row["eps"] = data["eps"]
            result.enriched_eps += 1
            updated = True

        # Update BPS
        if original_bps is None and data.get("bps") is not None:
            row["bps"] = data["bps"]
            result.enriched_bps += 1
            updated = True

        # Track source
        if updated:
            if data.get("source") == "kis":
                result.kis_success += 1
            else:
                result.naver_success += 1

    # Calculate Graham Number for all rows
    for ticker, row in ticker_to_row.items():
        eps = _parse_float(row.get("eps"))
        bps = _parse_float(row.get("bps"))

        original_graham = _parse_float(row.get("graham_number"))

        if original_graham is None:
            graham = calculate_graham_number(eps, bps)
            if graham is not None:
                row["graham_number"] = graham
                result.enriched_graham += 1

    # Count failed tickers
    result.failed = len(tickers_need_enrichment) - (result.kis_success + result.naver_success)

    logger.info(
        f"Enrichment complete: EPS={result.enriched_eps}, BPS={result.enriched_bps}, "
        f"Graham={result.enriched_graham}, KIS={result.kis_success}, Naver={result.naver_success}, "
        f"Failed={result.failed}"
    )

    # Save updated metrics
    if not dry_run:
        _save_csv(metrics_file, rows)
        logger.info(f"Saved enriched metrics to {metrics_file}")
    else:
        logger.info("Dry run - no changes saved")

    return result


async def _fetch_enrichment_data(
    tickers: list[str],
    trading_date: date,
    config: KRConfig,
) -> dict[str, dict[str, Any]]:
    """Fetch EPS and BPS from KIS (primary) and Naver (fallback).

    Args:
        tickers: List of tickers to fetch
        trading_date: Trading date for the data
        config: KR pipeline configuration

    Returns:
        Dict mapping ticker to enrichment data (eps, bps, source)
    """
    result: dict[str, dict[str, Any]] = {}

    # Try KIS first if available
    kis = KISSource(config=config)
    naver = NaverSource(config=config)

    failed_tickers = tickers.copy()

    if kis.is_available:
        logger.info(f"Fetching {len(tickers)} tickers from KIS API")

        with log_context(source="kis", phase="enrich"):
            kis_result = await kis.fetch_metrics(tickers, trading_date)

        # Process KIS results
        for fetch_result in kis_result.succeeded:
            if fetch_result.data:
                ticker = fetch_result.ticker
                data = fetch_result.data

                if data.eps is not None or data.bps is not None:
                    result[ticker] = {
                        "eps": data.eps,
                        "bps": data.bps,
                        "source": "kis",
                    }
                    if ticker in failed_tickers:
                        failed_tickers.remove(ticker)

        logger.info(
            f"KIS: {kis_result.success_count} success, {len(failed_tickers)} remaining"
        )
    else:
        logger.info("KIS API not configured, using Naver only")

    # Fallback to Naver for remaining tickers
    if failed_tickers:
        logger.info(f"Fetching {len(failed_tickers)} tickers from Naver")

        with log_context(source="naver", phase="enrich"):
            naver_result = await naver.fetch_metrics(failed_tickers, trading_date)

        # Process Naver results
        for fetch_result in naver_result.succeeded:
            if fetch_result.data:
                ticker = fetch_result.ticker
                data = fetch_result.data

                if data.eps is not None or data.bps is not None:
                    result[ticker] = {
                        "eps": data.eps,
                        "bps": data.bps,
                        "source": "naver",
                    }

        logger.info(f"Naver: {naver_result.success_count} success")

    return result


def _find_metrics_file(
    data_dir: Path,
    date_str: str | None,
    version: str | None,
) -> Path | None:
    """Find the metrics.csv file for the specified date and version.

    Args:
        data_dir: Base data directory (e.g., data/kr)
        date_str: Date string (YYYY-MM-DD) or None for latest
        version: Version string (v1, v2, ...) or None for current

    Returns:
        Path to metrics.csv or None if not found
    """
    # If no date specified, use latest symlink
    if date_str is None:
        latest_link = data_dir / "latest"
        if latest_link.is_symlink():
            metrics_file = latest_link / "metrics.csv"
            if metrics_file.exists():
                return metrics_file.resolve()
        return None

    # Find date directory
    date_dir = data_dir / date_str
    if not date_dir.exists():
        return None

    # If no version specified, use current symlink
    if version is None:
        current_link = date_dir / "current"
        if current_link.is_symlink():
            metrics_file = current_link / "metrics.csv"
            if metrics_file.exists():
                return metrics_file.resolve()
        return None

    # Use specific version
    version_dir = date_dir / version
    metrics_file = version_dir / "metrics.csv"
    if metrics_file.exists():
        return metrics_file

    return None


def _load_csv(file_path: Path) -> list[dict[str, Any]]:
    """Load CSV file into list of dicts."""
    rows = []
    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _save_csv(file_path: Path, rows: list[dict[str, Any]]) -> None:
    """Save list of dicts to CSV file."""
    if not rows:
        return

    # Get fieldnames from first row
    fieldnames = list(rows[0].keys())

    with open(file_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_float(value: Any) -> float | None:
    """Parse a value to float, returning None for invalid/empty values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value or value in ("-", "N/A", "NA", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None
