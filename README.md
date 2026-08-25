# Morocco Maritime & Port Supply Chain Intelligence (Tanger Med & Casablanca Hubs)

A high-throughput, fault-tolerant Python data ingestion pipeline engineered for real-time AIS (Automatic Identification System) maritime telemetry ingestion across the North-Western Moroccan maritime corridor (Strait of Gibraltar, Tanger Med Port, and Casablanca Port approach).

---

## System Architecture & Data Flow

```
+---------------------------------------------------+
|               Maritime Source Layer               |
|  - Live AISStream WebSocket Feed (or)             |
|  - High-Fidelity Deterministic Maritime Simulator |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
|         Validation & Geofencing Engine            |
|  - Pydantic v2 Strong Typing & Normalization      |
|  - WGS84 & Speed Bounds Validation                |
|  - Moroccan Waters Bounding Box Check             |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
|              Async Ingestion Buffer               |
|  - asyncio.Queue Accumulator                      |
|  - Time-based & Size-based Batch Flush Controls   |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
|           PostgreSQL / PostGIS Warehouse          |
|  - asyncpg Bulk Copy/Insert                       |
|  - Target Table: staging.stg_vessel_ais_raw       |
+---------------------------------------------------+
```

---

## Target Database Schema: `staging.stg_vessel_ais_raw`

| Column | Type | Constraints / Details |
|---|---|---|
| `id` | UUID | Primary Key (`gen_random_uuid()`) |
| `mmsi` | VARCHAR(20) | NOT NULL (9-digit MMSI identifier) |
| `imo` | VARCHAR(20) | IMO Number (7-digit standard) |
| `vessel_name` | VARCHAR(150) | NOT NULL (Standardized Uppercase) |
| `vessel_type` | VARCHAR(50) | Standardized (e.g. Container Ship, Tanker, Tug) |
| `flag_country` | VARCHAR(50) | Flag State |
| `latitude` | NUMERIC(10, 6) | NOT NULL WGS84 (-90.0 to 90.0) |
| `longitude` | NUMERIC(10, 6) | NOT NULL WGS84 (-180.0 to 180.0) |
| `speed_knots` | NUMERIC(5, 2) | NOT NULL Speed Over Ground (SOG) |
| `heading` | NUMERIC(5, 2) | True Heading / Course Over Ground |
| `nav_status` | VARCHAR(50) | Standardized Navigational Status |
| `destination` | VARCHAR(100) | Reported destination port |
| `eta` | TIMESTAMP WITH TZ | Estimated Time of Arrival |
| `timestamp_utc` | TIMESTAMP WITH TZ | NOT NULL Telemetry Timestamp |
| `created_at` | TIMESTAMP WITH TZ | Default `NOW()` |

---

## Operational Regions & Geofencing Bounds

- **Strait of Gibraltar & Tanger Med Bounding Box**:
  - Latitude: `[35.7000, 36.1500]`
  - Longitude: `[-5.9000, -5.2000]`
- **Casablanca Port Approach**:
  - Latitude: `[33.5500, 33.7000]`
  - Longitude: `[-7.7000, -7.5000]`

---

## Quick Start & Installation

### 1. Prerequisites
- Python 3.10+
- PostgreSQL 14+ with PostGIS extension (Optional for local testing; runs in Dry-Run mode if DB is offline)

### 2. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and set your database connection parameters or AIS API key:
```bash
cp .env.example .env
```

### 4. Run Pipeline
```bash
python main.py
```

---

## Running Unit & Integration Tests

Execute the pytest test suite:
```bash
PYTHONPATH=. pytest -v tests/
```

---

## Key Modules

- [`config.py`](file:///home/zakaria-laptop/Morocco%20Port%20&%20Maritime%20Intelligence/config.py): Environment settings (`pydantic-settings`) and Moroccan geofence definitions.
- [`models.py`](file:///home/zakaria-laptop/Morocco%20Port%20&%20Maritime%20Intelligence/models.py): Pydantic v2 validation schema, data cleaning, and geofence spatial checker.
- [`database.py`](file:///home/zakaria-laptop/Morocco%20Port%20&%20Maritime%20Intelligence/database.py): Connection pool management (`asyncpg`), DDL schema initialization, and bulk insert engine with retry logic (`tenacity`).
- [`ingestion_service.py`](file:///home/zakaria-laptop/Morocco%20Port%20&%20Maritime%20Intelligence/ingestion_service.py): Live WebSocket consumer, High-Fidelity Maritime Simulator, and async queue buffer.
- [`main.py`](file:///home/zakaria-laptop/Morocco%20Port%20&%20Maritime%20Intelligence/main.py): Entrypoint, structured JSON logging (`structlog`), and signal handling (`SIGINT`/`SIGTERM`).
