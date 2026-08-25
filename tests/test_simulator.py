import pytest
from ingestion_service import MaritimeSimulator
from models import AISVesselRecord


def test_simulator_initialization():
    simulator = MaritimeSimulator()
    assert len(simulator.vessels) >= 6


def test_simulator_generate_tick():
    simulator = MaritimeSimulator()
    records = simulator.generate_tick(delta_seconds=1.0)

    assert len(records) == len(simulator.vessels)
    for rec in records:
        assert isinstance(rec, AISVesselRecord)
        assert rec.mmsi is not None
        assert rec.vessel_name is not None
        assert -90.0 <= rec.latitude <= 90.0
        assert -180.0 <= rec.longitude <= 180.0
        assert 0.0 <= rec.speed_knots <= 60.0


def test_vessel_kinematic_movement():
    simulator = MaritimeSimulator()
    vessel = simulator.vessels[0]

    initial_lat, initial_lon = vessel.latitude, vessel.longitude

    # Advance time by 10 seconds
    simulator.generate_tick(delta_seconds=10.0)

    # Coordinates should shift if vessel is underway
    if vessel.nav_status == "Underway using engine" and vessel.speed_knots > 0:
        assert (vessel.latitude, vessel.longitude) != (initial_lat, initial_lon)
