"""Stock data collectors.

New architecture using BaseCollector pattern with dependency injection.
"""

from .base import BaseCollector, CollectionPhase, CollectionResult
from .kr_collector import NewKRCollector, create_kr_collector
from .us_collector import NewUSCollector, create_us_collector

__all__ = [
    # Base
    "BaseCollector",
    "CollectionPhase",
    "CollectionResult",
    # US
    "NewUSCollector",
    "create_us_collector",
    # KR
    "NewKRCollector",
    "create_kr_collector",
]
