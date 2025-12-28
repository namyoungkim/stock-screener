"""Backend API tests."""

from unittest.mock import MagicMock

import pytest
from app.core.database import get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """Create a mock database client."""
    mock = MagicMock()
    # Setup default return values
    mock.table.return_value.select.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.execute.return_value.count = 0
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.range.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def client(mock_db):
    """Create test client with mocked database."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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

    def test_list_stocks(self, client, mock_db):
        """Test list stocks endpoint."""
        # Setup mock response
        mock_db.table.return_value.select.return_value.range.return_value.execute.return_value.data = []
        mock_db.table.return_value.select.return_value.range.return_value.execute.return_value.count = 0

        response = client.get("/api/stocks")
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert "total" in data


class TestScreenEndpoint:
    """Test screen endpoint."""

    def test_screen_with_preset(self, client, mock_db):
        """Test screening with preset."""
        # Setup mock response
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        mock_db.table.return_value.select.return_value.execute.return_value.count = 0

        response = client.post("/api/screen", json={"preset": "graham"})
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert "total" in data

    def test_screen_endpoint_validation(self, client):
        """Test screen endpoint validates input."""
        response = client.post("/api/screen", json={})
        # 200 is valid (empty filters)
        assert response.status_code == 200
