import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
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

    async def reserve_next_pending(self, *, now: datetime) -> DocumentJob | None:
        statement = (
            select(DocumentJob)
            .where(DocumentJob.status == DocumentJobStatus.PENDING)
            .order_by(DocumentJob.created_at, DocumentJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = (await self._session.execute(statement)).scalar_one_or_none()
        if job is None:
            return None

        job.status = DocumentJobStatus.PROCESSING
        job.started_at = now
        job.updated_at = now
        await self._session.flush()
        return job

    async def mark_completed(
        self,
        job_id: uuid.UUID,
        *,
        result_content: str,
        result_format: str,
        expected_started_at: datetime,
        now: datetime,
    ) -> bool:
        statement = (
            update(DocumentJob)
            .where(
                DocumentJob.id == job_id,
                DocumentJob.status == DocumentJobStatus.PROCESSING,
                DocumentJob.started_at == expected_started_at,
            )
            .values(
                status=DocumentJobStatus.COMPLETED,
                result_content=result_content,
                result_format=result_format,
                error_code=None,
                error_message=None,
                completed_at=now,
                updated_at=now,
            )
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        *,
        error_code: str,
        error_message: str,
        expected_started_at: datetime,
        now: datetime,
    ) -> bool:
        statement = (
            update(DocumentJob)
            .where(
                DocumentJob.id == job_id,
                DocumentJob.status == DocumentJobStatus.PROCESSING,
                DocumentJob.started_at == expected_started_at,
            )
            .values(
                status=DocumentJobStatus.FAILED,
                result_content=None,
                result_format=None,
                error_code=error_code,
                error_message=error_message,
                completed_at=now,
                updated_at=now,
            )
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def requeue_stale_jobs(
        self,
        *,
        cutoff: datetime,
        now: datetime,
    ) -> list[uuid.UUID]:
        statement = (
            update(DocumentJob)
            .where(
                DocumentJob.status == DocumentJobStatus.PROCESSING,
                DocumentJob.started_at < cutoff,
            )
            .values(
                status=DocumentJobStatus.PENDING,
                started_at=None,
                completed_at=None,
                result_content=None,
                result_format=None,
                error_code=None,
                error_message=None,
                updated_at=now,
            )
            .returning(DocumentJob.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
