import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.database import async_session_factory
from app.main import app
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.repositories.document_job_repository import DocumentJobRepository
from cv_generator_shared.models import ApiClient, ApiKey
from cv_generator_shared.services import ApiKeyService
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url


def _require_isolated_database() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL n'est pas définie")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("TEST_DATABASE_URL doit désigner une base PostgreSQL de test")
    configured_url = make_url(os.environ["DATABASE_URL"])
    if configured_url != url:
        pytest.fail("DATABASE_URL et TEST_DATABASE_URL doivent désigner la même base")


@pytest.mark.asyncio
async def test_http_authentication_and_ownership_with_real_services() -> None:
    _require_isolated_database()
    async with async_session_factory() as setup_session:
        key_service = ApiKeyService(setup_session)
        client_a = await key_service.create_client(name="Client HTTP A")
        key_a_1 = await key_service.create_key(client_a.id, name="Première clé")
        key_a_2 = await key_service.create_key(client_a.id, name="Deuxième clé")
        client_b = await key_service.create_client(name="Client HTTP B")
        key_b = await key_service.create_key(client_b.id)

    transport = httpx.ASGITransport(app=app)
    job_id: uuid.UUID | None = None
    extra_job_ids: list[uuid.UUID] = []
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            created = await client.post(
                "/api/v1/documents/cv",
                headers={"X-API-Key": key_a_1.value},
                json={
                    "avp_number": "1234-26-001",
                    "resume": {"basics": {"name": "Camille Exemple"}},
                },
            )
            assert created.status_code == 202
            job_id = uuid.UUID(created.json()["id"])

            async with async_session_factory() as verification_session:
                job = await verification_session.scalar(
                    select(DocumentJob).where(DocumentJob.id == job_id)
                )
                assert job is not None
                assert job.client_id == client_a.id
                assert job.api_key_id == key_a_1.key.id

            now = datetime.now(UTC)
            pending_same_key = DocumentJob(
                client_id=client_a.id,
                api_key_id=key_a_1.key.id,
                document_type=DocumentType.CV,
                status=DocumentJobStatus.PENDING,
                avp_number="PENDING-SAME-KEY",
                resume_data={"basics": {}},
            )
            processing_same_key = DocumentJob(
                client_id=client_a.id,
                api_key_id=key_a_1.key.id,
                document_type=DocumentType.CV,
                status=DocumentJobStatus.PROCESSING,
                avp_number="PROCESSING-SAME-KEY",
                resume_data={"basics": {}},
                started_at=now,
            )
            pending_other_key = DocumentJob(
                client_id=client_a.id,
                api_key_id=key_a_2.key.id,
                document_type=DocumentType.CV,
                status=DocumentJobStatus.PENDING,
                avp_number="PENDING-OTHER-KEY",
                resume_data={"basics": {}},
            )
            legacy_pending = DocumentJob(
                client_id=client_a.id,
                api_key_id=None,
                document_type=DocumentType.CV,
                status=DocumentJobStatus.PENDING,
                avp_number="LEGACY-PENDING",
                resume_data={"basics": {}},
            )
            async with async_session_factory() as setup_jobs, setup_jobs.begin():
                setup_jobs.add_all(
                    [
                        pending_same_key,
                        processing_same_key,
                        pending_other_key,
                        legacy_pending,
                    ]
                )
            extra_job_ids = [
                pending_same_key.id,
                processing_same_key.id,
                pending_other_key.id,
                legacy_pending.id,
            ]

            same_client = await client.get(
                f"/api/v1/documents/{job_id}/status",
                headers={"X-API-Key": key_a_2.value},
            )
            other_client = await client.get(
                f"/api/v1/documents/{job_id}/status",
                headers={"X-API-Key": key_b.value},
            )
            assert same_client.status_code == 200
            assert other_client.status_code == 404
            assert "resume" not in other_client.text

            history_same_client = await client.get(
                "/api/v1/documents",
                headers={"X-API-Key": key_a_2.value},
            )
            history_other_client = await client.get(
                "/api/v1/documents",
                headers={"X-API-Key": key_b.value},
            )
            assert history_same_client.status_code == 200
            assert history_same_client.json()["total"] == 5
            created_item = next(
                item
                for item in history_same_client.json()["items"]
                if item["id"] == str(job_id)
            )
            assert created_item["candidate_name"] == "Camille Exemple"
            assert history_other_client.status_code == 200
            assert history_other_client.json()["items"] == []

            avps_same_client = await client.get(
                "/api/v1/documents/avp-numbers",
                headers={"X-API-Key": key_a_2.value},
            )
            avps_other_client = await client.get(
                "/api/v1/documents/avp-numbers",
                headers={"X-API-Key": key_b.value},
            )
            assert "1234-26-001" in avps_same_client.json()["items"]
            assert avps_other_client.json() == {"items": []}

            async with async_session_factory() as revoke_session:
                await ApiKeyService(revoke_session).revoke_key(key_a_1.key.id)
                await ApiKeyService(revoke_session).revoke_key(key_a_1.key.id)
            revoked = await client.get(
                f"/api/v1/documents/{job_id}/status",
                headers={"X-API-Key": key_a_1.value},
            )
            assert revoked.status_code == 401
            assert key_a_1.value not in revoked.text
            async with async_session_factory() as verification_session:
                job = await verification_session.get(DocumentJob, job_id)
                assert job is not None
                assert job.status.value == "cancelled"
                assert job.cancelled_at is not None
                assert job.cancellation_reason == "api_key_revoked"
                statuses = dict(
                    (
                        await verification_session.execute(
                            select(DocumentJob.id, DocumentJob.status).where(
                                DocumentJob.id.in_(extra_job_ids)
                            )
                        )
                    ).all()
                )
                assert statuses[pending_same_key.id] is DocumentJobStatus.CANCELLED
                assert statuses[processing_same_key.id] is DocumentJobStatus.PROCESSING
                assert statuses[pending_other_key.id] is DocumentJobStatus.PENDING
                assert statuses[legacy_pending.id] is DocumentJobStatus.PENDING

            async with (
                async_session_factory() as recovery_session,
                recovery_session.begin(),
            ):
                recovery = await DocumentJobRepository(
                    recovery_session
                ).requeue_stale_jobs(
                    cutoff=now + timedelta(seconds=1),
                    now=now + timedelta(seconds=2),
                )
                assert processing_same_key.id in recovery.cancelled_ids
                assert processing_same_key.id not in recovery.requeued_ids
            async with async_session_factory() as verification_session:
                recovered_job = await verification_session.get(
                    DocumentJob, processing_same_key.id
                )
                assert recovered_job is not None
                assert recovered_job.status is DocumentJobStatus.CANCELLED
    finally:
        async with async_session_factory() as cleanup_session, cleanup_session.begin():
            if job_id is not None:
                await cleanup_session.execute(
                    delete(DocumentJob).where(
                        DocumentJob.id.in_([job_id, *extra_job_ids])
                    )
                )
            await cleanup_session.execute(
                delete(ApiKey).where(ApiKey.client_id.in_([client_a.id, client_b.id]))
            )
            await cleanup_session.execute(
                delete(ApiClient).where(ApiClient.id.in_([client_a.id, client_b.id]))
            )
