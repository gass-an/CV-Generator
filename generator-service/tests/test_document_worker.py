import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.processors.document_processor import DocumentJobData, GeneratedDocument
from app.repositories.document_job_repository import DocumentJobRepository
from app.services.document_worker_service import DocumentWorkerService
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession


def make_job(
    status: DocumentJobStatus,
    *,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
) -> DocumentJob:
    now = datetime.now(UTC)
    return DocumentJob(
        id=uuid.uuid4(),
        document_type=DocumentType.CV,
        status=status,
        avp_number="1234-26-001",
        resume_data={"basics": {}},
        created_at=created_at or now,
        started_at=started_at,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_repository_reserves_pending_job_with_skip_locked() -> None:
    job = make_job(DocumentJobStatus.PENDING)
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = job
    session.execute.return_value = result
    repository = DocumentJobRepository(session)
    now = datetime.now(UTC)

    reserved = await repository.reserve_next_pending(now=now)

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert reserved is job
    assert job.status is DocumentJobStatus.PROCESSING
    assert job.started_at == now
    assert job.updated_at == now
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_returns_none_when_no_job_is_available() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    reserved = await DocumentJobRepository(session).reserve_next_pending(
        now=datetime.now(UTC)
    )

    assert reserved is None
    session.flush.assert_not_awaited()


class FakeWorkerState:
    def __init__(self, jobs: list[DocumentJob]) -> None:
        self.jobs = jobs


class FakeTransaction:
    def __init__(self, factory: "FakeSessionFactory") -> None:
        self._factory = factory

    async def __aenter__(self) -> None:
        assert not self._factory.transaction_active
        self._factory.transaction_active = True

    async def __aexit__(self, *args: object) -> None:
        self._factory.transaction_active = False


class FakeSession:
    def __init__(self, factory: "FakeSessionFactory") -> None:
        self.factory = factory

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        assert not self.factory.transaction_active

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self.factory)


class FakeSessionFactory:
    def __init__(self) -> None:
        self.transaction_active = False

    def __call__(self) -> FakeSession:
        return FakeSession(self)


class FakeWorkerRepository:
    state: FakeWorkerState

    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def _assert_transaction(self) -> None:
        assert self._session.factory.transaction_active

    async def reserve_next_pending(self, *, now: datetime) -> DocumentJob | None:
        self._assert_transaction()
        pending = [
            job for job in self.state.jobs if job.status is DocumentJobStatus.PENDING
        ]
        if not pending:
            return None
        job = min(pending, key=lambda item: (item.created_at, item.id))
        job.status = DocumentJobStatus.PROCESSING
        job.started_at = now
        job.updated_at = now
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
        self._assert_transaction()
        job = self._find(job_id)
        if job.started_at != expected_started_at:
            return False
        job.status = DocumentJobStatus.COMPLETED
        job.result_content = result_content
        job.result_format = result_format
        job.completed_at = now
        job.updated_at = now
        return True

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        *,
        error_code: str,
        error_message: str,
        expected_started_at: datetime,
        now: datetime,
    ) -> bool:
        self._assert_transaction()
        job = self._find(job_id)
        if job.started_at != expected_started_at:
            return False
        job.status = DocumentJobStatus.FAILED
        job.error_code = error_code
        job.error_message = error_message
        job.completed_at = now
        job.updated_at = now
        return True

    async def requeue_stale_jobs(
        self,
        *,
        cutoff: datetime,
        now: datetime,
    ) -> list[uuid.UUID]:
        self._assert_transaction()
        stale_ids: list[uuid.UUID] = []
        for job in self.state.jobs:
            if (
                job.status is DocumentJobStatus.PROCESSING
                and job.started_at is not None
                and job.started_at < cutoff
            ):
                job.status = DocumentJobStatus.PENDING
                job.started_at = None
                job.error_code = None
                job.error_message = None
                job.updated_at = now
                stale_ids.append(job.id)
        return stale_ids

    def _find(self, job_id: uuid.UUID) -> DocumentJob:
        return next(job for job in self.state.jobs if job.id == job_id)


class SuccessProcessor:
    def __init__(self, session_factory: FakeSessionFactory) -> None:
        self._session_factory = session_factory

    async def process(self, job: DocumentJobData) -> GeneratedDocument:
        assert not self._session_factory.transaction_active
        return GeneratedDocument(
            content=f"= CV généré\n\nAVP : {job.avp_number}\n",
            format="asciidoc",
        )


class FailOnceProcessor(SuccessProcessor):
    def __init__(self, session_factory: FakeSessionFactory) -> None:
        super().__init__(session_factory)
        self._call_count = 0

    async def process(self, job: DocumentJobData) -> GeneratedDocument:
        assert not self._session_factory.transaction_active
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("secret-token-must-not-be-stored")
        return await super().process(job)


def make_worker(
    jobs: list[DocumentJob],
    processor: Any,
    session_factory: FakeSessionFactory,
    *,
    stale_timeout: float = 600,
) -> DocumentWorkerService:
    FakeWorkerRepository.state = FakeWorkerState(jobs)
    return DocumentWorkerService(
        session_factory=session_factory,  # type: ignore[arg-type]
        processor=processor,
        poll_interval_seconds=0.01,
        stale_job_timeout_seconds=stale_timeout,
        repository_factory=FakeWorkerRepository,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_success_processing_closes_reservation_transaction() -> None:
    job = make_job(DocumentJobStatus.PENDING)
    session_factory = FakeSessionFactory()
    worker = make_worker(
        [job],
        SuccessProcessor(session_factory),
        session_factory,
    )

    processed = await worker.process_next_job()

    assert processed is True
    assert job.status is DocumentJobStatus.COMPLETED
    assert job.result_format == "asciidoc"
    assert job.result_content == "= CV généré\n\nAVP : 1234-26-001\n"
    assert job.completed_at is not None
    assert not session_factory.transaction_active


@pytest.mark.asyncio
async def test_processor_error_fails_job_and_worker_can_process_next_job() -> None:
    first_job = make_job(
        DocumentJobStatus.PENDING,
        created_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    second_job = make_job(DocumentJobStatus.PENDING)
    session_factory = FakeSessionFactory()
    worker = make_worker(
        [first_job, second_job],
        FailOnceProcessor(session_factory),
        session_factory,
    )

    assert await worker.process_next_job() is True
    assert await worker.process_next_job() is True

    assert first_job.status is DocumentJobStatus.FAILED
    assert first_job.error_code == "unexpected_processing_error"
    assert first_job.error_message == "Unexpected document processing error"
    assert "secret-token" not in first_job.error_message
    assert first_job.completed_at is not None
    assert second_job.status is DocumentJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_recovery_only_requeues_stale_processing_jobs() -> None:
    now = datetime.now(UTC)
    stale_job = make_job(
        DocumentJobStatus.PROCESSING,
        started_at=now - timedelta(seconds=601),
    )
    recent_job = make_job(
        DocumentJobStatus.PROCESSING,
        started_at=now - timedelta(seconds=10),
    )
    session_factory = FakeSessionFactory()
    worker = make_worker(
        [stale_job, recent_job],
        SuccessProcessor(session_factory),
        session_factory,
        stale_timeout=600,
    )

    recovered_count = await worker.recover_stale_jobs()

    assert recovered_count == 1
    assert stale_job.status is DocumentJobStatus.PENDING
    assert stale_job.started_at is None
    assert recent_job.status is DocumentJobStatus.PROCESSING
    assert recent_job.started_at is not None
