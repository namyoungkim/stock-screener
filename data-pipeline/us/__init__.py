"""US stock data collection pipeline.

Rate-limit-aware pipeline optimized for yfinance data source.
Includes Circuit Breaker, Token Bucket Rate Limiter, and retry logic.

Usage:
    from us import USPipeline, USConfig, collect_us

    # Quick usage
    result, data = await collect_us(tickers=["AAPL", "MSFT"])

    # Custom config
    config = USConfig(price_batch_size=100)
    pipeline = USPipeline(config=config)
    result, data = await pipeline.run(tickers)
"""

from .config import USConfig
from .pipeline import USPipeline, collect_us

__all__ = [
    "USConfig",
    "USPipeline",
    "collect_us",
]
