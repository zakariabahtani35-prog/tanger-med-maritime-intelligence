import asyncio
import logging
import signal
import sys
import structlog

from config import settings
from database import db_manager
from ingestion_service import AISIngestionService


def setup_logging():
    """Configures structlog for JSON or development console output."""
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


async def main():
    setup_logging()
    logger = structlog.get_logger(__name__)

    logger.info(
        "Starting Morocco Maritime & Port Supply Chain Intelligence Ingestion Engine",
        target_table="staging.stg_vessel_ais_raw",
        simulation_mode=settings.simulation_mode,
        batch_size=settings.batch_size,
        flush_interval=settings.flush_interval_seconds,
    )

    # 1. Initialize Database Manager & Schema
    await db_manager.init_pool()
    await db_manager.init_schema("schema.sql")

    # 2. Initialize Ingestion Service
    ingestion_service = AISIngestionService()
    await ingestion_service.start()

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal(sig):
        logger.info(f"Received shutdown signal ({signal.Signals(sig).name}). Triggering graceful shutdown...")
        shutdown_event.set()

    # Register OS Signal Handlers (SIGINT, SIGTERM)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        except NotImplementedError:
            # Signal handling on Windows/non-POSIX platforms fallback
            pass

    logger.info("Pipeline pipeline actively running. Press Ctrl+C to terminate.")

    # Wait until shutdown signal is received
    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Executing Pipeline Shutdown Sequence...")
        # 3. Stop Ingestion Service (Flushes remaining queue)
        await ingestion_service.stop()

        # 4. Close Database Pool
        await db_manager.close_pool()
        logger.info("Shutdown sequence completed cleanly. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
