# Morocco Port & Maritime Intelligence — Architectural Audit & Execution Breakdown (`ana.md`)

---

## Executive Summary

The **Morocco Port & Maritime Intelligence Platform** is a high-throughput, real-time maritime telemetry ingestion, spatial geofencing, ML analytics, and presentation platform. It is engineered specifically for North-Western Moroccan maritime corridors, including **Tanger Med 1 & 2**, **Casablanca Port Approach**, and the **Strait of Gibraltar Traffic Separation Scheme (TSS)**.

This document serves as the authoritative architectural audit detailing data lifecycles, configuration root-cause analysis, component relationships, machine learning inference loops, and operational troubleshooting.

---

## 1. Data Processing Architecture & Dual Lifecycle

The system operates on a **hybrid real-time stream + batch storage architecture**. Telemetry is ingested in real time, validated and geofenced in memory, buffered into micro-batches, and persisted to Supabase (with automatic fallback to an in-memory relational warehouse store).

```
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                                STREAMING SOURCE                                 │
 │  Real-time AIS Stream (wss://stream.aisstream.io) OR Kinematic Simulator Tick    │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                               PYDANTIC VALIDATION                                │
 │               AISVesselRecord (MMSI, WGS84 Coords, SOG, COG, Heading)           │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                               SPATIAL GEOFENCING                                 │
 │         BoundingBox Filtering (Tanger Med: 35.7-36.15N / Casablanca: 33.55-33.7N)  │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                         BATCH BUFFERING & WAREHOUSING                            │
 │   Micro-batch Queue (Size: 100, Flush: 5.0s) ──► Supabase / WarehouseInMemoryStore │
 └───────────────────┬──────────────────────────────────────────────┬───────────────┘
                     │                                              │
                     ▼                                              ▼
 ┌───────────────────────────────────────┐      ┌───────────────────────────────────┐
 │       REAL-TIME ML INFERENCE WORKER   │      │        FASTAPI PRESENTATION       │
 │ - XGBoost Regressor (Port Dwell)      │      │ - REST API (/api/v1/radar/...)    │
 │ - Isolation Forest (Anomalies)        │      │ - WebSocket (/ws/telemetry)       │
 │ Updates fact_vessel_movements (2.5s)  │      │ - Interactive Leaflet Dashboard   │
 └───────────────────────────────────────┘      └───────────────────────────────────┘
```

---

### 1.1 Data Processing Flow Breakdown

#### A. Stream Path (Ingestion & Geofencing)
1. **Source Connection**: `AISIngestionService` in `ingestion_service.py` connects to either:
   - **Production Mode**: External WebSocket stream `wss://stream.aisstream.io/v0/stream` (Message Type `PositionReport`).
   - **Simulation Mode**: Internal kinematic state engine (`SimulatedVessel`) updating vessel positions along realistic maritime waypoints across the Strait of Gibraltar and Moroccan coast every `0.5s`.
2. **Pydantic Validation**: Incoming JSON payloads are parsed into `AISVesselRecord` dataclasses in `models.py`, ensuring strict typing and valid coordinate bounds.
3. **Geofence Filtering**: Coordinates are evaluated against operational bounding boxes in `config.py` (`GEOFENCES`):
   - **Strait of Gibraltar & Tanger Med**: `35.7000°N - 36.1500°N`, `-5.9000°W - -5.2000°W`
   - **Casablanca Port Approach**: `33.5500°N - 33.7000°N`, `-7.7000°W - -7.5000°W`
4. **Batch Buffer & Ingestion**: Valid records enter a thread-safe async queue buffer (`_batch_queue`). When the buffer reaches `batch_size` (100 records) or `flush_interval_seconds` (5.0s), `db_manager.ingest_batch()` flushes records to the data store.

---

#### B. ML Inference Path (Background Analytics Worker)
1. **Asynchronous Inference Loop**: `ml_inference_service.start_inference_worker()` runs continuously as a background `asyncio` task in `app.py` (executing every `2.5s`).
2. **Feature Extraction**: `feature_engineering.py` extracts kinematic and spatial features from recent vessel records:
   - Current speed over ground (SOG) & heading change rate.
   - Distance to nearest port terminal (Tanger Med or Casablanca).
   - Port anchorage queue density.
   - Temporal features (hour of day, day of week).
3. **Model Prediction**:
   - **Port Dwell Predictor (`XGBoost Regressor`)**: Predicts expected berth/anchorage dwell time in hours (`predicted_dwell_hours`).
   - **Anomaly Detector (`Isolation Forest`)**: Computes kinematic anomaly scores (`anomaly_score`) and sets `is_anomaly=True` if the score exceeds threshold `0.65`.
4. **Warehouse Update**: Predictions are written back directly into `fact_vessel_movements` in real time, making them instantly queryable.

---

#### C. Dashboard Delivery Path
- **How `/dashboard` gets data**:
  - `/dashboard` serves `templates/dashboard.html`.
  - The client-side Leaflet.js map makes periodic polling requests to `/api/v1/radar/positions`, `/api/v1/vessels/active`, `/api/v1/ports/congestion`, and `/api/v1/ai/summary`.
  - In addition, real-time kinematics are broadcast to active WebSocket clients connected to `/ws/telemetry`.
  - **Data Source**: The endpoints read from `db_manager`. If Supabase is connected, it executes SQL queries against `public.fact_vessel_movements` and `public.dim_vessels`. If Supabase is not configured or offline, `db_manager` reads seamlessly from `WarehouseInMemoryStore` (in-memory relational store), ensuring zero downtime.

---

## 2. Configuration Root Cause Analysis: Why the App Runs With a Blank `.env`

### 2.1 Root Cause Explanation

The project uses `pydantic-settings` via `class Settings(BaseSettings)` in `config.py`.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str = "https://syaigxflutyefwszxpsr.supabase.co"
    supabase_service_role_key: Optional[str] = None
    supabase_key: Optional[str] = None
    simulation_mode: bool = True
    ...
```

### 2.1 Environment Hardening & Strict Production Enforcement

To ensure zero architectural ambiguity and prevent silent mock fallbacks:
1. **Explicit `.env` Loading**: `config.py` uses `dotenv.find_dotenv(usecwd=True)` and `load_dotenv()` to guarantee that environment variables are loaded directly from `.env` prior to instantiating application settings.
2. **Fail Fast (No Silent Mock Fallback)**:
   - When `database.py` initializes `db_manager.init_client()`, `settings.validate_strict_production_config()` is executed.
   - If `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_KEY` is missing, empty, or set to placeholder strings (e.g., `your_service_role_key_here`, `your_anon_key_here`), the application logs a `critical` `STRICT_SUPABASE_ENV_FAILURE` error and raises a `RuntimeError`, halting startup immediately.
   - If Supabase REST connection initialization fails, `database.py` logs `SUPABASE_CONNECTION_FAILURE` and raises `RuntimeError`, preventing silent in-memory fallback.

---

### 2.2 Production `.env` File Configuration

The persisted `.env` file at the repository root contains:

```ini
SUPABASE_URL=https://syaigxflutyefwszxpsr.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
SUPABASE_KEY=your_anon_key_here
TARGET_TABLE=stg_vessel_ais_raw
SIMULATION_MODE=false
LOG_LEVEL=INFO
```
*(To bring the server online in production, replace `your_service_role_key_here` and `your_anon_key_here` with your actual Supabase PostgreSQL API keys).*

---

## 3. End-to-End Component Map

| Component Directory / File | Type / Responsibility | Key Functions & Interactions |
| :--- | :--- | :--- |
| **`portal/index.html`** | Presentation Portal | Landing page branded with official BY Logo Identity (`#010101`, `#9E261A`). Contains CTAs routing users to `/dashboard`. |
| **`portal/style.css`** | Design Token System | Centralized CSS custom properties (`--brand-black`, `--brand-red`, `--brand-white`, etc.), buttons, nav, hero, bento cards, footer. |
| **`portal/script.js`** | Client Interactions | Header scroll shadow effects, smooth anchor scrolling, FAQ accordions, mobile drawer navigation toggle. |
| **`templates/dashboard.html`** | Live Analytics Dashboard | Single-page Leaflet.js interactive geospatial map, port dwell metrics, vessel fleet table, AI anomaly feeds, WebSocket listener. |
| **`app.py`** | Application Server | FastAPI application setup. Mounts static files, serves presentation routes (`/` and `/dashboard`), REST endpoints, WebSocket `/ws/telemetry`, and background lifespan worker tasks. |
| **`config.py`** | Configuration & Geofences | Pydantic `Settings` loader, bounding box definitions (`GEOFENCES`) for Tanger Med and Casablanca, environmental defaults. |
| **`database.py`** | Data Access Layer | `SupabaseDatabaseManager` handling Supabase REST queries, retry logic via `tenacity`, and `WarehouseInMemoryStore` fallback. |
| **`ingestion_service.py`** | Telemetry Ingestion Engine | `AISIngestionService` managing live WebSocket connections or running `SimulatedVessel` kinematic state calculations and batch queuing. |
| **`models.py`** | Dataclasses & Schemas | `AISVesselRecord` Pydantic models for validation, dictionary conversions, and database mapping. |
| **`ml_engine/feature_engineering.py`** | Feature Extraction | Derives distance to port, queue density, heading rates, and SOG vectors for machine learning models. |
| **`ml_engine/inference_service.py`** | AI Inference Worker | `MaritimeMLInferenceService` loading XGBoost Regressor (`dwell_model.joblib`) and Isolation Forest (`anomaly_model.joblib`) to update live predictions. |
| **`ml_engine/train_*.py`** | Model Training | Automated training scripts for dwell time prediction and kinematic anomaly detection. |

---

## 4. Operational Bug Fix: Port 8000 Conflict (`[Errno 98 Address already in use]`)

When restarting `app.py`, Linux may throw `[Errno 98] Address already in use` if a background process or zombie Uvicorn instance is holding Port 8000.

### Quick Terminal Fix Commands

#### Method 1: Kill via `fuser` (Recommended)
```bash
# Force kill any process listening on TCP port 8000
sudo fuser -k 8000/tcp
```

#### Method 2: Kill via `lsof` + `kill`
```bash
# Find Process ID (PID) on port 8000 and terminate forcefully
kill -9 $(lsof -t -i:8000)
```

#### Method 3: Inspect Process via `ss` / `netstat`
```bash
# Inspect process listening on port 8000
ss -lptn 'sport = :8000'

# Kill specific PID (replace <PID> with actual process ID)
kill -9 <PID>
```

#### Method 4: Restart App Service cleanly
```bash
cd "/home/zakaria-laptop/Morocco Port & Maritime Intelligence"
sudo fuser -k 8000/tcp
./venv/bin/python app.py
```

---

## 5. Summary & System Health Verification

- **Portal URL**: `http://localhost:8000/`
- **Dashboard URL**: `http://localhost:8000/dashboard`
- **Active Vessels Endpoint**: `http://localhost:8000/api/v1/vessels/active`
- **Port Congestion Endpoint**: `http://localhost:8000/api/v1/ports/congestion`
- **Radar Map Endpoint**: `http://localhost:8000/api/v1/radar/positions`

### 4.2 Pure Supabase Data Warehouse Analytics Mode

- **Simulator Stream Disabled**: `SIMULATION_MODE=false` set in `.env` and `config.py`. The background `AISIngestionService` worker task is completely disabled, stopping continuous `POST /stg_vessel_ais_raw` inserts.
- **Pure Database Queries**: All API endpoints (`/api/v1/vessels/active`, `/api/v1/radar/positions`, `/api/v1/ports/congestion`, `/api/v1/ais/stream`, `/api/v1/ai/summary`) query and aggregate directly from historical records in Supabase PostgreSQL tables (`public.fact_vessel_movements` [38,000+ rows], `public.stg_vessel_ais_raw` [46,000+ rows], `public.dim_vessels`).
- **Batch Inference Sync**: Runs an initial batch ML scoring pass across database records upon application startup, ensuring all predictions (`predicted_dwell_hours`, `anomaly_score`, `is_anomaly`) are synced directly to PostgreSQL rows.

---
*Documentation generated automatically for Morocco Port & Maritime Intelligence Platform.*
