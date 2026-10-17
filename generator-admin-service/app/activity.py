import math
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from cv_generator_shared.document_jobs import (
    DocumentJob,
    DocumentJobStatus,
    DocumentType,
)
from cv_generator_shared.models import ApiClient
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement


@dataclass(frozen=True, slots=True)
class ActivityFilters:
    client_id: uuid.UUID | None = None
    document_type: DocumentType | None = None
    status: DocumentJobStatus | None = None
    avp_number: str | None = None
    created_from: date | None = None
    created_to: date | None = None
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True, slots=True)
class ActivityCounters:
    pending: int
    processing: int
    completed_today: int
    failed_today: int


@dataclass(frozen=True, slots=True)
class ActivityJob:
    id: uuid.UUID
    client_id: uuid.UUID | None
    owner_name: str | None
    owner_active: bool | None
    document_type: DocumentType
    status: DocumentJobStatus
    avp_number: str
    candidate_name: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    counters: ActivityCounters
    recent: list[ActivityJob]
    history: list[ActivityJob]
    total: int
    page: int
    page_size: int
    page_count: int
    refreshed_at: datetime


class AdminActivityService:
    """Lecture seule de l'activité de génération, sans résultat ni CV complet."""

    def __init__(self, session: AsyncSession, timezone: ZoneInfo) -> None:
        self._session = session
        self._timezone = timezone

    async def list_clients(self) -> list[ApiClient]:
        statement = select(ApiClient).order_by(
            func.lower(ApiClient.name), ApiClient.name, ApiClient.id
        )
        return list((await self._session.scalars(statement)).all())

    async def snapshot(
        self, filters: ActivityFilters, *, now: datetime | None = None
    ) -> ActivitySnapshot:
        moment = now or datetime.now(UTC)
        day_start_local = datetime.combine(
            moment.astimezone(self._timezone).date(), time.min, self._timezone
        )
        day_start = day_start_local.astimezone(UTC)
        day_end = (day_start_local + timedelta(days=1)).astimezone(UTC)

        counters_statement = select(
            func.count(DocumentJob.id)
            .filter(DocumentJob.status == DocumentJobStatus.PENDING)
            .label("pending"),
            func.count(DocumentJob.id)
            .filter(DocumentJob.status == DocumentJobStatus.PROCESSING)
            .label("processing"),
            func.count(DocumentJob.id)
            .filter(
                DocumentJob.status == DocumentJobStatus.COMPLETED,
                DocumentJob.completed_at >= day_start,
                DocumentJob.completed_at < day_end,
            )
            .label("completed_today"),
            func.count(DocumentJob.id)
            .filter(
                DocumentJob.status == DocumentJobStatus.FAILED,
                DocumentJob.completed_at >= day_start,
                DocumentJob.completed_at < day_end,
            )
            .label("failed_today"),
        )
        counter_row = (await self._session.execute(counters_statement)).one()

        recent = await self._list_jobs(limit=10, offset=0, conditions=[])
        conditions = self._conditions(filters)
        total = int(
            await self._session.scalar(
                select(func.count(DocumentJob.id)).where(*conditions)
            )
            or 0
        )
        page_count = max(1, math.ceil(total / filters.page_size))
        page = min(max(filters.page, 1), page_count)
        history = await self._list_jobs(
            limit=filters.page_size,
            offset=(page - 1) * filters.page_size,
            conditions=conditions,
        )
        return ActivitySnapshot(
            counters=ActivityCounters(
                pending=counter_row.pending,
                processing=counter_row.processing,
                completed_today=counter_row.completed_today,
                failed_today=counter_row.failed_today,
            ),
            recent=recent,
            history=history,
            total=total,
            page=page,
            page_size=filters.page_size,
            page_count=page_count,
            refreshed_at=moment,
        )

    def _conditions(self, filters: ActivityFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.client_id is not None:
            conditions.append(DocumentJob.client_id == filters.client_id)
        if filters.document_type is not None:
            conditions.append(DocumentJob.document_type == filters.document_type)
        if filters.status is not None:
            conditions.append(DocumentJob.status == filters.status)
        if filters.avp_number:
            conditions.append(
                func.btrim(DocumentJob.avp_number) == filters.avp_number.strip()
            )
        if filters.created_from is not None:
            start = datetime.combine(
                filters.created_from, time.min, self._timezone
            ).astimezone(UTC)
            conditions.append(DocumentJob.created_at >= start)
        if filters.created_to is not None:
            end = datetime.combine(
                filters.created_to + timedelta(days=1), time.min, self._timezone
            ).astimezone(UTC)
            conditions.append(DocumentJob.created_at < end)
        return conditions

    async def _list_jobs(
        self,
        *,
        limit: int,
        offset: int,
        conditions: list[ColumnElement[bool]],
    ) -> list[ActivityJob]:
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
                DocumentJob.client_id,
                ApiClient.name.label("owner_name"),
                ApiClient.is_active.label("owner_active"),
                DocumentJob.document_type,
                DocumentJob.status,
                DocumentJob.avp_number,
                candidate_name,
                DocumentJob.created_at,
                DocumentJob.started_at,
                DocumentJob.completed_at,
                DocumentJob.cancelled_at,
            )
            .outerjoin(ApiClient, ApiClient.id == DocumentJob.client_id)
            .where(*conditions)
            .order_by(DocumentJob.created_at.desc(), DocumentJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(statement)).all()
        return [ActivityJob(**row._mapping) for row in rows]
