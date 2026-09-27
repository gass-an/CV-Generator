import asyncio
import logging
import signal
from contextlib import suppress

from app.clients.avp_client import AvpClient
from app.clients.llm_client import LlmClient
from app.core.config import get_settings
from app.core.database import async_session_factory, engine
from app.processors.cv_document_processor import CvDocumentProcessor
from app.prompts.cv_prompt_builder import CvPromptBuilder
from app.services.document_worker_service import DocumentWorkerService

logger = logging.getLogger(__name__)


def validate_worker_configuration(*, llm_base_url: str, llm_model: str) -> None:
    missing = []
    if not llm_base_url.strip():
        missing.append("LLM_BASE_URL")
    if not llm_model.strip():
        missing.append("LLM_MODEL")
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing worker configuration: {names}")


async def run_worker() -> None:
    settings = get_settings()
    validate_worker_configuration(
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
    )
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, stop_event.set)

    avp_client = AvpClient(base_url=settings.opt_avp_base_url)
    llm_client = LlmClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )
    processor = CvDocumentProcessor(
        avp_client=avp_client,
        prompt_builder=CvPromptBuilder(),
        llm_client=llm_client,
    )
    worker = DocumentWorkerService(
        session_factory=async_session_factory,
        processor=processor,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        stale_job_timeout_seconds=settings.worker_stale_job_timeout_seconds,
    )

    logger.info("Document worker started")
    try:
        await worker.run(stop_event)
    finally:
        try:
            await asyncio.gather(avp_client.aclose(), llm_client.aclose())
        finally:
            await engine.dispose()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker())


if __name__ == "__main__":
    main()
