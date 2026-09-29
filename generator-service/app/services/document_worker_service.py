import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.document_job import DocumentJob, DocumentType
from app.processors.document_processor import (
    DocumentJobData,
    DocumentProcessingError,
    DocumentProcessor,
    GeneratedDocument,
)
from app.repositories.document_job_repository import DocumentJobRepository

logger = logging.getLogger(__name__)

RepositoryFactory = Callable[[AsyncSession], DocumentJobRepository]


class DocumentWorkerService:
    """Orchestre le traitement asynchrone des jobs de génération."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        processors: Mapping[DocumentType, DocumentProcessor],
        poll_interval_seconds: float,
        stale_job_timeout_seconds: float,
        repository_factory: RepositoryFactory = DocumentJobRepository,
    ) -> None:
        self._session_factory = session_factory
        self._processors = processors
        self._poll_interval_seconds = poll_interval_seconds
        self._stale_job_timeout_seconds = stale_job_timeout_seconds
        self._repository_factory = repository_factory

    async def reserve_next_job(self) -> DocumentJobData | None:
        """Réserve un job dans une transaction courte puis détache ses données."""
        async with self._session_factory() as session, session.begin():
            job = await self._repository_factory(session).reserve_next_pending(
                now=datetime.now(UTC)
            )
            return self._detach_job(job) if job is not None else None

    async def process_next_job(self) -> bool:
        """
        Traite au plus un job hors de toute transaction de réservation.

        Le booléen retourné indique si un job a été réservé, quel que soit le
        résultat de sa génération.
        """
        job = await self.reserve_next_job()
        if job is None:
            return False

        started = time.monotonic()
        logger.info(
            "Traitement du job id=%s type=%s status=processing",
            job.id,
            job.document_type,
        )
        try:
            processor = self._processors.get(job.document_type)
            if processor is None:
                raise DocumentProcessingError(
                    code="unsupported_document_type",
                    message="Type de document non pris en charge",
                )
            document = await processor.process(job)
        except DocumentProcessingError as error:
            await self._mark_failed(job, error.code, error.message[:1000])
            self._log_failure(job, started, error.code)
        except Exception as error:
            error_code = "unexpected_processing_error"
            await self._mark_failed(
                job,
                error_code,
                "Erreur inattendue pendant le traitement du document",
            )
            logger.error(
                "Échec du job id=%s type=%s status=failed durée=%.3fs "
                "error_code=%s exception_type=%s",
                job.id,
                job.document_type,
                time.monotonic() - started,
                error_code,
                type(error).__name__,
            )
        else:
            await self._mark_completed(job, document)
            logger.info(
                "Job terminé id=%s type=%s status=completed durée=%.3fs",
                job.id,
                job.document_type,
                time.monotonic() - started,
            )
        return True

    async def recover_stale_jobs(self) -> int:
        """Remet en attente les jobs abandonnés par un worker interrompu."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self._stale_job_timeout_seconds)
        async with self._session_factory() as session, session.begin():
            job_ids = await self._repository_factory(session).requeue_stale_jobs(
                cutoff=cutoff,
                now=now,
            )
        if job_ids:
            logger.warning("Jobs expirés remis en attente nombre=%d", len(job_ids))
        return len(job_ids)

    async def run(self, stop_event: asyncio.Event) -> None:
        """Exécute la boucle de polling jusqu'au signal d'arrêt."""
        await self._recover_with_database_handling()
        recovery_interval = min(self._stale_job_timeout_seconds, 60.0)
        next_recovery = time.monotonic() + recovery_interval

        while not stop_event.is_set():
            try:
                processed = await self.process_next_job()
                if time.monotonic() >= next_recovery:
                    await self.recover_stale_jobs()
                    next_recovery = time.monotonic() + recovery_interval
            except SQLAlchemyError as error:
                logger.error(
                    "Échec d'une opération de base du worker exception_type=%s",
                    type(error).__name__,
                )
                processed = False

            if not processed:
                await self._wait_for_poll_or_stop(stop_event)

        logger.info("Worker de génération arrêté")

    async def _mark_completed(
        self,
        job: DocumentJobData,
        document: GeneratedDocument,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            updated = await self._repository_factory(session).mark_completed(
                job.id,
                result_content=document.content,
                result_format=document.format,
                expected_started_at=job.started_at,
                now=datetime.now(UTC),
            )
        if not updated:
            logger.warning("Fin du job ignorée id=%s", job.id)

    async def _mark_failed(
        self,
        job: DocumentJobData,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            updated = await self._repository_factory(session).mark_failed(
                job.id,
                error_code=error_code,
                error_message=error_message,
                expected_started_at=job.started_at,
                now=datetime.now(UTC),
            )
        if not updated:
            logger.warning("Mise en échec du job ignorée id=%s", job.id)

    async def _recover_with_database_handling(self) -> None:
        try:
            await self.recover_stale_jobs()
        except SQLAlchemyError as error:
            logger.error(
                "Échec de la récupération initiale des jobs expirés exception_type=%s",
                type(error).__name__,
            )

    async def _wait_for_poll_or_stop(self, stop_event: asyncio.Event) -> None:
        with suppress(TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=self._poll_interval_seconds,
            )

    def _log_failure(
        self,
        job: DocumentJobData,
        started: float,
        error_code: str,
    ) -> None:
        logger.warning(
            "Échec du job id=%s type=%s status=failed durée=%.3fs error_code=%s",
            job.id,
            job.document_type,
            time.monotonic() - started,
            error_code,
        )

    @staticmethod
    def _detach_job(job: DocumentJob) -> DocumentJobData:
        if job.started_at is None:
            raise RuntimeError("Le job réservé ne possède pas de date de début")
        return DocumentJobData(
            id=job.id,
            document_type=job.document_type,
            avp_number=job.avp_number,
            resume_data=dict(job.resume_data),
            started_at=job.started_at,
        )
