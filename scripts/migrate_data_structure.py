#!/usr/bin/env python3
"""
Migrate data from flat structure to date+version structure.

Before:
    data/
    ├── prices/
    │   ├── us_prices_20260101.csv
    │   └── kr_prices_20260101.csv
    ├── financials/
    │   ├── us_metrics_20260101.csv
    │   └── kr_metrics_20260101.csv
    ├── us_companies.csv
    └── kr_companies.csv

After:
    data/
    ├── 2026-01-01/
    │   └── v1/
    │       ├── us_prices.csv
    │       ├── us_metrics.csv
    │       ├── kr_prices.csv
    │       └── kr_metrics.csv
    ├── companies/
    │   ├── us_companies.csv
    │   └── kr_companies.csv
    └── latest -> 2026-01-03/v1/

Usage:
    python scripts/migrate_data_structure.py [--dry-run]
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def parse_date_from_filename(filename: str) -> str | None:
    """Parse YYYYMMDD from filename and return YYYY-MM-DD."""
    match = re.search(r"_(\d{8})\.csv$", filename)
    if match:
        date_str = match.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def migrate(dry_run: bool = False) -> None:
    """Migrate data to new structure."""
    print("=" * 60)
    print("Data Structure Migration")
    print("=" * 60)
    if dry_run:
        print("DRY RUN MODE - No files will be moved")
    print()

    # 1. Create and populate companies/ directory
    print("Step 1: Migrating company files...")
    companies_dir = DATA_DIR / "companies"
    if not dry_run:
        companies_dir.mkdir(exist_ok=True)

    for prefix in ["us", "kr"]:
        src = DATA_DIR / f"{prefix}_companies.csv"
        dst = companies_dir / f"{prefix}_companies.csv"
        if src.exists():
            print(f"  Move: {src.name} -> companies/{dst.name}")
            if not dry_run:
                shutil.move(src, dst)
        elif dst.exists():
            print(f"  Skip: {dst.name} (already migrated)")

    # 2. Migrate prices and financials
    print()
    print("Step 2: Migrating prices and financials...")

    # Collect all dates from existing files
    dates_to_migrate: dict[str, list[tuple[Path, str, str]]] = {}  # date -> [(file, type, market)]

    for subdir, _file_type in [("prices", "prices"), ("financials", "metrics")]:
        dir_path = DATA_DIR / subdir
        if not dir_path.exists():
            continue

        for file in dir_path.glob("*.csv"):
            if file.name.startswith("."):
                continue

            # Parse filename: us_prices_20260103.csv or kr_metrics_20260103.csv
            match = re.match(r"(us|kr)_(prices|metrics)_(\d{8})\.csv", file.name)
            if not match:
                print(f"  Skip: {file.name} (unrecognized format)")
                continue

            market, ftype, date_str = match.groups()
            formatted_date = parse_date_from_filename(file.name)
            if not formatted_date:
                continue

            if formatted_date not in dates_to_migrate:
                dates_to_migrate[formatted_date] = []
            dates_to_migrate[formatted_date].append((file, ftype, market))

    # Move files to new structure
    for date_str in sorted(dates_to_migrate.keys()):
        files = dates_to_migrate[date_str]
        version_dir = DATA_DIR / date_str / "v1"

        print(f"  Date: {date_str} ({len(files)} files)")
        if not dry_run:
            version_dir.mkdir(parents=True, exist_ok=True)

        for src_file, ftype, market in files:
            new_name = f"{market}_{ftype}.csv"
            dst = version_dir / new_name
            print(f"    Move: {src_file.parent.name}/{src_file.name} -> {date_str}/v1/{new_name}")
            if not dry_run:
                shutil.move(src_file, dst)

        # Create current symlink for this date
        current_link = DATA_DIR / date_str / "current"
        if not dry_run:
            if current_link.is_symlink():
                current_link.unlink()
            current_link.symlink_to("v1")
            print(f"    Symlink: {date_str}/current -> v1")

    # 3. Remove empty directories
    print()
    print("Step 3: Cleaning up empty directories...")

    for subdir in ["prices", "financials"]:
        dir_path = DATA_DIR / subdir
        if dir_path.exists():
            remaining = list(dir_path.iterdir())
            # Only .gitkeep should remain
            gitkeep_only = all(f.name == ".gitkeep" for f in remaining)
            if not remaining or gitkeep_only:
                if not dry_run:
                    if remaining:
                        # Keep .gitkeep
                        print(f"  Keep: {subdir}/ (contains .gitkeep)")
                    else:
                        dir_path.rmdir()
                        print(f"  Remove: {subdir}/ (empty)")
            else:
                print(f"  Keep: {subdir}/ (still has files: {[f.name for f in remaining[:5]]}...)")

    # 4. Create latest symlink
    print()
    print("Step 4: Creating 'latest' symlink...")

    if dates_to_migrate:
        latest_date = max(dates_to_migrate.keys())
        latest_path = f"{latest_date}/v1"
        latest_link = DATA_DIR / "latest"

        print(f"  Symlink: latest -> {latest_path}")
        if not dry_run:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(latest_path)
    else:
        print("  Skip: No data to link")

    print()
    print("=" * 60)
    if dry_run:
        print("DRY RUN complete. Run without --dry-run to apply changes.")
    else:
        print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
