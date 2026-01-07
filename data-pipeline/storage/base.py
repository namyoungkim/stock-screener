"""Base protocol and data classes for storage backends."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class SaveResult:
    """Result of a save operation."""

    saved: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.saved + self.skipped

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def merge(self, other: "SaveResult") -> "SaveResult":
        """Merge another SaveResult into this one."""
        return SaveResult(
            saved=self.saved + other.saved,
            skipped=self.skipped + other.skipped,
            errors=self.errors + other.errors,
        )


@runtime_checkable
class Storage(Protocol):
    """Protocol for storage backends (CSV, Supabase).

    All storage backends must implement this protocol.
    The protocol is runtime checkable, so you can use isinstance() to verify.
    """

    @property
    def name(self) -> str:
        """Storage backend name (e.g., 'csv', 'supabase')."""
        ...

    def save_companies(self, records: list[dict], market: str) -> SaveResult:
        """Save company records.

        Args:
            records: List of company dicts with keys:
                - ticker: str
                - name: str
                - market: str
                - sector: str | None
                - industry: str | None
            market: Market identifier ('US' or 'KR')

        Returns:
            SaveResult with counts of saved/skipped records
        """
        ...

    def save_metrics(self, records: list[dict], market: str) -> SaveResult:
        """Save metrics records.

        Args:
            records: List of metrics dicts with ticker and metric values
            market: Market identifier ('US' or 'KR')

        Returns:
            SaveResult with counts of saved/skipped records
        """
        ...

    def save_prices(self, records: list[dict], market: str) -> SaveResult:
        """Save price records.

        Args:
            records: List of price dicts with keys:
                - ticker: str
                - date: str (YYYY-MM-DD)
                - open, high, low, close: float
                - volume: int
            market: Market identifier ('US' or 'KR')

        Returns:
            SaveResult with counts of saved/skipped records
        """
        ...

    def load_completed_tickers(self, market: str) -> set[str]:
        """Load tickers that have already been collected.

        Used for resume functionality.

        Args:
            market: Market identifier ('US' or 'KR')

        Returns:
            Set of ticker symbols that have been saved
        """
        ...

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        """Get mapping of (ticker, market) to company_id.

        Used when saving metrics/prices that need to reference companies.

        Args:
            market: Market identifier ('US' or 'KR')

        Returns:
            Dict mapping ticker to company_id
        """
        ...


class BaseStorage:
    """Base implementation with common functionality.

    Subclasses should override the save/load methods.
    """

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def save_companies(self, records: list[dict], market: str) -> SaveResult:
        raise NotImplementedError("Subclass must implement save_companies")

    def save_metrics(self, records: list[dict], market: str) -> SaveResult:
        raise NotImplementedError("Subclass must implement save_metrics")

    def save_prices(self, records: list[dict], market: str) -> SaveResult:
        raise NotImplementedError("Subclass must implement save_prices")

    def load_completed_tickers(self, market: str) -> set[str]:
        raise NotImplementedError("Subclass must implement load_completed_tickers")

    def get_company_id_mapping(self, market: str) -> dict[str, str]:
        raise NotImplementedError("Subclass must implement get_company_id_mapping")


@dataclass
class VersionedPath:
    """Represents a versioned data directory path.

    Structure: data/{date}/v{version}/
    Example: data/2026-01-03/v1/
    """

    base_dir: Path
    date_str: str  # YYYY-MM-DD
    version: int = 1

    @property
    def date_dir(self) -> Path:
        """Path to the date directory."""
        return self.base_dir / self.date_str

    @property
    def version_dir(self) -> Path:
        """Path to the versioned directory."""
        return self.date_dir / f"v{self.version}"

    @property
    def current_symlink(self) -> Path:
        """Path to the 'current' symlink in date directory."""
        return self.date_dir / "current"

    @property
    def latest_symlink(self) -> Path:
        """Path to the 'latest' symlink in base directory."""
        return self.base_dir / "latest"

    def ensure_dirs(self) -> None:
        """Create directories if they don't exist."""
        self.version_dir.mkdir(parents=True, exist_ok=True)

    def update_symlinks(self) -> None:
        """Update current and latest symlinks to point to this version."""
        # Update current symlink (relative within date_dir)
        if self.current_symlink.is_symlink():
            self.current_symlink.unlink()
        self.current_symlink.symlink_to(f"v{self.version}")

        # Update latest symlink (relative from base_dir)
        if self.latest_symlink.is_symlink():
            self.latest_symlink.unlink()
        self.latest_symlink.symlink_to(f"{self.date_str}/v{self.version}")

    @classmethod
    def get_next_version(cls, base_dir: Path, date_str: str) -> "VersionedPath":
        """Get the next available version for a date."""
        date_dir = base_dir / date_str
        if not date_dir.exists():
            return cls(base_dir=base_dir, date_str=date_str, version=1)

        # Find existing versions
        existing = [
            int(p.name[1:])
            for p in date_dir.iterdir()
            if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
        ]

        next_version = max(existing, default=0) + 1
        return cls(base_dir=base_dir, date_str=date_str, version=next_version)

    @classmethod
    def get_latest(cls, base_dir: Path) -> "VersionedPath | None":
        """Get the latest versioned path from the 'latest' symlink."""
        latest = base_dir / "latest"
        if not latest.is_symlink():
            return None

        target = latest.resolve()
        if not target.exists():
            return None

        # Parse path: should be {date}/v{version}
        parts = target.relative_to(base_dir).parts
        if len(parts) != 2:
            return None

        date_str, version_str = parts
        if not version_str.startswith("v"):
            return None

        try:
            version = int(version_str[1:])
        except ValueError:
            return None

        return cls(base_dir=base_dir, date_str=date_str, version=version)
