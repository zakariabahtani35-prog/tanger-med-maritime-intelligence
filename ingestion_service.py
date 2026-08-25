import asyncio
import json
import math
import random
from datetime import datetime, timezone
from typing import List, Optional
import aiohttp
import structlog

from config import settings
from database import db_manager
from models import AISVesselRecord

logger = structlog.get_logger(__name__)


class SimulatedVessel:
    """
    Kinematic State for a Simulated Maritime Vessel.
    Tracks waypoints and updates position based on speed and heading.
    """

    def __init__(
        self,
        mmsi: str,
        imo: str,
        name: str,
        vessel_type: str,
        flag: str,
        waypoints: List[tuple[float, float]],
        base_speed: float,
        destination: str,
    ):
        self.mmsi = mmsi
        self.imo = imo
        self.name = name
        self.vessel_type = vessel_type
        self.flag = flag
        self.waypoints = waypoints
        self.current_waypoint_idx = 0
        self.latitude, self.longitude = waypoints[0]
        self.speed_knots = base_speed
        self.base_speed = base_speed
        self.heading = 90.0
        self.destination = destination
        self.nav_status = "Underway using engine"
        self._update_heading_to_next_waypoint()

    def _update_heading_to_next_waypoint(self):
        target_lat, target_lon = self.waypoints[self.current_waypoint_idx]
        d_lat = target_lat - self.latitude
        d_lon = (target_lon - self.longitude) * math.cos(math.radians(self.latitude))
        angle = math.degrees(math.atan2(d_lon, d_lat))
        self.heading = (angle + 360) % 360

    def tick(self, delta_seconds: float = 1.0):
        """Simulate kinematic movement for delta_seconds."""
        if self.nav_status in ("Moored", "At anchor"):
            # Minimal jitter while anchored/moored
            self.speed_knots = max(0.0, self.speed_knots + random.uniform(-0.1, 0.1))
            if random.random() < 0.05:
                self.nav_status = "Underway using engine"
                self.speed_knots = self.base_speed
            return

        target_lat, target_lon = self.waypoints[self.current_waypoint_idx]
        dist_deg = math.hypot(target_lat - self.latitude, target_lon - self.longitude)

        # Reached waypoint threshold (~200 meters)
        if dist_deg < 0.003:
            self.current_waypoint_idx = (self.current_waypoint_idx + 1) % len(self.waypoints)
            self._update_heading_to_next_waypoint()
            # Randomly change navigation status near port
            if "TANGER" in self.destination and self.current_waypoint_idx == 2:
                if random.random() < 0.3:
                    self.nav_status = "Moored"
                    self.speed_knots = 0.0
                    return

        # Calculate position change: SOG in knots to degrees/second
        # 1 knot = 1.852 km/h = 1852 m/h -> 1 degree lat ~ 111,111 m -> 1 knot = 1.852/111.111 deg/hr = 0.00000463 deg/sec
        speed_deg_per_sec = (self.speed_knots * 1.852 / 111.111) / 3600.0
        step_dist = speed_deg_per_sec * delta_seconds

        rad_heading = math.radians(self.heading)
        d_lat = step_dist * math.cos(rad_heading)
        d_lon = (step_dist * math.sin(rad_heading)) / math.cos(math.radians(self.latitude))

        self.latitude += d_lat
        self.longitude += d_lon

        # Minor speed variation
        self.speed_knots = max(0.5, min(28.0, self.speed_knots + random.uniform(-0.2, 0.2)))

    def to_record(self) -> AISVesselRecord:
        return AISVesselRecord(
            mmsi=self.mmsi,
            imo=self.imo,
            vessel_name=self.name,
            vessel_type=self.vessel_type,
            flag_country=self.flag,
            latitude=self.latitude,
            longitude=self.longitude,
            speed_knots=self.speed_knots,
            heading=self.heading,
            nav_status=self.nav_status,
            destination=self.destination,
            eta=datetime.now(timezone.utc),
            timestamp_utc=datetime.now(timezone.utc),
        )


class MaritimeSimulator:
    """
    High-Fidelity Deterministic Simulator generating realistic vessel traffic
    for Gibraltar Strait, Tanger Med Port, and Casablanca Port approaches.
    """

    def __init__(self):
        self.vessels: List[SimulatedVessel] = [
            # 1. Tanger Med Container Carrier (TSS Route)
            SimulatedVessel(
                mmsi="228389000",
                imo="9839179",
                name="CMA CGM JACQUES SAADE",
                vessel_type="Container Ship",
                flag="France",
                waypoints=[
                    (35.9500, -5.8500),  # West Entrance Gibraltar TSS
                    (35.9100, -5.5000),  # Mid Strait
                    (35.8900, -5.4800),  # Tanger Med Approach Channel
                    (35.8850, -5.5000),  # Tanger Med Berth TC1
                ],
                base_speed=18.5,
                destination="TANGER MED",
            ),
            # 2. Maersk Ultra-Large Container Vessel
            SimulatedVessel(
                mmsi="219018000",
                imo="9632064",
                name="MAERSK MC-KINNEY MOLLER",
                vessel_type="Container Ship",
                flag="Denmark",
                waypoints=[
                    (35.8850, -5.5050),  # Tanger Med Berth TC2
                    (35.9000, -5.4000),  # Eastbound Gibraltar TSS
                    (36.0500, -5.2500),  # Mediterranean Exit
                    (35.9500, -5.8500),  # Round loop
                ],
                base_speed=19.0,
                destination="ALGECIRAS / TANGER MED",
            ),
            # 3. Fast Passenger Ferry (Tanger Med <-> Algeciras)
            SimulatedVessel(
                mmsi="224639000",
                imo="9216171",
                name="BALEARIA PASSENGER FERRY",
                vessel_type="Passenger Ferry",
                flag="Spain",
                waypoints=[
                    (35.8880, -5.5020),  # Tanger Med Ferry Terminal
                    (36.0000, -5.4500),  # Mid Strait Crossing
                    (36.1200, -5.4300),  # Algeciras Port Entrance
                    (36.0000, -5.4500),  # Return leg
                ],
                base_speed=24.0,
                destination="TANGER MED",
            ),
            # 4. Crude Oil Tanker in Tanger Med Outer Anchorage
            SimulatedVessel(
                mmsi="636018345",
                imo="9412356",
                name="AFRAMAX TANKER ATLAS",
                vessel_type="Crude Oil Tanker",
                flag="Liberia",
                waypoints=[
                    (35.9300, -5.4200),  # Anchorage Zone North
                    (35.9250, -5.4100),  # Drift slow
                    (35.9350, -5.4250),
                ],
                base_speed=2.5,
                destination="TANGER MED ANCHORAGE",
            ),
            # 5. Moroccan Tugboat in Tanger Med Basin
            SimulatedVessel(
                mmsi="242123400",
                imo="9754321",
                name="TANGER TUG 1",
                vessel_type="Tug",
                flag="Morocco",
                waypoints=[
                    (35.8870, -5.5080),  # Port Basin
                    (35.8910, -5.4950),  # Outer Pier Assist
                    (35.8870, -5.5080),
                ],
                base_speed=8.0,
                destination="TANGER MED PORT",
            ),
            # 6. Casablanca Port Approaching Bulk Carrier
            SimulatedVessel(
                mmsi="242555666",
                imo="9334455",
                name="MAROC PHOSPHATE I",
                vessel_type="Bulk Carrier",
                flag="Morocco",
                waypoints=[
                    (33.6800, -7.5200),  # Outer Casablanca Approach
                    (33.6200, -7.5800),  # Anchorage Point
                    (33.6050, -7.6000),  # Casablanca Mineral Quay
                ],
                base_speed=12.0,
                destination="CASABLANCA",
            ),
            # 7. Casablanca Express Container Ship
            SimulatedVessel(
                mmsi="352001234",
                imo="9500123",
                name="CASABLANCA EXPRESS",
                vessel_type="Container Ship",
                flag="Panama",
                waypoints=[
                    (33.6100, -7.6050),  # Casablanca Terminal
                    (33.6700, -7.5400),  # Departure Channel
                    (33.6100, -7.6050),
                ],
                base_speed=14.0,
                destination="CASABLANCA PORT",
            ),
        ]

    def generate_tick(self, delta_seconds: float = 1.0) -> List[AISVesselRecord]:
        records = []
        for vessel in self.vessels:
            vessel.tick(delta_seconds=delta_seconds)
            rec = vessel.to_record()
            records.append(rec)
        return records


class AISIngestionService:
    """
    Core Ingestion Engine managing raw AIS stream ingestion, Pydantic validation,
    Moroccan geofence filtering, and async batching buffer.
    """

    def __init__(self):
        self.queue: asyncio.Queue[AISVesselRecord] = asyncio.Queue(maxsize=5000)
        self.simulator = MaritimeSimulator()
        self.is_running: bool = False
        self._producer_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None
        self.total_processed_count: int = 0
        self.total_flushed_count: int = 0

    async def start(self):
        """Starts producer and consumer workers."""
        self.is_running = True
        logger.info("Starting AIS Ingestion Service...", simulation_mode=settings.simulation_mode)

        if settings.simulation_mode or not settings.ais_api_key:
            logger.info("Running in Deterministic High-Fidelity Maritime Simulator Mode.")
            self._producer_task = asyncio.create_task(self._simulator_producer_loop())
        else:
            logger.info("Running in Live AISStream WebSocket Feed Mode.")
            self._producer_task = asyncio.create_task(self._live_ais_producer_loop())

        self._consumer_task = asyncio.create_task(self._batch_consumer_loop())

    async def stop(self):
        """Gracefully stops ingestion engine and drains buffer."""
        logger.info("Stopping AIS Ingestion Service...")
        self.is_running = False

        if self._producer_task:
            self._producer_task.cancel()
            try:
                await self._producer_task
            except asyncio.CancelledError:
                pass

        # Drain and final flush
        await self._flush_buffer_remaining()

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        logger.info(
            "AIS Ingestion Service stopped cleanly.",
            total_processed=self.total_processed_count,
            total_flushed=self.total_flushed_count,
        )

    async def _simulator_producer_loop(self):
        """Producer loop generating simulated AIS telemetry ticks."""
        while self.is_running:
            try:
                records = self.simulator.generate_tick(delta_seconds=settings.simulator_tick_interval)
                for record in records:
                    if settings.strict_geofence_check and not record.is_in_moroccan_geofence:
                        continue

                    await self.queue.put(record)
                    self.total_processed_count += 1

                await asyncio.sleep(settings.simulator_tick_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in simulator producer loop", error=str(e))
                await asyncio.sleep(1.0)

    async def _live_ais_producer_loop(self):
        """Producer loop connecting to live AISStream WebSocket API."""
        subscribe_message = {
            "APIKey": settings.ais_api_key,
            "BoundingBoxes": [
                [[35.7000, -5.9000], [36.1500, -5.2000]],  # Tanger Med
                [[33.5500, -7.7000], [33.7000, -7.5000]],  # Casablanca
            ],
        }

        while self.is_running:
            try:
                import websockets

                logger.info("Connecting to AIS WebSocket Feed...", url=settings.ais_websocket_url)
                async with websockets.connect(settings.ais_websocket_url) as ws:
                    await ws.send(json.dumps(subscribe_message))
                    logger.info("Sent AIS subscription request.")

                    async for message in ws:
                        if not self.is_running:
                            break

                        data = json.loads(message)
                        msg_type = data.get("MessageType")

                        if msg_type == "PositionReport":
                            pos = data.get("Message", {}).get("PositionReport", {})
                            meta = data.get("MetaData", {})

                            raw_record = {
                                "mmsi": pos.get("Mmsi") or meta.get("MMSI"),
                                "vessel_name": meta.get("VesselName", "UNKNOWN"),
                                "latitude": pos.get("Latitude"),
                                "longitude": pos.get("Longitude"),
                                "speed_knots": pos.get("Sog", 0.0),
                                "heading": pos.get("TrueHeading") or pos.get("Cog"),
                                "nav_status": pos.get("NavigationalStatus"),
                                "timestamp_utc": meta.get("time_utc", datetime.now(timezone.utc)),
                            }

                            try:
                                record = AISVesselRecord(**raw_record)
                                if not settings.strict_geofence_check or record.is_in_moroccan_geofence:
                                    await self.queue.put(record)
                                    self.total_processed_count += 1
                            except Exception as val_err:
                                logger.debug("Raw AIS record validation skipped", error=str(val_err))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AIS WebSocket connection error, retrying in 5s...", error=str(e))
                await asyncio.sleep(5.0)

    async def _batch_consumer_loop(self):
        """Consumer loop reading queue and performing bulk flush to database."""
        buffer: List[AISVesselRecord] = []
        last_flush_time = asyncio.get_event_loop().time()

        while self.is_running:
            try:
                # Wait for items with timeout to enforce flush_interval_seconds
                try:
                    record = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    buffer.append(record)
                    self.queue.task_done()
                except asyncio.TimeoutError:
                    pass

                now = asyncio.get_event_loop().time()
                time_since_flush = now - last_flush_time

                # Flush conditions: buffer size reaches BATCH_SIZE or flush interval exceeded
                if len(buffer) >= settings.batch_size or (buffer and time_since_flush >= settings.flush_interval_seconds):
                    count = await db_manager.bulk_insert_records(buffer)
                    self.total_flushed_count += count
                    buffer.clear()
                    last_flush_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in batch consumer loop", error=str(e))
                await asyncio.sleep(1.0)

        # Final flush on loop exit
        if buffer:
            count = await db_manager.bulk_insert_records(buffer)
            self.total_flushed_count += count
            buffer.clear()

    async def _flush_buffer_remaining(self):
        """Drains remaining queue items and flushes."""
        remaining: List[AISVesselRecord] = []
        while not self.queue.empty():
            remaining.append(self.queue.get_nowait())
            self.queue.task_done()

        if remaining:
            logger.info("Flushing final remaining records from buffer...", count=len(remaining))
            count = await db_manager.bulk_insert_records(remaining)
            self.total_flushed_count += count
