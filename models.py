import re
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from config import settings


# Standard Vessel Types mapping
VESSEL_TYPE_MAP = {
    "container": "Container Ship",
    "containership": "Container Ship",
    "tanker": "Crude Oil Tanker",
    "crude oil tanker": "Crude Oil Tanker",
    "chemical tanker": "Chemical Tanker",
    "oil/chemical tanker": "Chemical Tanker",
    "bulk": "Bulk Carrier",
    "bulk carrier": "Bulk Carrier",
    "cargo": "Cargo",
    "general cargo": "Cargo",
    "tug": "Tug",
    "tugboat": "Tug",
    "towing": "Tug",
    "passenger": "Passenger Ferry",
    "ferry": "Passenger Ferry",
    "ro-ro": "Ro-Ro Cargo",
    "ro-ro cargo": "Ro-Ro Cargo",
    "fishing": "Fishing Vessel",
}

# Standard Navigation Statuses mapping
NAV_STATUS_MAP = {
    "0": "Underway using engine",
    "1": "At anchor",
    "2": "Not under command",
    "3": "Restricted manoeuvrability",
    "4": "Constrained by her draught",
    "5": "Moored",
    "6": "Aground",
    "7": "Engaged in fishing",
    "8": "Under way sailing",
    "underway using engine": "Underway using engine",
    "at anchor": "At anchor",
    "moored": "Moored",
    "restricted manoeuvrability": "Restricted manoeuvrability",
}


class AISVesselRecord(BaseModel):
    """
    Validated & Normalized AIS Vessel Record targeting staging.stg_vessel_ais_raw
    """

    mmsi: str = Field(..., description="Maritime Mobile Service Identity (9 digits)")
    imo: Optional[str] = Field(None, description="IMO Number (7 digits if present)")
    vessel_name: str = Field(..., description="Name of the vessel")
    vessel_type: str = Field(default="Cargo", description="Standardized vessel category")
    flag_country: str = Field(default="Unknown", description="Vessel flag state")
    latitude: float = Field(..., description="Latitude in WGS84 (-90.0 to 90.0)")
    longitude: float = Field(..., description="Longitude in WGS84 (-180.0 to 180.0)")
    speed_knots: float = Field(..., description="Speed Over Ground in Knots (0.0 to 60.0)")
    heading: Optional[float] = Field(None, description="True Heading / COG in Degrees (0.0 to 360.0)")
    nav_status: str = Field(default="Underway using engine", description="Navigational Status")
    destination: Optional[str] = Field(None, description="Reported destination port")
    eta: Optional[datetime] = Field(None, description="Estimated Time of Arrival in UTC")
    timestamp_utc: datetime = Field(..., description="Telemetry timestamp in UTC")

    @field_validator("mmsi", mode="before")
    @classmethod
    def validate_mmsi(cls, v: str | int) -> str:
        s = str(v).strip()
        cleaned = re.sub(r"[^\d]", "", s)
        if not (5 <= len(cleaned) <= 12):
            raise ValueError(f"Invalid MMSI format: {v}")
        return cleaned

    @field_validator("imo", mode="before")
    @classmethod
    def validate_imo(cls, v: Optional[str | int]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        cleaned = re.sub(r"[^\d]", "", s)
        if not cleaned or cleaned == "0":
            return None
        return f"IMO{cleaned}" if not cleaned.startswith("IMO") else cleaned

    @field_validator("vessel_name", mode="before")
    @classmethod
    def clean_vessel_name(cls, v: str) -> str:
        if not v or not str(v).strip():
            return "UNKNOWN_VESSEL"
        return str(v).strip().upper()

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude out of WGS84 bounds: {v}")
        return round(float(v), 6)

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude out of WGS84 bounds: {v}")
        return round(float(v), 6)

    @field_validator("speed_knots")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        val = float(v)
        if val < 0.0:
            val = 0.0
        if val > 60.0:
            raise ValueError(f"Speed exceeds realistic maritime threshold (60 kts): {v}")
        return round(val, 2)

    @field_validator("heading")
    @classmethod
    def validate_heading(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        val = float(v)
        if val == 511.0 or val < 0.0 or val > 360.0:
            return None
        return round(val, 2)

    @field_validator("vessel_type", mode="before")
    @classmethod
    def normalize_vessel_type(cls, v: Optional[str]) -> str:
        if not v:
            return "Cargo"
        raw = str(v).strip().lower()
        for key, std_name in VESSEL_TYPE_MAP.items():
            if key in raw:
                return std_name
        return str(v).strip().title()

    @field_validator("nav_status", mode="before")
    @classmethod
    def normalize_nav_status(cls, v: Optional[str | int]) -> str:
        if v is None:
            return "Underway using engine"
        raw = str(v).strip().lower()
        if raw in NAV_STATUS_MAP:
            return NAV_STATUS_MAP[raw]
        for key, std_status in NAV_STATUS_MAP.items():
            if key in raw:
                return std_status
        return str(v).strip().capitalize()

    @field_validator("destination", mode="before")
    @classmethod
    def clean_destination(cls, v: Optional[str]) -> Optional[str]:
        if not v or not str(v).strip():
            return None
        cleaned = str(v).strip().upper()
        return cleaned if cleaned != "UNKNOWN" else None

    @field_validator("timestamp_utc", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: str | datetime | int | float) -> datetime:
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        raise ValueError(f"Cannot parse timestamp: {v}")

    @property
    def is_in_moroccan_geofence(self) -> bool:
        """Returns True if vessel telemetry lies within targeted Moroccan waters."""
        return settings.is_in_moroccan_waters(self.latitude, self.longitude)
