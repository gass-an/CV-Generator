import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType


class DocumentJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_cv_job(
        self,
        *,
        avp_number: str,
        resume_data: dict[str, Any],
    ) -> DocumentJob:
        job = DocumentJob(
            document_type=DocumentType.CV,
            status=DocumentJobStatus.PENDING,
            avp_number=avp_number,
            resume_data=resume_data,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> DocumentJob | None:
        return await self._session.get(DocumentJob, job_id)

    async def update(self, job: DocumentJob) -> DocumentJob:
        await self._session.flush()
        await self._session.refresh(job)
        return job
