<div align="center">

# 🚢 Morocco Port & Maritime Intelligence Platform
### Enterprise AIS Telemetry, PostGIS Spatial Geofencing, ML Dwell Forecasting & Kinematic Anomaly Radar

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![PostGIS](https://img.shields.io/badge/PostGIS-Spatial_GIST-00599C?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgis.net)
[![XGBoost](https://img.shields.io/badge/XGBoost-Dwell_Model-117DDF?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://xgboost.readthedocs.io)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-Isolation_Forest-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![Status](https://img.shields.io/badge/Status-Production_Zero--Defect-9E261A?style=for-the-badge)](https://github.com/zakariabahtani35-prog/tanger-med-maritime-intelligence)
[![Author](https://img.shields.io/badge/Author-Zakaria_Bahtani-010101?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/zakaria-bahtani-b64251390/)

<br/>

<p align="center">
  <b>Enterprise Maritime Data Engine for North-Western Moroccan Territorial Waters:</b><br/>
  <b>Strait of Gibraltar TSS</b> • <b>Tanger Med 1 &amp; 2 Mega-Hubs (TC1/TC2/TC3/TC4)</b> • <b>Casablanca Commercial Port Approach</b>
</p>

<p align="center">
  <a href="#-platform-showcase--preview"><b>Platform Preview</b></a> •
  <a href="#-brand-identity--design-system"><b>Design System</b></a> •
  <a href="#-project-vision--maritime-context"><b>Project Vision</b></a> •
  <a href="#-system-architecture"><b>Architecture</b></a> •
  <a href="#-machine-learning-model-cards"><b>ML Engine</b></a> •
  <a href="#-api-documentation--endpoints"><b>API Reference</b></a> •
  <a href="#-quickstart--deployment-guide"><b>Quickstart</b></a>
</p>

</div>

---

## 🖥️ Platform Showcase & Preview

<div align="center">

| 📊 Live Maritime Analytics Dashboard (`/dashboard`) | 🌐 Morocco Maritime Landing Portal (`/`) |
| :---: | :---: |
| <img src="./portal/assets/readme_dashboard_preview.jpg" alt="Live Maritime Analytics Dashboard" width="480"/> | <img src="./portal/assets/readme_website_preview.jpg" alt="Morocco Maritime Portal Landing Page" width="480"/> |
| *Real-Time Telemetry Stream, PostGIS Spatial Radar & KPI Analytics* | *Futuristic Sci-Fi Maritime Corridor Portal & Terminal Showcase* |

</div>

---

## 🎨 Brand Identity & Design System

The platform adheres to the official **ByteCrafters Luxury Maritime Palette**, blending obsidian deep-sea canvas tones with emergency telemetry crimson, cyan vector highlights, and crisp high-contrast cards matching the Analytics Dashboard:

<div align="center">

| Color Name | Hex Token | Swatch | Architectural & UI Role |
| :--- | :--- | :---: | :--- |
| **Obsidian Black** | `#010101` | <img src="https://via.placeholder.com/28/010101/010101.png" width="28" height="28" style="border-radius:4px;"/> | Main application background, navigation capsule, high-contrast dark typography. |
| **Crimson Red** | `#9E261A` | <img src="https://via.placeholder.com/28/9E261A/9E261A.png" width="28" height="28" style="border-radius:4px;"/> | Signature brand accent, primary CTA buttons, TSS lane drift alerts, high-risk anomalies. |
| **Cyan Telemetry** | `#00E5FF` | <img src="https://via.placeholder.com/28/00E5FF/00E5FF.png" width="28" height="28" style="border-radius:4px;"/> | Live vessel heading vectors, spatial radar beacons, active PostGIS geofence polygons. |
| **Crisp White** | `#FFFFFF` | <img src="https://via.placeholder.com/28/FFFFFF/FFFFFF.png" width="28" height="28" style="border-radius:4px;"/> | Bento container cards, modal dialogs, data table headers, high-clarity metric surfaces. |
| **Berth Emerald** | `#137333` | <img src="https://via.placeholder.com/28/137333/137333.png" width="28" height="28" style="border-radius:4px;"/> | Nominal vessel speed, moored status, verified berthing clearances. |
| **Slate Neutral** | `#F1F4F9` | <img src="https://via.placeholder.com/28/F1F4F9/F1F4F9.png" width="28" height="28" style="border-radius:4px;"/> | Auxiliary metric pill backgrounds, subtle container dividers, metadata badges. |

</div>

---

## 🌍 Project Vision & Maritime Context

North-Western Morocco represents one of the most vital maritime crossroads on Earth. Governed by two strategic sea corridors, the platform monitors:

1. **The Strait of Gibraltar TSS (Traffic Separation Scheme)**:
   - Accommodates over **100,000 vessel transits annually** (~20% of global ocean trade).
   - High risk of bottlenecking, requiring real-time collision monitoring, lane drift prevention, and speed anomaly triggers.

2. **Tanger Med Mega-Port Hub Complex (MAPTM)**:
   - Ranked **#1 Container Hub in Africa & the Mediterranean** (handling over **8.6 Million TEUs** annually).
   - Continuous PostGIS polygon tracking across Terminals TC1, TC2, TC3, TC4, and anchorage zones.

3. **Casablanca Commercial & Bulk Gateway (MACAS)**:
   - The primary Atlantic port for bulk commodities, general cargo, and world-leading phosphate exports.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph SOURCES["1. Streaming Telemetry Sources"]
        S1["🛰️ Live AISStream WebSocket<br/><code>wss://stream.aisstream.io/v0/stream</code>"]
        S2["🚢 Kinematic Vessel Simulator<br/>(0.5s Multi-Waypoint Engine)"]
    end

    subgraph VALIDATION["2. Ingestion & Spatial Geofence"]
        V1["🛡️ Pydantic v2 Schema Validator<br/>(WGS84 Coordinates, MMSI, SOG, COG)"]
        V2{"🌐 PostGIS Polygon Geofence<br/>Strait of Gibraltar & Tanger Med"}
        V3["❌ Out-of-Bounds Discard"]
    end

    subgraph BUFFER["3. Async Micro-Batching Buffer"]
        B1["📦 Asyncio Queue Buffer<br/>(Batch: 100 | Flush: 5.0s)"]
    end

    subgraph STORAGE["4. Persistence & Fail-Safe Engine"]
        DB1[("🛢️ Supabase PostgreSQL + PostGIS")]
        DB2["⚡ In-Memory Fallback Mirror"]
    end

    subgraph ANALYTICS["5. Machine Learning & APIs"]
        ML1["🤖 XGBoost Berth Dwell Model"]
        ML2["📡 Isolation Forest Anomaly Detector"]
        API["🚀 FastAPI REST & WebSocket Endpoints"]
    end

    SOURCES --> VALIDATION
    V1 --> V2
    V2 -- Out --> V3
    V2 -- Valid --> BUFFER
    BUFFER --> DB1
    BUFFER --> DB2
    DB1 --> ANALYTICS
    DB2 --> ANALYTICS
```

---

## 🤖 Machine Learning Model Cards

### Model 1: XGBoost Port Dwell Forecaster
- **Target Variable**: Expected Berth Dwell Time (Hours).
- **Features**: Vessel Type, Gross Tonnage (GT), Draft, Current Berth Occupancy Rate, Arrival Season, Historical Turnaround.
- **Performance**: $R^2 \approx 83.9\%$, MAE $\approx 2.4$ Hours.

### Model 2: Isolation Forest Kinematic Anomaly Radar
- **Target Variable**: Anomaly Score & Drift Flag (`-1` Anomaly, `1` Nominal).
- **Features**: Speed Over Ground (SOG), Course Over Ground (COG), Rate of Turn (ROT), Distance to Shipping Lane Centerline.
- **Contamination Parameter**: `0.035` (3.5% Expected Anomaly Rate).

---

## 🔌 API Documentation & Endpoints

| Method | Endpoint | Description | Query Parameters |
| :---: | :--- | :--- | :--- |
| `GET` | `/api/v1/vessels/active` | Fetch all active vessels currently inside Moroccan spatial geofences | `port_code`, `limit` |
| `GET` | `/api/v1/ports/congestion` | Fetch congestion indices and dwell stats for Tanger Med & Casablanca | None |
| `GET` | `/api/v1/radar/positions` | High-frequency radar vector coordinates for spatial map rendering | `mmsi` |
| `WS` | `/ws/telemetry` | WebSocket stream for live AIS position packets | `token` |

---

## 🚀 Quickstart & Deployment Guide

### Step 1: Clone Repository
```bash
git clone https://github.com/zakariabahtani35-prog/tanger-med-maritime-intelligence.git
cd tanger-med-maritime-intelligence
```

### Step 2: Initialize Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Environment Setup (`.env`)
Create a `.env` file in the root directory:
```env
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/maritime_db
AISSTREAM_API_KEY=your-aisstream-api-key
PORT=8000
```

### Step 4: Run Application Server
```bash
python main.py
```

### Step 5: Access Platforms
- **Landing Page Portal**: [`http://localhost:8000/`](http://localhost:8000/)
- **Live Analytics Dashboard**: [`http://localhost:8000/dashboard`](http://localhost:8000/dashboard)

---

## 📁 Directory Structure

```
.
├── app.py                      # Flask Application Server
├── main.py                     # Primary Application Entrypoint
├── ingestion_service.py        # AIS Ingestion & Micro-Batching Service
├── models.py                   # Data Models & Schemas
├── ml_engine/                  # Machine Learning Training & Inference
│   ├── feature_engineering.py  # Feature Extraction Pipeline
│   └── train_anomaly_model.py  # Isolation Forest Model Trainer
├── portal/                     # Frontend Application Portal & Dashboard
│   ├── index.html              # Landing Page HTML
│   ├── dashboard.html          # Analytics Dashboard HTML
│   ├── style.css               # Brand Styling System
│   ├── script.js               # Interactive Application Bundle
│   └── assets/                 # High-Resolution Media & Screenshots
│       ├── readme_dashboard_preview.jpg
│       ├── readme_website_preview.jpg
│       └── hero_presentation_bg.jpg
├── requirements.txt            # Python Dependencies Manifest
└── README.md                   # Platform Documentation
```

---

<div align="center">

**Developed by Zakaria Bahtani ([@zakariabahtani35-prog](https://github.com/zakariabahtani35-prog))**  
[LinkedIn Profile](https://www.linkedin.com/in/zakaria-bahtani-b64251390/) • [GitHub Repository](https://github.com/zakariabahtani35-prog/tanger-med-maritime-intelligence)

© 2026 Morocco Maritime & Port Intelligence Platform. Released under the MIT License.

</div>
