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

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from config import get_settings

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
    batch_size: Annotated[Optional[int], typer.Option("--batch-size", help="Batch size")] = None,
    tickers_file: Annotated[Optional[Path], typer.Option("--tickers-file", help="File with tickers")] = None,
    no_backup: Annotated[bool, typer.Option("--no-backup", help="Skip Google Drive backup")] = False,
    no_db: Annotated[bool, typer.Option("--no-db", help="Skip Supabase loading")] = False,
    limit: Annotated[Optional[int], typer.Option("--limit", help="Limit number of tickers")] = None,
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

    settings = get_settings()
    save_db = not (csv_only or no_db)

    # Print configuration
    if not quiet:
        console.print("=" * 44)
        console.print("[bold]Stock Data Pipeline[/bold]")
        console.print(f"Market: {market.upper()}")
        console.print(f"Resume: {resume}")
        console.print(f"Save CSV: True")
        console.print(f"Save DB: {save_db}")
        console.print(f"Test mode: {test}")
        if limit:
            console.print(f"Limit: {limit}")
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
            )

            if result.rate_limit_hit:
                rate_limit_hit = True
                console.print(f"[yellow]Rate limit hit for {m.upper()}[/yellow]")
                console.print(f"[yellow]Progress saved. Run with --resume to continue.[/yellow]")
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

    # DB loading phase
    if save_db and not csv_only and not rate_limit_hit:
        if not quiet:
            console.print("\n[bold blue]Loading to Supabase...[/bold blue]")
        try:
            _run_db_load(market=market)
            console.print("[green]DB load completed![/green]")
        except Exception as e:
            console.print(f"[red]DB load failed: {e}[/red]")

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
    date_str: Annotated[Optional[str], typer.Option("--date", help="Date (YYYY-MM-DD)")] = None,
    version: Annotated[Optional[str], typer.Option("--version", help="Version (v1, v2, ...)")] = None,
) -> None:
    """Load CSV data to Supabase."""
    setup_logging()

    market = None
    if us_only:
        market = "us"
    elif kr_only:
        market = "kr"

    console.print(f"[bold]Loading to Supabase...[/bold]")
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
    console.print("[bold]Stock Pipeline v0.2.0[/bold]")
    console.print("New architecture with clean abstractions")


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
                    console.print(f"    (showing first 20)")
                    for t in result.added[:20]:
                        console.print(f"    + {t}")

            if result.removed:
                console.print(f"  [yellow]- Removed: {len(result.removed)}[/yellow]")
                if not quiet and len(result.removed) <= 20:
                    for t in result.removed[:20]:
                        console.print(f"    - {t}")
                elif not quiet:
                    console.print(f"    (showing first 20)")
                    for t in result.removed[:20]:
                        console.print(f"    - {t}")

            if dry_run:
                console.print(f"  [dim](dry run - no changes saved)[/dim]")
            elif result.updated:
                console.print(f"  [green]Saved {result.updated} tickers[/green]")

        except Exception as e:
            console.print(f"[red]{m.upper()} update failed: {e}[/red]")

    if not quiet:
        console.print("\n[green]Done![/green]")


# ==================== Helper Functions ====================

def _run_collection(
    market: str,
    resume: bool = False,
    save_db: bool = True,
    test: bool = False,
    quiet: bool = False,
    batch_size: int | None = None,
    tickers_file: Path | None = None,
    limit: int | None = None,
):
    """Run collection for a single market."""
    from collectors.base import CollectionResult

    # Load tickers from file if provided
    tickers = None
    if tickers_file and tickers_file.exists():
        with open(tickers_file) as f:
            tickers = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    # Apply limit
    if limit and tickers:
        tickers = tickers[:limit]
    elif limit and not tickers:
        # Will be applied after get_tickers()
        pass

    # Create collector based on market
    if market.lower() == "us":
        from collectors.us_collector import create_us_collector
        collector = create_us_collector(
            save_db=save_db,
            save_csv=True,
            quiet=quiet,
        )
    else:
        from collectors.kr_collector import create_kr_collector
        collector = create_kr_collector(
            save_db=save_db,
            save_csv=True,
            quiet=quiet,
        )

    # Get tickers if not provided
    if tickers is None:
        tickers = collector.get_tickers()
        if test:
            tickers = tickers[:3]
        elif limit:
            tickers = tickers[:limit]

    # Run collection
    return collector.collect(
        tickers=tickers,
        resume=resume,
        auto_retry=True,
    )


def _run_backup() -> None:
    """Run Google Drive backup using rclone."""
    import subprocess
    from storage.base import VersionedPath

    settings = get_settings()
    latest = VersionedPath.get_latest(settings.data_dir)

    if latest is None:
        raise RuntimeError("No data to backup (no 'latest' symlink)")

    # Backup versioned data
    latest_path = f"{latest.date_str}/v{latest.version}"
    subprocess.run(
        ["rclone", "copy", str(latest.version_dir), f"gdrive:{latest_path}", "--progress"],
        check=True,
    )

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
    import sys
    old_argv = sys.argv
    sys.argv = ["csv_to_db"] + args
    try:
        csv_to_db_main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    app()
