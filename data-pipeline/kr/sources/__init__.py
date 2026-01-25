"""KR data sources.

- FDR (FinanceDataReader): Prices and OHLCV history
- Naver Finance: Fundamental metrics (web scraping)
- KIS API: Primary metrics source (optional, requires credentials)
- DART API: Financial statements for ROA, PS Ratio, EV/EBITDA (optional)
"""

from .dart import DARTSource
from .fdr import FDRSource
from .kis import KISSource
from .naver import NaverSource

__all__ = [
    "DARTSource",
    "FDRSource",
    "KISSource",
    "NaverSource",
]
