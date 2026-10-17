import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.database import async_session_factory, engine
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.repositories.document_job_repository import DocumentJobRepository
from cv_generator_shared.models import ApiClient, ApiKey
from cv_generator_shared.repositories import ApiKeyRepository
from cv_generator_shared.services import ApiKeyService
from sqlalchemy import delete, select, text, update
from sqlalchemy.engine import make_url


def _require_postgresql_test_database() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL n'est pas définie")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("TEST_DATABASE_URL doit désigner une base PostgreSQL de test")
    if make_url(os.environ["DATABASE_URL"]) != url:
        pytest.fail("DATABASE_URL et TEST_DATABASE_URL doivent désigner la même base")


def _job(
    *,
    client_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    status: DocumentJobStatus,
    avp_number: str,
    started_at: datetime | None = None,
) -> DocumentJob:
    return DocumentJob(
        client_id=client_id,
        api_key_id=api_key_id,
        document_type=DocumentType.CV,
        status=status,
        avp_number=avp_number,
        resume_data={"basics": {}},
        started_at=started_at,
    )


@pytest.mark.asyncio
async def test_recovery_waits_for_concurrent_revocation_before_requeueing() -> None:
    _require_postgresql_test_database()
    async with async_session_factory() as setup_session:
        service = ApiKeyService(setup_session)
        client = await service.create_client(name="Concurrence récupération")
        revoked_key = await service.create_key(client.id, name="À révoquer")
        other_key = await service.create_key(client.id, name="À conserver")
    now = datetime.now(UTC)
    stale_started_at = now - timedelta(minutes=20)
    cutoff = now - timedelta(minutes=10)

    pending_revoked = _job(
        client_id=client.id,
        api_key_id=revoked_key.key.id,
        status=DocumentJobStatus.PENDING,
        avp_number="CONCURRENT-PENDING",
    )
    stale_revoked = _job(
        client_id=client.id,
        api_key_id=revoked_key.key.id,
        status=DocumentJobStatus.PROCESSING,
        avp_number="CONCURRENT-STALE",
        started_at=stale_started_at,
    )
    recent_revoked = _job(
        client_id=client.id,
        api_key_id=revoked_key.key.id,
        status=DocumentJobStatus.PROCESSING,
        avp_number="CONCURRENT-RECENT",
        started_at=now,
    )
    stale_other = _job(
        client_id=client.id,
        api_key_id=other_key.key.id,
        status=DocumentJobStatus.PROCESSING,
        avp_number="CONCURRENT-OTHER",
        started_at=stale_started_at,
    )
    stale_legacy = _job(
        client_id=client.id,
        api_key_id=None,
        status=DocumentJobStatus.PROCESSING,
        avp_number="CONCURRENT-LEGACY",
        started_at=stale_started_at,
    )
    jobs = [
        pending_revoked,
        stale_revoked,
        recent_revoked,
        stale_other,
        stale_legacy,
    ]
    async with async_session_factory() as setup_session, setup_session.begin():
        setup_session.add_all(jobs)

    revocation_ready = asyncio.Event()
    allow_revocation_commit = asyncio.Event()
    recovery_pid_ready = asyncio.Event()
    recovery_pid: int | None = None

    async def revoke_without_committing() -> None:
        async with async_session_factory() as session, session.begin():
            key = await ApiKeyRepository(session).get_by_id(
                revoked_key.key.id, for_update=True
            )
            assert key is not None
            key.revoked_at = now
            await session.execute(
                update(DocumentJob)
                .where(
                    DocumentJob.api_key_id == key.id,
                    DocumentJob.status == DocumentJobStatus.PENDING,
                )
                .values(
                    status=DocumentJobStatus.CANCELLED,
                    cancelled_at=now,
                    cancellation_reason="api_key_revoked",
                    updated_at=now,
                )
            )
            await session.flush()
            revocation_ready.set()
            await allow_revocation_commit.wait()

    async def recover_concurrently():
        nonlocal recovery_pid
        await revocation_ready.wait()
        async with async_session_factory() as session, session.begin():
            recovery_pid = int(await session.scalar(text("SELECT pg_backend_pid()")))
            recovery_pid_ready.set()
            return await DocumentJobRepository(session).requeue_stale_jobs(
                cutoff=cutoff,
                now=now + timedelta(seconds=1),
            )

    revoke_task = asyncio.create_task(revoke_without_committing())
    recovery_task = asyncio.create_task(recover_concurrently())
    try:
        await recovery_pid_ready.wait()
        assert recovery_pid is not None
        async with async_session_factory() as observer:
            wait_event_query = text(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"
            )
            for _ in range(100):
                wait_event_type = await observer.scalar(
                    wait_event_query,
                    {"pid": recovery_pid},
                )
                if wait_event_type == "Lock":
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("La récupération n'a pas attendu le verrou de la clé")

        allow_revocation_commit.set()
        await revoke_task
        recovery = await recovery_task

        async with async_session_factory() as verification_session:
            rows = await verification_session.execute(
                select(DocumentJob.id, DocumentJob.status).where(
                    DocumentJob.id.in_([job.id for job in jobs])
                )
            )
            statuses = dict(rows.all())
        assert statuses[pending_revoked.id] is DocumentJobStatus.CANCELLED
        assert statuses[stale_revoked.id] is DocumentJobStatus.CANCELLED
        assert statuses[recent_revoked.id] is DocumentJobStatus.PROCESSING
        assert statuses[stale_other.id] is DocumentJobStatus.PENDING
        assert statuses[stale_legacy.id] is DocumentJobStatus.PENDING
        assert stale_revoked.id in recovery.cancelled_ids
        assert stale_other.id in recovery.requeued_ids
        assert stale_legacy.id in recovery.requeued_ids
        assert all(
            status is not DocumentJobStatus.PENDING
            for job_id, status in statuses.items()
            if job_id in {pending_revoked.id, stale_revoked.id, recent_revoked.id}
        )
    finally:
        allow_revocation_commit.set()
        await asyncio.gather(revoke_task, recovery_task, return_exceptions=True)
        async with async_session_factory() as cleanup_session, cleanup_session.begin():
            await cleanup_session.execute(
                delete(DocumentJob).where(DocumentJob.id.in_([job.id for job in jobs]))
            )
            await cleanup_session.execute(
                delete(ApiKey).where(ApiKey.client_id == client.id)
            )
            await cleanup_session.execute(
                delete(ApiClient).where(ApiClient.id == client.id)
            )
        await engine.dispose()
