"""
Maritime Feature Engineering Pipeline
Computes spatial metrics, kinematics, queue densities, and temporal features
for Port Dwell Time regression and Maritime Anomaly detection.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Moroccan Strategic Maritime Hub Coordinates
PORT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "MAPTM": (35.8860, -5.5030),  # Tanger Med Hub
    "MACAS": (33.6060, -7.6070),  # Casablanca Port
}

# Standard Vessel Type Encodings
VESSEL_TYPE_ENCODING: Dict[str, int] = {
    "container ship": 0,
    "containership": 0,
    "container": 0,
    "crude oil tanker": 1,
    "oil tanker": 1,
    "tanker": 1,
    "chemical tanker": 2,
    "bulk carrier": 3,
    "bulk": 3,
    "cargo": 4,
    "general cargo": 4,
    "passenger ferry": 5,
    "ferry": 5,
    "passenger": 5,
    "ro-ro cargo": 6,
    "ro-ro": 6,
    "fishing vessel": 7,
    "fishing": 7,
    "tug": 8,
    "tugboat": 8,
    "other": 9,
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two WGS84 geographic coordinates in kilometers.
    """
    r_earth = 6371.0  # Earth's radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return float(r_earth * c)


def corridor_distance_offset_km(lat: float, lon: float) -> float:
    """
    Calculates spatial offset (in km) from authorized Gibraltar TSS shipping lane.
    Centerline spans approximately from 35.9500N, -5.8500W to 35.9500N, -5.3000W.
    """
    center_lat = 35.9500
    clamped_lon = max(-5.8500, min(-5.3000, lon))
    return haversine_distance_km(lat, lon, center_lat, clamped_lon)


def compute_heading_deviation(heading: Optional[float], cog: Optional[float] = None) -> float:
    """
    Calculates absolute angular deviation between reported heading and course over ground / expected heading.
    Returns normalized deviation in degrees [0.0, 180.0].
    """
    h = float(heading or 0.0)
    c = float(cog if cog is not None else h)
    diff = abs(h - c) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return float(diff)


def encode_vessel_type(vessel_type: Optional[str]) -> int:
    """
    Encodes vessel type string to numeric category index.
    """
    if not vessel_type:
        return VESSEL_TYPE_ENCODING["other"]
    key = str(vessel_type).strip().lower()
    return VESSEL_TYPE_ENCODING.get(key, VESSEL_TYPE_ENCODING["other"])


def compute_port_queue_density(
    vessels: List[Dict[str, Any]],
    port_code: str = "MAPTM",
    radius_km: float = 15.0,
) -> int:
    """
    Calculates dynamic count of vessels currently within the port's anchorage buffer (15km).
    """
    port_coords = PORT_COORDINATES.get(port_code, PORT_COORDINATES["MAPTM"])
    p_lat, p_lon = port_coords
    count = 0

    for v in vessels:
        try:
            v_lat = float(v.get("latitude", 0.0))
            v_lon = float(v.get("longitude", 0.0))
            dist = haversine_distance_km(v_lat, v_lon, p_lat, p_lon)
            speed = float(v.get("speed_knots", 0.0))
            status = str(v.get("nav_status", "")).lower()
            if dist <= radius_km and (speed < 3.5 or "anchor" in status or "moored" in status):
                count += 1
        except Exception:
            continue

    return count


def extract_dwell_features(
    record: Dict[str, Any],
    port_queue_density_map: Optional[Dict[str, int]] = None,
) -> Dict[str, float]:
    """
    Extracts engineered features for the Port Dwell Time & Congestion Predictor (XGBoost).
    Features:
    - vessel_type_encoded
    - current_speed
    - distance_to_port_km
    - port_queue_density
    - hour_of_day
    - day_of_week
    """
    lat = float(record.get("latitude", 35.8860))
    lon = float(record.get("longitude", -5.5030))
    speed = float(record.get("speed_knots", 0.0))
    v_type = record.get("vessel_type", "Cargo")
    port_code = record.get("port_code") or ("MAPTM" if lat > 35.0 else "MACAS")

    # Target port coordinates
    target_port = PORT_COORDINATES.get(port_code, PORT_COORDINATES["MAPTM"])
    dist_to_port = haversine_distance_km(lat, lon, target_port[0], target_port[1])

    # Dynamic or provided queue density
    if port_queue_density_map and port_code in port_queue_density_map:
        queue_density = float(port_queue_density_map[port_code])
    else:
        queue_density = float(record.get("port_queue_density", 4.0))

    # Timestamp extraction
    ts_val = record.get("timestamp_utc")
    if isinstance(ts_val, str):
        try:
            dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    elif isinstance(ts_val, datetime):
        dt = ts_val
    else:
        dt = datetime.now(timezone.utc)

    hour_of_day = float(dt.hour)
    day_of_week = float(dt.weekday())
    v_encoded = float(encode_vessel_type(v_type))

    return {
        "vessel_type_encoded": v_encoded,
        "current_speed": speed,
        "distance_to_port_km": dist_to_port,
        "port_queue_density": queue_density,
        "hour_of_day": hour_of_day,
        "day_of_week": day_of_week,
    }


def extract_anomaly_features(
    record: Dict[str, Any],
    prev_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Extracts engineered kinematic & navigational features for Isolation Forest Anomaly Detection.
    Features:
    - speed_knots
    - speed_delta (rolling acceleration / abrupt change)
    - heading_deviation (difference between heading and course vector)
    - corridor_distance_offset (distance from authorized Gibraltar TSS lane)
    """
    lat = float(record.get("latitude", 35.9500))
    lon = float(record.get("longitude", -5.5500))
    speed = float(record.get("speed_knots", 0.0))
    heading = float(record.get("heading") or 0.0)

    # Rolling acceleration / speed delta
    if prev_record and "speed_knots" in prev_record:
        prev_speed = float(prev_record["speed_knots"])
        speed_delta = abs(speed - prev_speed)
    else:
        speed_delta = float(record.get("speed_delta", 0.0))

    # Heading deviation
    cog = record.get("course_over_ground") or record.get("cog")
    heading_dev = compute_heading_deviation(heading, float(cog) if cog is not None else None)

    # Offset from Gibraltar TSS shipping channel
    corridor_offset = corridor_distance_offset_km(lat, lon)

    return {
        "speed_knots": speed,
        "speed_delta": speed_delta,
        "heading_deviation": heading_dev,
        "corridor_distance_offset": corridor_offset,
    }
