import asyncio
import logging
import signal
from contextlib import suppress

from app.core.config import get_settings
from app.core.database import async_session_factory, engine
from app.processors.document_processor import PlaceholderDocumentProcessor
from app.services.document_worker_service import DocumentWorkerService

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, stop_event.set)

    worker = DocumentWorkerService(
        session_factory=async_session_factory,
        processor=PlaceholderDocumentProcessor(),
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        stale_job_timeout_seconds=settings.worker_stale_job_timeout_seconds,
    )

    logger.info("Document worker started")
    try:
        await worker.run(stop_event)
    finally:
        await engine.dispose()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker())


if __name__ == "__main__":
    main()
