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


api_client = APIClient()
