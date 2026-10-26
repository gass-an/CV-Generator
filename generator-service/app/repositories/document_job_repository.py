import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cv_generator_shared.llm import (
    get_llm_configuration_for_update,
    lock_llm_configuration,
)
from cv_generator_shared.models import ApiKey
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType


@dataclass(frozen=True, slots=True)
class DocumentHistoryRecord:
    """Projection non sensible d'un job destinée à l'historique public."""

    id: uuid.UUID
    document_type: DocumentType
    status: DocumentJobStatus
    avp_number: str
    candidate_name: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None = None
    llm_model: str | None = None


@dataclass(frozen=True, slots=True)
class StaleJobRecovery:
    """Résultat explicite d'une récupération de traitements interrompus."""

    requeued_ids: list[uuid.UUID]
    cancelled_ids: list[uuid.UUID]

    @property
    def total(self) -> int:
        return len(self.requeued_ids) + len(self.cancelled_ids)


class DocumentJobRepository:
    """Centralise la persistance et la réservation concurrente des jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        client_id: uuid.UUID,
        api_key_id: uuid.UUID,
        document_type: DocumentType,
        avp_number: str,
        resume_data: dict[str, Any],
        llm_model: str,
    ) -> DocumentJob:
        job = DocumentJob(
            client_id=client_id,
            api_key_id=api_key_id,
            document_type=document_type,
            status=DocumentJobStatus.PENDING,
            avp_number=avp_number,
            resume_data=resume_data,
            llm_model=llm_model,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> DocumentJob | None:
        return await self._session.get(DocumentJob, job_id)

    async def get_by_id_for_client(
        self,
        job_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> DocumentJob | None:
        """Charge un document seulement lorsqu'il appartient au client."""
        statement = select(DocumentJob).where(
            DocumentJob.id == job_id,
            DocumentJob.client_id == client_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def list_for_client(
        self,
        *,
        client_id: uuid.UUID,
        limit: int,
        offset: int,
        document_type: DocumentType | None = None,
        status: DocumentJobStatus | None = None,
        avp_number: str | None = None,
    ) -> tuple[list[DocumentHistoryRecord], int]:
        """Retourne une projection paginée sans charger le CV ni le résultat."""
        filters = [DocumentJob.client_id == client_id]
        if document_type is not None:
            filters.append(DocumentJob.document_type == document_type)
        if status is not None:
            filters.append(DocumentJob.status == status)
        if avp_number is not None:
            filters.append(func.btrim(DocumentJob.avp_number) == avp_number.strip())

        candidate_value = DocumentJob.resume_data["basics"]["name"]
        candidate_name = case(
            (
                func.jsonb_typeof(candidate_value) == "string",
                func.nullif(func.btrim(candidate_value.astext), ""),
            ),
            else_=None,
        ).label("candidate_name")
        statement = (
            select(
                DocumentJob.id,
                DocumentJob.document_type,
                DocumentJob.status,
                DocumentJob.avp_number,
                candidate_name,
                DocumentJob.created_at,
                DocumentJob.started_at,
                DocumentJob.completed_at,
                DocumentJob.cancelled_at,
                DocumentJob.llm_model,
            )
            .where(*filters)
            .order_by(DocumentJob.created_at.desc(), DocumentJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
        count_statement = select(func.count(DocumentJob.id)).where(*filters)

        rows = (await self._session.execute(statement)).all()
        total = (await self._session.execute(count_statement)).scalar_one()
        items = [
            DocumentHistoryRecord(
                id=row.id,
                document_type=row.document_type,
                status=row.status,
                avp_number=row.avp_number,
                candidate_name=row.candidate_name,
                created_at=row.created_at,
                started_at=row.started_at,
                completed_at=row.completed_at,
                cancelled_at=row.cancelled_at,
                llm_model=row.llm_model,
            )
            for row in rows
        ]
        return items, total

    async def list_distinct_avp_numbers_for_client(
        self,
        *,
        client_id: uuid.UUID,
        prefix: str | None = None,
    ) -> list[str]:
        """Retourne tous les AVP distincts d'un client, sans charger ses jobs."""
        normalized_avp = func.btrim(DocumentJob.avp_number).label("avp_number")
        filters = [DocumentJob.client_id == client_id]
        if prefix:
            escaped_prefix = (
                prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            filters.append(normalized_avp.ilike(f"{escaped_prefix}%", escape="\\"))
        statement = (
            select(normalized_avp)
            .where(*filters, normalized_avp != "")
            .group_by(normalized_avp)
            .order_by(func.lower(normalized_avp), normalized_avp)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def update(self, job: DocumentJob) -> DocumentJob:
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def reserve_next_pending(self, *, now: datetime) -> DocumentJob | None:
        """
        Réserve atomiquement le plus ancien job en attente.

        Le verrou PostgreSQL `FOR UPDATE SKIP LOCKED` empêche plusieurs workers
        de réserver simultanément le même job.
        """
        from app.core.config import get_settings

        configuration = await get_llm_configuration_for_update(
            self._session, fallback_model=get_settings().llm_model
        )
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
        if job.llm_model is None:
            job.llm_model = configuration.selected_model
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
        """Termine un job seulement si sa réservation est toujours la même."""
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
        """Met un job en échec seulement si sa réservation est toujours la même."""
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
    ) -> StaleJobRecovery:
        """Réactive ou annule les traitements périmés selon leur clé."""
        # Même premier verrou que création, réservation et activation. Une
        # activation ne peut ainsi observer aucun interstice PROCESSING -> PENDING.
        await lock_llm_configuration(self._session)
        stale_filters = (
            DocumentJob.status == DocumentJobStatus.PROCESSING,
            DocumentJob.started_at < cutoff,
        )
        stale_key_ids = (
            select(DocumentJob.api_key_id)
            .where(*stale_filters, DocumentJob.api_key_id.is_not(None))
            .group_by(DocumentJob.api_key_id)
        )
        locked_keys = list(
            (
                await self._session.scalars(
                    select(ApiKey)
                    .where(ApiKey.id.in_(stale_key_ids))
                    .order_by(ApiKey.id)
                    .with_for_update()
                )
            ).all()
        )
        revoked_key_ids = [key.id for key in locked_keys if key.revoked_at is not None]
        cancelled_ids: list[uuid.UUID] = []
        if revoked_key_ids:
            cancelled = (
                update(DocumentJob)
                .where(*stale_filters, DocumentJob.api_key_id.in_(revoked_key_ids))
                .values(
                    status=DocumentJobStatus.CANCELLED,
                    cancelled_at=now,
                    cancellation_reason="api_key_revoked",
                    updated_at=now,
                )
                .returning(DocumentJob.id)
            )
            cancelled_ids = list(
                (await self._session.execute(cancelled)).scalars().all()
            )

        requeue_key_filter = or_(
            DocumentJob.api_key_id.is_(None),
            DocumentJob.api_key_id.not_in(revoked_key_ids),
        )
        statement = (
            update(DocumentJob)
            .where(*stale_filters, requeue_key_filter)
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
        return StaleJobRecovery(
            requeued_ids=list(result.scalars().all()),
            cancelled_ids=cancelled_ids,
        )
