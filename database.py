import asyncio
import os
from typing import List, Optional
import asyncpg
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings
from models import AISVesselRecord

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """
    Asynchronous Connection Pool and Bulk Loading Manager for PostgreSQL/PostGIS warehouse.
    """

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self.is_connected: bool = False

    async def init_pool(self) -> Optional[asyncpg.Pool]:
        """Initialize the asyncpg connection pool."""
        try:
            logger.info("Initializing Database Connection Pool...", dsn=settings.database_url)
            self._pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=settings.db_min_pool_size,
                max_size=settings.db_max_pool_size,
                timeout=10.0,
            )
            self.is_connected = True
            logger.info("Database Connection Pool successfully initialized.")
            return self._pool
        except Exception as e:
            self.is_connected = False
            logger.warning(
                "Could not connect to PostgreSQL database. Running in DRY-RUN / Standalone mode.",
                error=str(e),
            )
            return None

    async def init_schema(self, schema_file: str = "schema.sql") -> None:
        """Executes DDL schema initialization if database connection is active."""
        if not self.is_connected or not self._pool:
            logger.info("Skipping schema initialization (Database offline/standalone mode).")
            return

        if os.path.exists(schema_file):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    ddl_sql = f.read()

                async with self._pool.acquire() as conn:
                    await conn.execute(ddl_sql)
                logger.info("Database schema initialized successfully from schema.sql.")
            except Exception as e:
                logger.error("Failed to execute DDL schema initialization", error=str(e))
        else:
            logger.warning(f"Schema DDL file '{schema_file}' not found.")

    async def close_pool(self) -> None:
        """Gracefully closes the connection pool."""
        if self._pool:
            logger.info("Closing Database Connection Pool...")
            await self._pool.close()
            self.is_connected = False
            logger.info("Database Connection Pool closed.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((asyncpg.PostgresError, OSError)),
        reraise=True,
    )
    async def bulk_insert_records(self, records: List[AISVesselRecord]) -> int:
        """
        High-Throughput Bulk Insert into staging.stg_vessel_ais_raw using asyncpg copy_records_to_table or batch insert.
        """
        if not records:
            return 0

        if not self.is_connected or not self._pool:
            logger.info(
                "DRY-RUN BULK INSERT: Simulating ingestion flush to warehouse",
                record_count=len(records),
                sample_mmsi=records[0].mmsi,
                sample_vessel=records[0].vessel_name,
            )
            return len(records)

        # Prepare record tuples matching table columns:
        # (mmsi, imo, vessel_name, vessel_type, flag_country, latitude, longitude, speed_knots, heading, nav_status, destination, eta, timestamp_utc)
        record_tuples = [
            (
                r.mmsi,
                r.imo,
                r.vessel_name,
                r.vessel_type,
                r.flag_country,
                r.latitude,
                r.longitude,
                r.speed_knots,
                r.heading,
                r.nav_status,
                r.destination,
                r.eta,
                r.timestamp_utc,
            )
            for r in records
        ]

        table_columns = [
            "mmsi",
            "imo",
            "vessel_name",
            "vessel_type",
            "flag_country",
            "latitude",
            "longitude",
            "speed_knots",
            "heading",
            "nav_status",
            "destination",
            "eta",
            "timestamp_utc",
        ]

        async with self._pool.acquire() as conn:
            # Use binary copy_records_to_table for ultra-high throughput ELT loading
            result = await conn.copy_records_to_table(
                table_name="stg_vessel_ais_raw",
                schema_name="staging",
                columns=table_columns,
                records=record_tuples,
            )
            logger.info(
                "Successfully bulk-inserted AIS records to staging.stg_vessel_ais_raw",
                inserted_count=len(records),
                result=result,
            )
            return len(records)


# Global Database Manager Singleton
db_manager = DatabaseManager()
