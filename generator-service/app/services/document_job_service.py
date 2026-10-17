import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from cv_generator_shared.exceptions import ApiKeyNotFoundError
from cv_generator_shared.repositories import ApiClientRepository, ApiKeyRepository
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
from app.repositories.document_job_repository import (
    DocumentHistoryRecord,
    DocumentJobRepository,
)


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
        api_key_id: uuid.UUID,
        document_type: DocumentType,
        avp_number: str,
        resume_data: dict[str, Any],
    ) -> DocumentJob:
        async with self._session.begin():
            key = await ApiKeyRepository(self._session).get_by_id(
                api_key_id, for_update=True
            )
            client = await ApiClientRepository(self._session).get_by_id(client_id)
            now = datetime.now(UTC)
            if (
                key is None
                or key.client_id != client_id
                or key.revoked_at is not None
                or (key.expires_at is not None and key.expires_at <= now)
                or client is None
                or not client.is_active
            ):
                raise ApiKeyNotFoundError(api_key_id)
            return await self._repository.create_job(
                client_id=client_id,
                api_key_id=api_key_id,
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

    async def list_history(
        self,
        *,
        client_id: uuid.UUID,
        limit: int,
        offset: int,
        document_type: DocumentType | None = None,
        status: DocumentJobStatus | None = None,
        avp_number: str | None = None,
    ) -> tuple[list[DocumentHistoryRecord], int]:
        """Liste les documents du client dans une transaction de lecture courte."""
        async with self._session.begin():
            return await self._repository.list_for_client(
                client_id=client_id,
                limit=limit,
                offset=offset,
                document_type=document_type,
                status=status,
                avp_number=avp_number,
            )

    async def list_avp_numbers(
        self,
        *,
        client_id: uuid.UUID,
        prefix: str | None = None,
    ) -> list[str]:
        """Liste les AVP distincts du client dans une transaction courte."""
        normalized_prefix = prefix.strip() if prefix else None
        async with self._session.begin():
            return await self._repository.list_distinct_avp_numbers_for_client(
                client_id=client_id,
                prefix=normalized_prefix or None,
            )

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
