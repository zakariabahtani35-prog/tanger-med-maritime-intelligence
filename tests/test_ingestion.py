import asyncio
from datetime import datetime, timezone
import pytest
from database import db_manager
from ingestion_service import AISIngestionService
from models import AISVesselRecord


@pytest.mark.asyncio
async def test_supabase_bulk_insert_dry_run():
    records = [
        AISVesselRecord(
            mmsi="228389000",
            vessel_name="CMA CGM JACQUES SAADE",
            latitude=35.8900,
            longitude=-5.4800,
            speed_knots=18.5,
            timestamp_utc=datetime.now(timezone.utc),
        ),
        AISVesselRecord(
            mmsi="242555666",
            vessel_name="MAROC PHOSPHATE I",
            latitude=33.6100,
            longitude=-7.6000,
            speed_knots=12.0,
            timestamp_utc=datetime.now(timezone.utc),
        ),
    ]

    inserted = await db_manager.bulk_insert_records(records)
    assert inserted == 2


@pytest.mark.asyncio
async def test_ingestion_service_lifecycle():
    service = AISIngestionService()
    await service.start()

    # Let simulator producer run for 1.5 seconds
    await asyncio.sleep(1.5)

    assert service.total_processed_count > 0

    await service.stop()
    assert service.is_running is False
