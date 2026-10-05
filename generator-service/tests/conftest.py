import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

# Définir la version avant tout import de l'application.
os.environ.setdefault("APP_VERSION", "test")

from app.api.dependencies import require_api_identity
from app.core.exceptions import (
    DocumentGenerationFailedError,
    DocumentJobNotFoundError,
    DocumentJobNotReadyError,
    DocumentResultUnavailableError,
)
from app.main import app
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.services.document_job_service import get_document_job_service
from cv_generator_shared.dto import ApiIdentity

DEFAULT_CLIENT_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEFAULT_KEY_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakeDocumentJobService:
    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, DocumentJob] = {}

    def add_job(
        self,
        status: DocumentJobStatus,
        *,
        document_type: DocumentType = DocumentType.CV,
        result_content: str | None = None,
        result_format: str | None = None,
        error_message: str | None = None,
        client_id: uuid.UUID | None = DEFAULT_CLIENT_ID,
    ) -> DocumentJob:
        now = datetime.now(UTC)
        job = DocumentJob(
            id=uuid.uuid4(),
            client_id=client_id,
            document_type=document_type,
            status=status,
            avp_number="1234-26-001",
            resume_data={"private": "must not leak"},
            result_content=result_content,
            result_format=result_format,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        return job

    async def create_job(
        self,
        *,
        client_id: uuid.UUID,
        document_type: DocumentType,
        avp_number: str,
        resume_data: dict[str, Any],
    ) -> DocumentJob:
        job = self.add_job(DocumentJobStatus.PENDING, document_type=document_type)
        job.client_id = client_id
        job.avp_number = avp_number
        job.resume_data = resume_data
        return job

    async def get_job(self, job_id: uuid.UUID, *, client_id: uuid.UUID) -> DocumentJob:
        job = self.jobs.get(job_id)
        if job is None or job.client_id != client_id:
            raise DocumentJobNotFoundError(job_id)
        return job

    async def get_result(
        self, job_id: uuid.UUID, *, client_id: uuid.UUID
    ) -> DocumentJob:
        job = await self.get_job(job_id, client_id=client_id)
        if job.status in {
            DocumentJobStatus.PENDING,
            DocumentJobStatus.PROCESSING,
        }:
            raise DocumentJobNotReadyError
        if job.status is DocumentJobStatus.FAILED:
            raise DocumentGenerationFailedError
        return job

    async def get_asciidoc_job(
        self, job_id: uuid.UUID, *, client_id: uuid.UUID
    ) -> DocumentJob:
        job = await self.get_result(job_id, client_id=client_id)
        if (
            job.result_format != "asciidoc"
            or job.result_content is None
            or not job.result_content.strip()
        ):
            raise DocumentResultUnavailableError
        return job


@pytest.fixture
def document_service() -> FakeDocumentJobService:
    return FakeDocumentJobService()


@pytest.fixture
async def api_client(
    document_service: FakeDocumentJobService,
) -> AsyncIterator[httpx.AsyncClient]:
    async def override_document_service() -> FakeDocumentJobService:
        return document_service

    async def override_identity() -> ApiIdentity:
        return ApiIdentity(
            client_id=DEFAULT_CLIENT_ID,
            key_id=DEFAULT_KEY_ID,
            client_name="Client de test",
        )

    app.dependency_overrides[get_document_job_service] = override_document_service
    app.dependency_overrides[require_api_identity] = override_identity
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()
