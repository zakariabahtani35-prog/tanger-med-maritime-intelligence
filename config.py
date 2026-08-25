from typing import NamedTuple, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class BoundingBox(NamedTuple):
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


# Operational Geofences for North-Western Moroccan Maritime Corridor
GEOFENCES: List[BoundingBox] = [
    BoundingBox(
        name="Strait of Gibraltar & Tanger Med",
        min_lat=35.7000,
        max_lat=36.1500,
        min_lon=-5.9000,
        max_lon=-5.2000,
    ),
    BoundingBox(
        name="Casablanca Port Approach",
        min_lat=33.5500,
        max_lat=33.7000,
        min_lon=-7.7000,
        max_lon=-7.5000,
    ),
]


class Settings(BaseSettings):
    """
    Application Settings for Morocco Maritime Telemetry Ingestion Pipeline.
    Operates natively via Supabase Python SDK.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Supabase Connection Settings
    supabase_url: str = "https://syaigxflutyefwszxpsr.supabase.co"
    supabase_service_role_key: Optional[str] = None
    supabase_key: Optional[str] = None  # Fallback anon or service key
    target_table: str = "stg_vessel_ais_raw"

    # Batch Ingestion Parameters
    batch_size: int = 100
    flush_interval_seconds: float = 5.0

    # Ingestion Source Mode
    simulation_mode: bool = True
    ais_websocket_url: str = "wss://stream.aisstream.io/v0/stream"
    ais_api_key: Optional[str] = None

    # Geofence Filtering Settings
    strict_geofence_check: bool = True

    # Telemetry Ingestion Rate Limit / Delay for Simulation (seconds between ticks)
    simulator_tick_interval: float = 0.5

    # Structured Logging Level
    log_level: str = "INFO"

    @property
    def effective_supabase_key(self) -> Optional[str]:
        return self.supabase_service_role_key or self.supabase_key

    @property
    def is_in_moroccan_waters(self) -> callable:
        def check(lat: float, lon: float) -> bool:
            return any(box.contains(lat, lon) for box in GEOFENCES)

        return check


# Global singleton instance
settings = Settings()
