"""KR data sources.

- FDR (FinanceDataReader): Prices and OHLCV history
- Naver Finance: Fundamental metrics (web scraping)
- KIS API: Primary metrics source (optional, requires credentials)
"""

from .fdr import FDRSource
from .kis import KISSource
from .naver import NaverSource

__all__ = [
    "FDRSource",
    "KISSource",
    "NaverSource",
]
