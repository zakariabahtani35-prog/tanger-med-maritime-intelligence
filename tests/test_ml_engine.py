"""
Unit & Integration Tests for Maritime AI / ML Engines
Tests Feature Engineering, XGBoost Dwell Predictor, Isolation Forest Anomaly Detection,
and Real-time Inference Pipeline.
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from ml_engine.feature_engineering import (
    haversine_distance_km,
    corridor_distance_offset_km,
    compute_heading_deviation,
    compute_port_queue_density,
    encode_vessel_type,
    extract_dwell_features,
    extract_anomaly_features,
)
from ml_engine.train_dwell_model import train_dwell_predictor
from ml_engine.train_anomaly_model import train_anomaly_detector
from ml_engine.inference_service import MaritimeMLInferenceService


def test_haversine_distance():
    # Distance between Tanger Med and Casablanca Port (~318 km)
    dist = haversine_distance_km(35.8860, -5.5030, 33.6060, -7.6070)
    assert 300.0 < dist < 340.0

    # Same point should be zero distance
    assert haversine_distance_km(35.8860, -5.5030, 35.8860, -5.5030) == 0.0


def test_corridor_distance_offset():
    # Point directly on Gibraltar TSS centerline (35.95, -5.55) -> 0 offset
    offset_zero = corridor_distance_offset_km(35.9500, -5.5500)
    assert offset_zero < 0.1

    # Point 0.1 degree north (~11 km)
    offset_north = corridor_distance_offset_km(36.0500, -5.5500)
    assert 10.0 < offset_north < 13.0


def test_heading_deviation():
    # Same heading
    assert compute_heading_deviation(90.0, 90.0) == 0.0

    # 45 degrees
    assert compute_heading_deviation(90.0, 135.0) == 45.0

    # Wrap-around: 10 deg vs 350 deg -> 20 deg
    assert compute_heading_deviation(10.0, 350.0) == 20.0


def test_queue_density():
    vessels = [
        {"latitude": 35.8860, "longitude": -5.5030, "speed_knots": 0.2, "nav_status": "Moored"},
        {"latitude": 35.8900, "longitude": -5.5100, "speed_knots": 1.0, "nav_status": "At anchor"},
        {"latitude": 34.0000, "longitude": -6.5000, "speed_knots": 18.0, "nav_status": "Underway"},
    ]
    density_tm = compute_port_queue_density(vessels, port_code="MAPTM", radius_km=15.0)
    assert density_tm == 2


def test_dwell_model_training_and_inference():
    results = train_dwell_predictor(save_artifact=True)
    assert results["model"] is not None
    assert results["r2"] > 0.65
    assert results["rmse"] < 6.0


def test_anomaly_model_training_and_inference():
    results = train_anomaly_detector(save_artifact=True)
    assert results["model"] is not None
    assert results["min_score"] < results["max_score"]


def test_inference_service_batch_scoring():
    service = MaritimeMLInferenceService()
    assert service.load_models() is True

    test_movements = [
        {
            "mmsi": "228389000",
            "vessel_name": "CMA CGM JACQUES SAADE",
            "vessel_type": "Container Ship",
            "latitude": 35.9489,
            "longitude": -5.8405,
            "speed_knots": 22.5,
            "heading": 98.0,
            "port_code": "MAPTM",
            "nav_status": "Underway using engine",
        },
        {
            "mmsi": "999000111",
            "vessel_name": "ANOMALOUS DRIFTER",
            "vessel_type": "Cargo",
            "latitude": 36.2500,  # Far off lane
            "longitude": -5.5000,
            "speed_knots": 1.2,  # Standstill
            "heading": 290.0,
            "port_code": "MAPTM",
            "nav_status": "Underway",
        },
    ]

    scored = service.predict_batch(test_movements)
    assert len(scored) == 2
    for s in scored:
        assert "predicted_dwell_hours" in s
        assert "anomaly_score" in s
        assert "is_anomaly" in s
        assert 0.0 <= s["anomaly_score"] <= 1.0
        assert s["predicted_dwell_hours"] > 0.0

    # Summary generation
    summary = service.get_ai_summary(scored)
    assert summary["total_scored_vessels"] == 2
    assert "anomalous_vessel_count" in summary
    assert "tanger_med_predicted_dwell_avg" in summary


def test_ai_api_endpoints():
    client = TestClient(app)

    # 1. AI Summary Endpoint
    summary_res = client.get("/api/v1/ai/summary")
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert "anomalous_vessel_count" in s_data
    assert "tanger_med_predicted_dwell_avg" in s_data
    assert "status" in s_data

    # 2. AI Anomalies Endpoint
    anom_res = client.get("/api/v1/ai/anomalies")
    assert anom_res.status_code == 200
    assert isinstance(anom_res.json(), list)

    # 3. Radar Positions contain AI inference tags
    radar_res = client.get("/api/v1/radar/positions")
    assert radar_res.status_code == 200
    positions = radar_res.json()
    if positions:
        first = positions[0]
        assert "predicted_dwell_hours" in first
        assert "anomaly_score" in first
        assert "is_anomaly" in first
