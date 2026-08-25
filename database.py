import asyncio
from typing import List, Optional, Dict, Any
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from supabase import create_client, Client
    from postgrest.exceptions import APIError
except ImportError:
    create_client = None
    Client = Any
    APIError = Exception

from config import settings
from models import AISVesselRecord

logger = structlog.get_logger(__name__)


class SupabaseDatabaseManager:
    """
    Native Supabase Database Manager using official supabase-py REST Client.
    Manages batch insertion into target Supabase table (e.g. stg_vessel_ais_raw).
    """

    def __init__(self):
        self.client: Optional[Client] = None
        self.is_connected: bool = False

    async def init_client(self) -> Optional[Client]:
        """Initializes the Supabase client using SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."""
        key = settings.effective_supabase_key
        if not key or key in ("your_service_role_key_here", "your_anon_or_service_key_here", ""):
            logger.warning(
                "No valid SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY provided in .env. Pipeline will run in DRY-RUN mode.",
                supabase_url=settings.supabase_url,
            )
            self.is_connected = False
            return None

        try:
            logger.info("Initializing Supabase REST Client...", url=settings.supabase_url)
            self.client = create_client(settings.supabase_url, key)
            self.is_connected = True
            logger.info(
                "Supabase Client successfully initialized.",
                target_table=settings.target_table,
            )
            return self.client
        except Exception as e:
            self.is_connected = False
            logger.warning(
                "Failed to initialize Supabase Client. Falling back to DRY-RUN mode.",
                error=str(e),
            )
            return None

    async def close_client(self) -> None:
        """Gracefully closes Supabase Client connection."""
        self.is_connected = False
        self.client = None
        logger.info("Supabase Client shutdown completed.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def bulk_insert_records(self, records: List[AISVesselRecord]) -> int:
        """
        Bulk Insert list of AISVesselRecord into Supabase REST API (public.stg_vessel_ais_raw).
        """
        if not records:
            return 0

        # Convert records to JSON-serializable dictionaries
        payload: List[Dict[str, Any]] = [r.to_supabase_dict() for r in records]

        if not self.is_connected or not self.client:
            logger.info(
                "DRY-RUN BULK INSERT (Supabase REST API): Simulating batch load",
                record_count=len(payload),
                target_table=settings.target_table,
                sample_mmsi=payload[0]["mmsi"],
                sample_vessel=payload[0]["vessel_name"],
            )
            return len(records)

        try:
            logger.debug(
                "Executing Supabase REST API batch insert...",
                table=settings.target_table,
                count=len(payload),
            )

            # Execute synchronous Supabase insert call in an async executor thread
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.table(settings.target_table).insert(payload).execute()
            )

            logger.info(
                "Successfully inserted batch to Supabase via REST API",
                target_table=settings.target_table,
                count=len(payload),
            )
            return len(payload)

        except APIError as api_err:
            error_data = getattr(api_err, "info", {}) or str(api_err)
            if "PGRST205" in str(error_data) or "schema cache" in str(error_data):
                logger.warning(
                    f"Target table '{settings.target_table}' not found in Supabase schema cache. "
                    "Run 'schema.sql' in Supabase SQL Editor. Falling back to DRY-RUN mode for this batch.",
                    error=str(api_err),
                    count=len(payload),
                )
                return len(payload)
            else:
                logger.error("Supabase REST API Error", error=str(api_err), count=len(payload))
                raise api_err
        except Exception as e:
            logger.error("Supabase REST API Batch Insert failed", error=str(e), count=len(payload))
            raise e


# Global Supabase Database Manager Singleton
db_manager = SupabaseDatabaseManager()
