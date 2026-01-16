"""Stock Pipeline CLI - replaces collect-and-backup.sh.

Usage:
    stock-pipeline collect [us|kr|all] [OPTIONS]
    stock-pipeline backup
    stock-pipeline load [OPTIONS]

This CLI provides the same functionality as the shell script but with:
- Better error handling
- Type-safe configuration
- Testability
- Consistent exit codes (0=success, 1=error, 2=rate_limit)
"""

# Load .env file before any other imports
from pathlib import Path as _Path

from dotenv import load_dotenv

_env_path = _Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from config import get_settings
from rich.console import Console
from rich.logging import RichHandler

# Create CLI app
app = typer.Typer(
    name="stock-pipeline",
    help="Stock Screener Data Pipeline CLI",
    add_completion=False,
)

console = Console()


def setup_logging(quiet: bool = False, verbose: bool = False) -> None:
    """Configure logging with rich handler."""
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False)],
    )


@app.command()
def collect(
    market: Annotated[str, typer.Argument(help="Market to collect: us, kr, or all")] = "all",
    resume: Annotated[bool, typer.Option("--resume", "-r", help="Resume from previous run")] = False,
    csv_only: Annotated[bool, typer.Option("--csv-only", help="Only save to CSV (skip DB)")] = False,
    test: Annotated[bool, typer.Option("--test", "-t", help="Test mode (3 tickers only)")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Minimal output")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
    batch_size: Annotated[int | None, typer.Option("--batch-size", help="Batch size for metrics")] = None,
    tickers_file: Annotated[Path | None, typer.Option("--tickers-file", help="File with tickers")] = None,
    no_backup: Annotated[bool, typer.Option("--no-backup", help="Skip Google Drive backup")] = False,
    no_db: Annotated[bool, typer.Option("--no-db", help="Skip Supabase loading")] = False,
    limit: Annotated[int | None, typer.Option("--limit", help="Limit number of tickers")] = None,
    # New rate limit tuning options
    delay: Annotated[float | None, typer.Option("--delay", help="Inter-batch delay in seconds")] = None,
    workers: Annotated[int | None, typer.Option("--workers", help="Number of concurrent workers")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout", help="Request timeout in seconds")] = None,
    jitter: Annotated[float | None, typer.Option("--jitter", help="Random jitter range in seconds")] = None,
) -> None:
    """Collect stock data for specified market(s).

    This command replaces the shell script for data collection.

    Examples:
        stock-pipeline collect all
        stock-pipeline collect us --resume
        stock-pipeline collect kr --csv-only --quiet
        stock-pipeline collect all --test
    """
    setup_logging(quiet=quiet, verbose=verbose)
    logger = logging.getLogger(__name__)

    # Validate market
    market = market.lower()
    if market not in ("us", "kr", "all"):
        console.print(f"[red]Invalid market: {market}. Use us, kr, or all.[/red]")
        raise typer.Exit(code=1)

    save_db = not (csv_only or no_db)

    # Print configuration
    if not quiet:
        console.print("=" * 44)
        console.print("[bold]Stock Data Pipeline[/bold]")
        console.print(f"Market: {market.upper()}")
        console.print(f"Resume: {resume}")
        console.print("Save CSV: True")
        console.print(f"Save DB: {save_db}")
        console.print(f"Test mode: {test}")
        if limit:
            console.print(f"Limit: {limit}")
        # Show rate limit tuning params if customized
        if batch_size:
            console.print(f"Batch size: {batch_size}")
        if delay:
            console.print(f"Delay: {delay}s")
        if workers:
            console.print(f"Workers: {workers}")
        if jitter:
            console.print(f"Jitter: {jitter}s")
        console.print("=" * 44)

    rate_limit_hit = False
    markets_to_collect = ["kr", "us"] if market == "all" else [market]

    for m in markets_to_collect:
        if not quiet:
            console.print(f"\n[bold blue]Collecting {m.upper()} stocks...[/bold blue]")

        try:
            result = _run_collection(
                market=m,
                resume=resume,
                save_db=save_db,
                test=test,
                quiet=quiet,
                batch_size=batch_size,
                tickers_file=tickers_file,
                limit=limit,
                delay=delay,
                workers=workers,
                timeout=timeout,
                jitter=jitter,
            )

            if result.rate_limit_hit:
                rate_limit_hit = True
                console.print(f"[yellow]Rate limit hit for {m.upper()}[/yellow]")
                console.print("[yellow]Progress saved. Run with --resume to continue.[/yellow]")
            else:
                console.print(f"[green]{m.upper()} collection completed![/green]")
                console.print(f"  Success: {result.success}/{result.total}")
                if result.missing_tickers:
                    console.print(f"  Missing: {len(result.missing_tickers)}")

        except Exception as e:
            logger.error(f"{m.upper()} collection failed: {e}")
            console.print(f"[red]{m.upper()} collection failed: {e}[/red]")
            if "rate limit" in str(e).lower():
                rate_limit_hit = True

    # Backup phase
    if not no_backup and not rate_limit_hit:
        if not quiet:
            console.print("\n[bold blue]Backing up to Google Drive...[/bold blue]")
        try:
            _run_backup()
            console.print("[green]Backup completed![/green]")
        except Exception as e:
            console.print(f"[yellow]Backup skipped: {e}[/yellow]")

    # Note: DB loading is now done directly in _run_collection via _save_to_db
    # The old _run_db_load (CSV loader) is kept for manual loading via `load` command

    # Summary
    if not quiet:
        console.print("\n" + "=" * 44)
        if rate_limit_hit:
            console.print("[yellow]Completed with rate limits.[/yellow]")
            console.print("[yellow]Run with --resume to continue after reset.[/yellow]")
        else:
            console.print("[green]All tasks completed successfully![/green]")
        console.print("=" * 44)

    # Exit code
    if rate_limit_hit:
        raise typer.Exit(code=2)


@app.command()
def backup() -> None:
    """Backup data to Google Drive using rclone."""
    setup_logging()
    console.print("[bold]Backing up to Google Drive...[/bold]")

    try:
        _run_backup()
        console.print("[green]Backup completed![/green]")
    except Exception as e:
        console.print(f"[red]Backup failed: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def load(
    us_only: Annotated[bool, typer.Option("--us-only", help="Load only US data")] = False,
    kr_only: Annotated[bool, typer.Option("--kr-only", help="Load only KR data")] = False,
    date_str: Annotated[str | None, typer.Option("--date", help="Date (YYYY-MM-DD)")] = None,
    version: Annotated[str | None, typer.Option("--version", help="Version (v1, v2, ...)")] = None,
) -> None:
    """Load CSV data to Supabase."""
    setup_logging()

    market = None
    if us_only:
        market = "us"
    elif kr_only:
        market = "kr"

    console.print("[bold]Loading to Supabase...[/bold]")
    if market:
        console.print(f"Market: {market.upper()}")
    if date_str:
        console.print(f"Date: {date_str}")

    try:
        _run_db_load(market=market, date_str=date_str, version=version)
        console.print("[green]Load completed![/green]")
    except Exception as e:
        console.print(f"[red]Load failed: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold]Stock Pipeline v0.3.0[/bold]")
    console.print("Separate KR/US pipelines with improved resilience")


@app.command("update-tickers")
def update_tickers(
    market: Annotated[str, typer.Argument(help="Market to update: us, kr, or all")] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show changes without saving")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Minimal output")] = False,
) -> None:
    """Update ticker universe from official sources.

    Sources:
        US: NASDAQ FTP (nasdaqlisted.txt, otherlisted.txt)
        KR: FDR KRX-DESC (FinanceDataReader)

    Examples:
        stock-pipeline update-tickers all
        stock-pipeline update-tickers kr --dry-run
        stock-pipeline update-tickers us -q
    """
    setup_logging(quiet=quiet)
    from cli.tickers import update_tickers as do_update

    market = market.lower()
    if market not in ("us", "kr", "all"):
        console.print(f"[red]Invalid market: {market}. Use us, kr, or all.[/red]")
        raise typer.Exit(code=1)

    markets = ["kr", "us"] if market == "all" else [market]

    for m in markets:
        if not quiet:
            console.print(f"\n[bold blue]Updating {m.upper()} tickers...[/bold blue]")

        try:
            result = do_update(m, dry_run=dry_run)

            if result.errors:
                console.print(f"[red]Error: {result.errors[0]}[/red]")
                continue

            # Show results
            console.print(f"  Total: {result.total} tickers")

            if result.added:
                console.print(f"  [green]+ Added: {len(result.added)}[/green]")
                if not quiet and len(result.added) <= 20:
                    for t in result.added[:20]:
                        console.print(f"    + {t}")
                elif not quiet:
                    console.print("    (showing first 20)")
                    for t in result.added[:20]:
                        console.print(f"    + {t}")

            if result.removed:
                console.print(f"  [yellow]- Removed: {len(result.removed)}[/yellow]")
                if not quiet and len(result.removed) <= 20:
                    for t in result.removed[:20]:
                        console.print(f"    - {t}")
                elif not quiet:
                    console.print("    (showing first 20)")
                    for t in result.removed[:20]:
                        console.print(f"    - {t}")

            if dry_run:
                console.print("  [dim](dry run - no changes saved)[/dim]")
            elif result.updated:
                console.print(f"  [green]Saved {result.updated} tickers[/green]")

        except Exception as e:
            console.print(f"[red]{m.upper()} update failed: {e}[/red]")

    if not quiet:
        console.print("\n[green]Done![/green]")


# ==================== Helper Functions ====================


@dataclass
class CollectionResultAdapter:
    """Adapter to match the old collector result interface."""

    success: int
    total: int
    rate_limit_hit: bool
    missing_tickers: list[str]


def _run_collection(
    market: str,
    resume: bool = False,
    save_db: bool = True,
    test: bool = False,
    quiet: bool = False,
    batch_size: int | None = None,
    tickers_file: Path | None = None,
    limit: int | None = None,
    delay: float | None = None,
    workers: int | None = None,
    timeout: float | None = None,
    jitter: float | None = None,
) -> CollectionResultAdapter:
    """Run collection for a single market using the new pipeline architecture."""
    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Load tickers from file if provided
    tickers: list[str] | None = None
    if tickers_file and tickers_file.exists():
        with open(tickers_file) as f:
            tickers = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    # Load default tickers if not provided
    if tickers is None:
        tickers = _load_default_tickers(market, settings)

    # Apply test mode
    if test:
        if market.lower() == "us":
            test_tickers = ["AAPL", "MSFT", "GOOGL"]
        else:  # kr
            test_tickers = ["005930", "000660", "035420"]  # Samsung, SK Hynix, Naver
        # Filter to only include tickers that exist in the universe
        ticker_set = set(tickers)
        tickers = [t for t in test_tickers if t in ticker_set]
        if not tickers:
            # Fallback to first 3 if test tickers not found
            tickers = _load_default_tickers(market, settings)[:3]

    # Apply limit
    if limit:
        tickers = tickers[:limit]

    # Run collection based on market
    if market.lower() == "us":
        result = _run_us_collection(
            tickers=tickers,
            resume=resume,
            batch_size=batch_size,
            delay=delay,
            timeout=timeout,
            jitter=jitter,
        )
    else:  # kr
        result = _run_kr_collection(
            tickers=tickers,
            resume=resume,
            batch_size=batch_size,
            timeout=timeout,
        )

    # Save to CSV
    if result[1]:  # merged_data is not empty
        _save_to_csv(market, result[1], settings)

    # Save to DB if requested
    if save_db and result[1]:
        try:
            _save_to_db(market, result[1])
        except Exception as e:
            logger.warning(f"Failed to save to DB: {e}")

    # Adapt result to old interface
    collection_result = result[0]
    return CollectionResultAdapter(
        success=collection_result.successful,
        total=collection_result.total_tickers,
        rate_limit_hit=collection_result.rate_limit_hit,
        missing_tickers=[],  # Not tracked in new pipeline
    )


def _load_default_tickers(market: str, settings) -> list[str]:
    """Load default tickers from CSV file."""
    if market.lower() == "us":
        tickers_file = settings.companies_dir / "us_companies.csv"
    else:
        tickers_file = settings.companies_dir / "kr_companies.csv"

    if not tickers_file.exists():
        return []

    tickers = []
    with open(tickers_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("ticker") or row.get("symbol")
            if ticker:
                tickers.append(ticker)
    return tickers


def _run_us_collection(
    tickers: list[str],
    resume: bool = False,
    batch_size: int | None = None,
    delay: float | None = None,
    timeout: float | None = None,
    jitter: float | None = None,
):
    """Run US collection using the new pipeline."""
    from us import USConfig, collect_us

    # Build config with overrides
    config_kwargs = {}
    if batch_size is not None:
        config_kwargs["metrics_batch_size"] = batch_size
    if delay is not None:
        config_kwargs["batch_delay"] = delay
    if timeout is not None:
        config_kwargs["download_timeout"] = timeout
    if jitter is not None:
        config_kwargs["batch_jitter"] = jitter

    config = USConfig(**config_kwargs) if config_kwargs else None

    # Run async collection
    return asyncio.run(collect_us(tickers=tickers, config=config, resume=resume))


def _run_kr_collection(
    tickers: list[str],
    resume: bool = False,  # Ignored - KR doesn't need resume (no rate limiting)
    batch_size: int | None = None,
    timeout: float | None = None,
):
    """Run KR collection using the new pipeline.

    Note: resume parameter is ignored for KR as it completes quickly
    without rate limiting concerns.
    """
    from kr import KRConfig, collect_kr

    # Build config with overrides
    config_kwargs = {}
    if batch_size is not None:
        config_kwargs["history_batch_size"] = batch_size
    if timeout is not None:
        config_kwargs["fdr_timeout"] = timeout

    config = KRConfig(**config_kwargs) if config_kwargs else None

    # Run async collection (resume not supported for KR)
    return asyncio.run(collect_kr(tickers=tickers, config=config))


def _save_to_csv(market: str, data: list[dict], settings) -> None:
    """Save collected data to CSV files."""
    from datetime import date

    from storage.base import VersionedPath

    if not data:
        return

    # Extract trading date from data (not execution date)
    # The "date" field in data represents the actual trading date
    trading_date = None
    for row in data:
        if row.get("date"):
            trading_date = row["date"]
            break

    # Fallback to today if no date found in data
    if not trading_date:
        trading_date = date.today().isoformat()

    versioned = VersionedPath.get_next_version(settings.data_dir, market, trading_date)
    versioned.ensure_dirs()

    # Split into prices and metrics
    price_fields = [
        "ticker", "date", "market", "latest_price", "open", "high", "low",
        "volume", "change_percent",
    ]
    metrics_fields = [
        "ticker", "date", "market", "pe_ratio", "forward_pe", "pb_ratio",
        "ps_ratio", "peg_ratio", "ev_ebitda", "roe", "roa", "gross_margin",
        "net_margin", "debt_equity", "current_ratio", "eps", "bps",
        "dividend_yield", "market_cap", "beta", "fifty_two_week_high",
        "fifty_two_week_low", "ma_50", "ma_200", "graham_number",
        "rsi", "mfi", "macd", "macd_signal", "macd_histogram",
        "bb_upper", "bb_middle", "bb_lower", "bb_percent", "volume_change",
    ]

    # Write prices.csv
    prices_file = versioned.version_dir / "prices.csv"
    with open(prices_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=price_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)

    # Write metrics.csv
    metrics_file = versioned.version_dir / "metrics.csv"
    with open(metrics_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=metrics_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)

    # Update symlinks
    versioned.update_symlinks()

    logging.getLogger(__name__).info(
        f"Saved {len(data)} records to {versioned.version_dir}"
    )


def _sanitize_value(val, max_abs: float = 1e11):
    """Sanitize a value for DB storage.

    Returns None for invalid values (NaN, Inf, too large).
    Handles both Python float and numpy float types.
    """
    import math

    if val is None:
        return None

    # Convert numpy types to Python types first
    try:
        import numpy as np
        if isinstance(val, (np.floating, np.integer)):
            val = float(val)
        if isinstance(val, np.ndarray):
            if val.size == 1:
                val = float(val.item())
            else:
                return None
    except ImportError:
        pass

    if isinstance(val, float):
        # Check for NaN and Inf (works for both Python and numpy floats)
        if math.isnan(val) or math.isinf(val):
            return None
        if abs(val) > max_abs:
            return None

    return val


# Column-specific max values based on DB NUMERIC precision
# NUMERIC(n, d) -> max value is 10^(n-d) - 1
COLUMN_MAX_VALUES = {
    # NUMERIC(8, 4) -> max ~9999
    "roe": 9999,
    "roa": 9999,
    "gross_margin": 9999,
    "net_margin": 9999,
    "dividend_yield": 9999,
    "beta": 9999,
    "rsi": 9999,
    "mfi": 9999,
    "volume_change": 9999,
    "bb_percent": 9999,
    # NUMERIC(12, 4) -> max ~99999999
    "pe_ratio": 99999999,
    "pb_ratio": 99999999,
    "ps_ratio": 99999999,
    "peg_ratio": 99999999,
    "ev_ebitda": 99999999,
    "debt_equity": 99999999,
    "current_ratio": 99999999,
    "macd": 99999999,
    "macd_signal": 99999999,
    "macd_histogram": 99999999,
    "eps": 99999999,
    # NUMERIC(16, 4) -> max ~999999999999
    "fifty_two_week_high": 999999999999,
    "fifty_two_week_low": 999999999999,
    "fifty_day_average": 999999999999,
    "two_hundred_day_average": 999999999999,
    "bb_upper": 999999999999,
    "bb_middle": 999999999999,
    "bb_lower": 999999999999,
    "open": 999999999999,
    "high": 999999999999,
    "low": 999999999999,
    "close": 999999999999,
    # NUMERIC(20, 2) -> max ~999999999999999999
    "market_cap": 1e18,
}


def _save_to_db(market: str, data: list[dict]) -> None:
    """Save collected data to Supabase.

    The DB schema requires company_id (UUID) instead of ticker.
    We need to map ticker -> company_id using the companies table.
    """
    from common.utils import get_supabase_client

    logger = logging.getLogger(__name__)

    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client not available")

    # Fetch company ID mapping from DB
    ticker_to_id = _fetch_company_mapping(client, market)
    if not ticker_to_id:
        logger.warning("No company mappings found in DB")
        return

    # Column mapping from pipeline output to DB columns
    # Note: market_cap is in prices table, not metrics table
    # Note: forward_pe, book_value_per_share, graham_number don't exist in DB
    METRICS_COLUMN_MAP = {
        "pe_ratio": "pe_ratio",
        "pb_ratio": "pb_ratio",
        "ps_ratio": "ps_ratio",
        "peg_ratio": "peg_ratio",
        "ev_ebitda": "ev_ebitda",
        "roe": "roe",
        "roa": "roa",
        "gross_margin": "gross_margin",
        "net_margin": "net_margin",
        "debt_equity": "debt_equity",
        "current_ratio": "current_ratio",
        "dividend_yield": "dividend_yield",
        "fifty_two_week_high": "fifty_two_week_high",
        "fifty_two_week_low": "fifty_two_week_low",
        "beta": "beta",
        "ma_50": "fifty_day_average",
        "ma_200": "two_hundred_day_average",
        "rsi": "rsi",
        "mfi": "mfi",
        "volume_change": "volume_change",
        "macd": "macd",
        "macd_signal": "macd_signal",
        "macd_histogram": "macd_histogram",
        "bb_upper": "bb_upper",
        "bb_middle": "bb_middle",
        "bb_lower": "bb_lower",
        "bb_percent": "bb_percent",
        "eps": "eps",
    }

    # Determine market name for lookup
    is_kr = market.upper() == "KR"
    data_source = "fdr+naver" if is_kr else "yfinance"

    # Build metrics records
    metrics_data = []
    prices_data = []

    for row in data:
        ticker = str(row.get("ticker", ""))

        # Look up company_id
        if is_kr:
            company_id = ticker_to_id.get((ticker, "KOSPI")) or ticker_to_id.get((ticker, "KOSDAQ"))
        else:
            company_id = ticker_to_id.get((ticker, "US"))

        if not company_id:
            continue

        date_val = row.get("date")
        if not date_val:
            continue

        # Build metrics record
        metrics_row = {
            "company_id": company_id,
            "date": date_val,
            "data_source": data_source,
        }

        for src_col, db_col in METRICS_COLUMN_MAP.items():
            max_val = COLUMN_MAX_VALUES.get(db_col, 1e11)
            val = _sanitize_value(row.get(src_col), max_abs=max_val)
            if val is not None:
                metrics_row[db_col] = val

        metrics_data.append(metrics_row)

        # Build prices record
        prices_row = {
            "company_id": company_id,
            "date": date_val,
        }
        for col in ["open", "high", "low", "volume", "market_cap"]:
            max_val = COLUMN_MAX_VALUES.get(col, 1e11)
            val = _sanitize_value(row.get(col), max_abs=max_val)
            if val is not None:
                prices_row[col] = val

        # Map latest_price to close
        max_close = COLUMN_MAX_VALUES.get("close", 1e11)
        close_val = _sanitize_value(row.get("latest_price"), max_abs=max_close)
        if close_val is not None:
            prices_row["close"] = close_val

        # Only add if we have close price
        if "close" in prices_row:
            prices_data.append(prices_row)

    # Final sanitization pass - ensure no bad values slip through
    import math
    import numpy as np

    def _is_bad_numeric(v) -> bool:
        """Check if a value is NaN, Inf, or otherwise invalid for DB."""
        if v is None:
            return False
        # Check using repr() - catches string representations
        v_repr = repr(v).lower()
        if 'inf' in v_repr or 'nan' in v_repr:
            return True
        # Check numpy types
        try:
            if np.isnan(v) or np.isinf(v):
                return True
        except (TypeError, ValueError):
            pass
        # Check Python floats
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return True
        # Check JSON serializability
        import json
        try:
            json.dumps(v, allow_nan=False)
        except (ValueError, TypeError):
            return True
        return False

    def _final_sanitize(records: list[dict]) -> list[dict]:
        """Final pass to remove any remaining bad values."""
        clean_records = []
        for record in records:
            clean = {}
            for k, v in record.items():
                if v is None:
                    continue
                # Convert numpy types to Python types
                if hasattr(v, 'item'):  # numpy scalar
                    v = v.item()
                if isinstance(v, (np.floating, np.integer)):
                    v = float(v)
                if isinstance(v, np.ndarray):
                    if v.size == 1:
                        v = float(v.item())
                    else:
                        continue
                # Check for NaN/Inf using robust check
                if _is_bad_numeric(v):
                    logger.debug(f"Filtering bad value in final pass: {k}={v}")
                    continue
                clean[k] = v
            clean_records.append(clean)
        return clean_records

    metrics_data = _final_sanitize(metrics_data)
    prices_data = _final_sanitize(prices_data)

    # Upsert metrics
    if metrics_data:
        for i in range(0, len(metrics_data), 100):
            batch = metrics_data[i:i + 100]
            try:
                client.table("metrics").upsert(
                    batch, on_conflict="company_id,date"
                ).execute()
            except Exception as e:
                # Log the problematic batch for debugging
                logger.error(f"Metrics upsert failed: {e}")
                import json
                for rec in batch:
                    for k, v in rec.items():
                        # Check all value types
                        val_type = type(v).__name__
                        is_bad = False
                        if isinstance(v, float):
                            is_bad = math.isnan(v) or math.isinf(v)
                        elif isinstance(v, np.floating):
                            is_bad = np.isnan(v) or np.isinf(v)
                        if is_bad:
                            logger.error(f"  Bad value: {k}={v} (type={val_type})")
                        # Try JSON serialization to see if it produces "Infinity"
                        try:
                            json_val = json.dumps(v)
                            if "Infinity" in json_val or "NaN" in json_val:
                                logger.error(f"  JSON bad value: {k}={v} -> {json_val}")
                        except (TypeError, ValueError):
                            pass
                raise
        logger.info(f"Upserted {len(metrics_data)} metrics to DB")

    # Upsert prices
    if prices_data:
        for i in range(0, len(prices_data), 100):
            batch = prices_data[i:i + 100]
            try:
                client.table("prices").upsert(
                    batch, on_conflict="company_id,date"
                ).execute()
            except Exception as e:
                logger.error(f"Prices upsert failed: {e}")
                for rec in batch:
                    for k, v in rec.items():
                        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                            logger.error(f"  Bad value: {k}={v}")
                raise
        logger.info(f"Upserted {len(prices_data)} prices to DB")


def _fetch_company_mapping(client, market: str) -> dict[tuple[str, str], str]:
    """Fetch ticker -> company_id mapping from DB."""
    all_companies: list[dict] = []
    offset = 0
    page_size = 1000

    # Filter by market for efficiency
    if market.upper() == "KR":
        markets = ["KOSPI", "KOSDAQ"]
    else:
        markets = ["US"]

    while True:
        result = (
            client.table("companies")
            .select("id, ticker, market")
            .in_("market", markets)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_companies.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    return {(r["ticker"], r["market"]): r["id"] for r in all_companies}


def _run_backup() -> None:
    """Run Google Drive backup using rclone."""
    import subprocess

    from storage.base import VersionedPath

    settings = get_settings()
    backed_up = False

    # Backup each market's latest data
    for market in ["us", "kr"]:
        latest = VersionedPath.get_latest(settings.data_dir, market)

        if latest is None:
            console.print(f"[yellow]No {market.upper()} data to backup (no 'latest' symlink)[/yellow]")
            continue

        # Backup versioned data (e.g., us/2026-01-03/v1/)
        latest_path = f"{market}/{latest.date_str}/v{latest.version}"
        console.print(f"[blue]Backing up {market.upper()} data: {latest_path}[/blue]")
        subprocess.run(
            ["rclone", "copy", str(latest.version_dir), f"gdrive:{latest_path}", "--progress"],
            check=True,
        )
        backed_up = True

    if not backed_up:
        raise RuntimeError("No data to backup (no 'latest' symlinks found)")

    # Backup companies
    companies_dir = settings.companies_dir
    if companies_dir.exists():
        subprocess.run(
            ["rclone", "copy", str(companies_dir), "gdrive:companies/", "--progress"],
            check=True,
        )


def _run_db_load(
    market: str | None = None,
    date_str: str | None = None,
    version: str | None = None,
) -> None:
    """Run CSV to Supabase loading."""
    # Import and run the existing loader
    from loaders.csv_to_db import main as csv_to_db_main

    args = []
    if market == "us":
        args.append("--us-only")
    elif market == "kr":
        args.append("--kr-only")
    if date_str:
        args.extend(["--date", date_str])
    if version:
        args.extend(["--version", version])

    # The loader uses argparse, so we need to set sys.argv
    old_argv = sys.argv
    sys.argv = ["csv_to_db"] + args
    try:
        csv_to_db_main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    app()
