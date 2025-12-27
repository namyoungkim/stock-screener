"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance
limiter = Limiter(key_func=get_remote_address)

# Rate limit configurations
RATE_LIMITS = {
    "default": "100/minute",  # General API calls
    "screen": "30/minute",    # Screening (heavier operation)
    "auth": "10/minute",      # Auth-related endpoints
}
