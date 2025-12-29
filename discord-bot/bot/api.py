"""API client for the Stock Screener backend."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class APIClient:
    """HTTP client for Stock Screener API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_stocks(
        self,
        market: str | None = None,
        search: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get stocks list."""
        params = {"limit": limit}
        if market:
            params["market"] = market
        if search:
            params["search"] = search

        response = await self.client.get("/api/stocks", params=params)
        response.raise_for_status()
        return response.json()

    async def get_stock(self, ticker: str, market: str | None = None) -> dict[str, Any]:
        """Get stock details."""
        params = {}
        if market:
            params["market"] = market

        response = await self.client.get(f"/api/stocks/{ticker}", params=params)
        response.raise_for_status()
        return response.json()

    async def screen(
        self,
        preset: str | None = None,
        market: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Screen stocks."""
        payload = {"limit": limit}
        if preset:
            payload["preset"] = preset
        if market:
            payload["market"] = market

        response = await self.client.post("/api/screen", json=payload)
        response.raise_for_status()
        return response.json()

    async def get_presets(self) -> list[dict[str, Any]]:
        """Get available presets."""
        response = await self.client.get("/api/screen/presets")
        response.raise_for_status()
        return response.json()

    # ============================================
    # Discord Watchlist Methods
    # ============================================

    async def get_watchlist(self, discord_user_id: str) -> dict[str, Any]:
        """Get Discord user's watchlist."""
        headers = {"X-Discord-User-Id": discord_user_id}
        response = await self.client.get("/api/discord/watchlist", headers=headers)
        response.raise_for_status()
        return response.json()

    async def add_to_watchlist(
        self,
        discord_user_id: str,
        ticker: str,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Add stock to Discord user's watchlist."""
        headers = {"X-Discord-User-Id": discord_user_id}
        params = {"ticker": ticker}
        if market:
            params["market"] = market

        response = await self.client.post(
            "/api/discord/watchlist", headers=headers, params=params
        )
        response.raise_for_status()
        return response.json()

    async def remove_from_watchlist(
        self,
        discord_user_id: str,
        ticker: str,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Remove stock from Discord user's watchlist."""
        headers = {"X-Discord-User-Id": discord_user_id}
        params = {}
        if market:
            params["market"] = market

        response = await self.client.delete(
            f"/api/discord/watchlist/{ticker}", headers=headers, params=params
        )
        response.raise_for_status()
        return response.json()

    # ============================================
    # Discord Alert Methods
    # ============================================

    async def get_alerts(
        self,
        discord_user_id: str,
        active_only: bool = False,
    ) -> dict[str, Any]:
        """Get Discord user's alerts."""
        headers = {"X-Discord-User-Id": discord_user_id}
        params = {"active_only": str(active_only).lower()}
        response = await self.client.get(
            "/api/discord/alerts", headers=headers, params=params
        )
        response.raise_for_status()
        return response.json()

    async def create_alert(
        self,
        discord_user_id: str,
        ticker: str,
        metric: str,
        operator: str,
        value: float,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Discord alert."""
        headers = {"X-Discord-User-Id": discord_user_id}
        params = {"ticker": ticker}
        if market:
            params["market"] = market

        # company_id will be resolved by the API from ticker
        payload = {
            "company_id": "00000000-0000-4000-8000-000000000000",  # Placeholder
            "metric": metric,
            "operator": operator,
            "value": value,
        }

        response = await self.client.post(
            "/api/discord/alerts", headers=headers, params=params, json=payload
        )
        response.raise_for_status()
        return response.json()

    async def delete_alert(
        self,
        discord_user_id: str,
        alert_id: str,
    ) -> dict[str, Any]:
        """Delete a Discord alert."""
        headers = {"X-Discord-User-Id": discord_user_id}
        response = await self.client.delete(
            f"/api/discord/alerts/{alert_id}", headers=headers
        )
        response.raise_for_status()
        return response.json()

    async def toggle_alert(
        self,
        discord_user_id: str,
        alert_id: str,
    ) -> dict[str, Any]:
        """Toggle Discord alert active status."""
        headers = {"X-Discord-User-Id": discord_user_id}
        response = await self.client.post(
            f"/api/discord/alerts/{alert_id}/toggle", headers=headers
        )
        response.raise_for_status()
        return response.json()


api_client = APIClient()
