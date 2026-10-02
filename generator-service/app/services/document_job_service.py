import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import (
    DocumentGenerationFailedError,
    DocumentJobNotFoundError,
    DocumentJobNotReadyError,
    DocumentResultUnavailableError,
)
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.repositories.document_job_repository import DocumentJobRepository


class DocumentJobService:
    """Porte les règles métier de création et de consultation des jobs."""

    def __init__(
        self,
        session: AsyncSession,
        repository: DocumentJobRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or DocumentJobRepository(session)

    async def create_job(
        self,
        *,
        client_id: uuid.UUID,
        document_type: DocumentType,
        avp_number: str,
        resume_data: dict[str, Any],
    ) -> DocumentJob:
        async with self._session.begin():
            return await self._repository.create_job(
                client_id=client_id,
                document_type=document_type,
                avp_number=avp_number,
                resume_data=resume_data,
            )

    async def get_job(self, job_id: uuid.UUID, *, client_id: uuid.UUID) -> DocumentJob:
        async with self._session.begin():
            job = await self._repository.get_by_id_for_client(job_id, client_id)
        if job is None:
            raise DocumentJobNotFoundError(job_id)
        return job

    async def get_result(
        self, job_id: uuid.UUID, *, client_id: uuid.UUID
    ) -> DocumentJob:
        """Retourne un résultat terminé ou signale son état métier indisponible."""
        job = await self.get_job(job_id, client_id=client_id)
        if job.status in {
            DocumentJobStatus.PENDING,
            DocumentJobStatus.PROCESSING,
        }:
            raise DocumentJobNotReadyError
        if job.status is DocumentJobStatus.FAILED:
            raise DocumentGenerationFailedError
        if job.result_content is None or job.result_format is None:
            raise DocumentGenerationFailedError
        return job

    async def get_asciidoc_job(
        self, job_id: uuid.UUID, *, client_id: uuid.UUID
    ) -> DocumentJob:
        """Retourne un job terminé dont le résultat AsciiDoc est exploitable."""
        job = await self.get_result(job_id, client_id=client_id)
        if (
            job.result_format != "asciidoc"
            or job.result_content is None
            or not job.result_content.strip()
        ):
            raise DocumentResultUnavailableError
        return job


async def get_document_job_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentJobService:
    return DocumentJobService(session)
