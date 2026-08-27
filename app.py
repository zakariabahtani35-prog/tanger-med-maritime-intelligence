import asyncio
import os
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import structlog
import uvicorn

from config import settings, GEOFENCES
from database import db_manager
from ingestion_service import AISIngestionService
from ml_engine.inference_service import ml_inference_service

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
PORTAL_DIR = BASE_DIR / "portal"
TEMPLATES_DIR = BASE_DIR / "templates"

# Global Ingestion Engine singleton
ingestion_service = AISIngestionService()
active_websockets: List[WebSocket] = []


def setup_logging():
    """Configures structured logging for unified application."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager starting DB connections and serving pure Supabase data warehouse analytics."""
    setup_logging()
    logger = structlog.get_logger(__name__)
    logger.info("Initializing Morocco Maritime & Port Intelligence Platform (Pure Data Warehouse Analytics Mode)...")

    # 1. Initialize Supabase Client Connection
    await db_manager.init_client()

    # 2. Ingestion Service (Only run if explicitly enabled in simulation mode)
    if settings.simulation_mode:
        logger.info("Simulation Mode enabled. Starting background telemetry ingestion service...")
        await ingestion_service.start()
    else:
        logger.info("PURE DATA WAREHOUSE ANALYTICS MODE ACTIVE. Live simulator ingestion service disabled.")

    # 3. One-time ML Inference Batch Scoring Sync across existing database records
    try:
        scored_count = await ml_inference_service.run_batch_inference_and_persist(db_manager)
        logger.info("Completed ML Inference batch scoring sync on Supabase records.", scored_records=scored_count)
    except Exception as e:
        logger.warning("Initial ML inference scoring notice:", error=str(e))

    # 4. Background WebSocket broadcaster task
    broadcast_task = asyncio.create_task(telemetry_broadcaster())

    logger.info(
        "Platform online (Pure Supabase Data Warehouse Analytics Mode).",
        portal_url="http://localhost:8000/",
        dashboard_url="http://localhost:8000/dashboard",
    )

    yield

    # Shutdown sequence
    logger.info("Shutting down Morocco Maritime Intelligence Platform...")
    broadcast_task.cancel()
    try:
        await broadcast_task
    except Exception:
        pass

    if ingestion_service.is_running:
        await ingestion_service.stop()

    await db_manager.close_client()
    logger.info("Shutdown completed cleanly.")


app = FastAPI(
    title="Morocco Maritime & Port Supply Chain Intelligence",
    description="Unified platform serving presentation portal, telemetry engine, and real-time analytics.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static asset directories
if (PORTAL_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(PORTAL_DIR / "assets")), name="assets")

if (PORTAL_DIR / "fonts").exists():
    app.mount("/fonts", StaticFiles(directory=str(PORTAL_DIR / "fonts")), name="fonts")


# ==========================================
# 1. LANDING PORTAL ROUTES
# ==========================================

@app.api_route("/", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_landing_portal():
    """Serves the primary Obys-Agency-Clone presentation landing page."""
    portal_index = PORTAL_DIR / "index.html"
    if portal_index.exists():
        return FileResponse(str(portal_index))
    return HTMLResponse("<h1>Morocco Maritime Intelligence Platform</h1>")


@app.api_route("/style.css", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_portal_style():
    """Serves the portal CSS stylesheet."""
    return FileResponse(str(PORTAL_DIR / "style.css"))


@app.api_route("/script.js", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_portal_script():
    """Serves the portal JavaScript bundle."""
    return FileResponse(str(PORTAL_DIR / "script.js"))


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_favicon():
    """Serves the official BY logo browser tab favicon."""
    fav_file = PORTAL_DIR / "assets" / "favicon.ico"
    if fav_file.exists():
        return FileResponse(str(fav_file), media_type="image/x-icon")
    return FileResponse(str(PORTAL_DIR / "assets" / "bytecrafters-by.svg"))


@app.api_route("/obys.png", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_portal_logo():
    """Serves the portal preview asset if requested."""
    return FileResponse(str(PORTAL_DIR / "assets" / "bytecrafters-by.svg"))


# ==========================================
# 2. LIVE ANALYTICS DASHBOARD ROUTES
# ==========================================

@app.api_route("/dashboard", methods=["GET", "HEAD"], response_class=FileResponse)
async def serve_dashboard():
    """Serves the live interactive geospatial maritime analytics dashboard."""
    dashboard_file = TEMPLATES_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(str(dashboard_file))
    return HTMLResponse("<h1>Maritime Analytics Dashboard Loading...</h1>")


# ==========================================
# 3. REAL-TIME SUPABASE REST API ENDPOINTS
# ==========================================

@app.api_route("/api/v1/vessels/active", methods=["GET", "HEAD"])
async def get_active_vessels_kpi():
    """Query 1: Active Vessels KPI & Fleet Composition from public.dim_vessels & public.fact_vessel_movements."""
    return await db_manager.query_active_vessels_and_fleet_composition()


@app.api_route("/api/v1/ports/congestion", methods=["GET", "HEAD"])
async def get_port_congestion_indices():
    """Query 2: Port Occupancy & Congestion Indices (Tanger Med & Casablanca) from public.fact_vessel_movements & public.fact_port_dwell_time."""
    return await db_manager.query_port_congestion_indices()


@app.api_route("/api/v1/radar/positions", methods=["GET", "HEAD"])
async def get_geospatial_radar_positions():
    """Query 3: Geospatial Radar Map WGS84 Coords from public.fact_vessel_movements."""
    return await db_manager.query_geospatial_radar_positions()


@app.api_route("/api/v1/ais/stream", methods=["GET", "HEAD"])
async def get_live_ais_stream(limit: int = 100):
    """Query 4: Live AIS Vessel Stream Table from public.stg_vessel_ais_raw."""
    return await db_manager.query_live_ais_stream(limit=limit)


@app.api_route("/api/v1/ai/summary", methods=["GET", "HEAD"])
async def get_ai_summary():
    """Returns aggregated AI anomaly counts, risk scores, and port predicted dwell times."""
    movements = await db_manager.query_geospatial_radar_positions()
    return ml_inference_service.get_ai_summary(movements)


@app.api_route("/api/v1/ai/anomalies", methods=["GET", "HEAD"])
async def get_active_anomalies():
    """Returns list of active vessels flagged with high risk / kinematic anomalies."""
    movements = await db_manager.query_geospatial_radar_positions()
    return [
        m for m in movements
        if m.get("is_anomaly") is True or float(m.get("anomaly_score", 0.0)) > 0.65
    ]


# Backward-Compatible Legacy Endpoints
@app.api_route("/api/telemetry/live", methods=["GET", "HEAD"])
async def get_live_telemetry():
    """Legacy alias for geospatial radar positions."""
    return await db_manager.query_geospatial_radar_positions()


@app.api_route("/api/metrics/summary", methods=["GET", "HEAD"])
async def get_metrics_summary():
    """Legacy alias for summary metrics."""
    vessels_kpi = await db_manager.query_active_vessels_and_fleet_composition()
    ports_kpi = await db_manager.query_port_congestion_indices()
    movements = await db_manager.query_geospatial_radar_positions()
    ai_summary = ml_inference_service.get_ai_summary(movements)
    base_metrics = ingestion_service.get_metrics()
    base_metrics["active_vessel_count"] = vessels_kpi["total_unique_vessels"]
    base_metrics["fleet_composition"] = vessels_kpi["fleet_composition"]
    base_metrics["tanger_med"] = ports_kpi["tanger_med"]
    base_metrics["casablanca"] = ports_kpi["casablanca"]
    base_metrics["ai_summary"] = ai_summary
    return base_metrics


@app.get("/api/geofences")
async def get_operational_geofences():
    """Returns configured PostGIS spatial bounding boxes for Moroccan waters."""
    return [
        {
            "name": gf.name,
            "min_lat": gf.min_lat,
            "max_lat": gf.max_lat,
            "min_lon": gf.min_lon,
            "max_lon": gf.max_lon,
        }
        for gf in GEOFENCES
    ]


@app.get("/health")
async def health_check():
    """Health check status endpoint."""
    return {
        "status": "healthy",
        "ingestion_active": ingestion_service.is_running,
        "processed_packets": ingestion_service.total_processed_count,
    }


# ==========================================
# 4. WEBSOCKET REAL-TIME STREAM
# ==========================================

@app.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """High-frequency WebSocket endpoint streaming vessel telemetry updates directly from Supabase warehouse."""
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial snapshot immediately from database
        movements = await db_manager.query_geospatial_radar_positions()
        metrics = await get_metrics_summary()
        initial_data = {
            "vessels": movements,
            "metrics": metrics,
        }
        await websocket.send_json(initial_data)

        while True:
            # Keep-alive receive ping
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


async def telemetry_broadcaster():
    """Broadcasts real-time telemetry updates from Supabase database to connected WebSockets every 3 seconds."""
    while True:
        try:
            await asyncio.sleep(3.0)
            if active_websockets:
                movements = await db_manager.query_geospatial_radar_positions()
                metrics = await get_metrics_summary()
                payload = {
                    "vessels": movements,
                    "metrics": metrics,
                }
                dead_sockets = []
                for ws in active_websockets:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead_sockets.append(ws)

                for dead in dead_sockets:
                    if dead in active_websockets:
                        active_websockets.remove(dead)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(3.0)


# ==========================================
# 5. UNIFIED LAUNCHER ENTRYPOINT
# ==========================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print("\n" + "=" * 70)
    print(" 🚢 MOROCCO MARITIME & PORT SUPPLY CHAIN INTELLIGENCE PLATFORM")
    print(f" 🌐 Entry Portal:      http://localhost:{port}/")
    print(f" 📊 Analytics Hub:     http://localhost:{port}/dashboard")
    print(f" 📡 API Telemetry:     http://localhost:{port}/api/telemetry/live")
    print(f" 🛰️ Pipeline Mode:     {'SIMULATOR' if settings.simulation_mode else 'LIVE AISSTREAM'}")
    print("=" * 70 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")
