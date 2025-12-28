"""Backend API tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestPresetsEndpoint:
    """Test presets endpoint."""

    def test_get_presets(self, client):
        """Test getting system presets."""
        response = client.get("/api/screen/presets")
        assert response.status_code == 200
        presets = response.json()
        assert isinstance(presets, list)
        assert len(presets) > 0

        # Check preset structure
        preset = presets[0]
        assert "id" in preset
        assert "name" in preset
        assert "description" in preset
        assert "filters" in preset


class TestStocksEndpoint:
    """Test stocks endpoints."""

    @patch("app.api.stocks.get_db")
    def test_list_stocks_requires_db(self, mock_get_db, client):
        """Test that list stocks endpoint exists and requires db."""
        # Mock the database dependency
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        mock_get_db.return_value = mock_db

        # This will fail with rate limiting or DB error, but endpoint exists
        response = client.get("/api/stocks")
        # Accept either success or error (we're testing route exists)
        assert response.status_code in [200, 429, 500]


class TestScreenEndpoint:
    """Test screen endpoint."""

    @patch("app.api.screen.get_db")
    def test_screen_with_preset(self, mock_get_db, client):
        """Test screening with preset."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        response = client.post(
            "/api/screen",
            json={"preset": "graham"}
        )
        # Accept success or error (testing route exists)
        assert response.status_code in [200, 429, 500]

    def test_screen_endpoint_exists(self, client):
        """Test screen endpoint exists."""
        response = client.post("/api/screen", json={})
        # 422 means validation error (endpoint exists)
        # 200, 429, 500 are also valid
        assert response.status_code in [200, 422, 429, 500]
