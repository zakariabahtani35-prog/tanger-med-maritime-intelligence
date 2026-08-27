import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_landing_portal_route():
    """Verify that root / serves the HTML presentation landing page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Morocco Maritime" in response.text
    assert "text/html" in response.headers["content-type"]


def test_dashboard_route():
    """Verify that /dashboard serves the analytics dashboard."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Morocco" in response.text or "MOROCCO" in response.text
    assert "text/html" in response.headers["content-type"]


def test_live_telemetry_api():
    """Verify that /api/telemetry/live returns vessel telemetry list."""
    response = client.get("/api/telemetry/live")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "mmsi" in data[0]
        assert "vessel_name" in data[0]
        assert "latitude" in data[0]
        assert "longitude" in data[0]


def test_metrics_summary_api():
    """Verify that /api/metrics/summary returns real-time pipeline KPIs."""
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    metrics = response.json()
    assert "active_vessel_count" in metrics
    assert "tanger_med" in metrics
    assert "casablanca" in metrics
    assert "pipeline_latency_seconds" in metrics


def test_geofences_api():
    """Verify that /api/geofences returns configured PostGIS bounding boxes."""
    response = client.get("/api/geofences")
    assert response.status_code == 200
    geofences = response.json()
    assert len(geofences) >= 2
    names = [gf["name"] for gf in geofences]
    assert any("Gibraltar" in n or "Tanger" in n for n in names)
    assert any("Casablanca" in n for n in names)


def test_health_endpoint():
    """Verify health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
