"""KR (Korea) stock data collection pipeline.

Simple pipeline optimized for FDR + Naver + KIS data sources.
No complex rate limiting needed - focus on timeout management.

Usage:
    from kr import KRPipeline, KRConfig, collect_kr

    # Quick usage
    result, data = await collect_kr(tickers=["005930", "000660"])

    # Custom config
    config = KRConfig(fdr_timeout=15.0)
    pipeline = KRPipeline(config=config)
    result, data = await pipeline.run(tickers)
"""

from .config import KRConfig
from .pipeline import KRPipeline, collect_kr

__all__ = [
    "KRConfig",
    "KRPipeline",
    "collect_kr",
]
