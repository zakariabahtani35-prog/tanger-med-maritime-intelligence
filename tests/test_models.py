from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from models import AISVesselRecord


def test_valid_ais_vessel_record():
    record = AISVesselRecord(
        mmsi="228389000",
        imo="9839179",
        vessel_name="cma cgm jacques saade ",
        vessel_type="containership",
        flag_country="France",
        latitude=35.8900,
        longitude=-5.4800,
        speed_knots=18.5,
        heading=90.0,
        nav_status="0",
        destination="tanger med",
        timestamp_utc="2026-08-25T20:00:00Z",
    )

    assert record.mmsi == "228389000"
    assert record.imo == "IMO9839179"
    assert record.vessel_name == "CMA CGM JACQUES SAADE"
    assert record.vessel_type == "Container Ship"
    assert record.nav_status == "Underway using engine"
    assert record.latitude == 35.8900
    assert record.longitude == -5.4800
    assert record.speed_knots == 18.5
    assert record.destination == "TANGER MED"
    assert record.timestamp_utc.tzinfo == timezone.utc
    assert record.is_in_moroccan_geofence is True


def test_invalid_coordinates_latitude():
    with pytest.raises(ValidationError):
        AISVesselRecord(
            mmsi="228389000",
            vessel_name="TEST VESSEL",
            latitude=95.0,  # Out of bounds
            longitude=-5.4800,
            speed_knots=10.0,
            timestamp_utc=datetime.now(timezone.utc),
        )


def test_invalid_speed_bounds():
    with pytest.raises(ValidationError):
        AISVesselRecord(
            mmsi="228389000",
            vessel_name="TEST VESSEL",
            latitude=35.8900,
            longitude=-5.4800,
            speed_knots=75.0,  # Exceeds 60 kts threshold
            timestamp_utc=datetime.now(timezone.utc),
        )


def test_heading_sentinel_511():
    record = AISVesselRecord(
        mmsi="228389000",
        vessel_name="TEST VESSEL",
        latitude=35.8900,
        longitude=-5.4800,
        speed_knots=10.0,
        heading=511.0,  # Sentinel value in AIS
        timestamp_utc=datetime.now(timezone.utc),
    )
    assert record.heading is None


def test_casablanca_geofence_check():
    record = AISVesselRecord(
        mmsi="242555666",
        vessel_name="MAROC PHOSPHATE I",
        latitude=33.6100,
        longitude=-7.6000,
        speed_knots=12.0,
        timestamp_utc=datetime.now(timezone.utc),
    )
    assert record.is_in_moroccan_geofence is True


def test_out_of_bounds_geofence_check():
    record = AISVesselRecord(
        mmsi="123456789",
        vessel_name="ATLANTIC VOYAGER",
        latitude=40.7128,  # New York latitude
        longitude=-74.0060,
        speed_knots=15.0,
        timestamp_utc=datetime.now(timezone.utc),
    )
    assert record.is_in_moroccan_geofence is False
