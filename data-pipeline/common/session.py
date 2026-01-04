"""Browser session utilities for yfinance to bypass TLS fingerprinting."""

from curl_cffi import requests


def create_browser_session() -> requests.Session:
    """Create a session that impersonates Chrome browser.

    This helps bypass TLS fingerprinting that Yahoo Finance uses to detect
    and rate-limit automated requests.

    Returns:
        A curl_cffi Session configured to impersonate Chrome.
    """
    return requests.Session(impersonate="chrome")
