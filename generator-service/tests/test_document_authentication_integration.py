import os
import uuid

import httpx
import pytest
from app.core.database import async_session_factory
from app.main import app
from app.models.document_job import DocumentJob
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
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            created = await client.post(
                "/api/v1/documents/cv",
                headers={"X-API-Key": key_a_1.value},
                json={"avp_number": "1234-26-001", "resume": {"basics": {}}},
            )
            assert created.status_code == 202
            job_id = uuid.UUID(created.json()["id"])

            async with async_session_factory() as verification_session:
                job = await verification_session.scalar(
                    select(DocumentJob).where(DocumentJob.id == job_id)
                )
                assert job is not None
                assert job.client_id == client_a.id

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

            async with async_session_factory() as revoke_session:
                await ApiKeyService(revoke_session).revoke_key(key_a_1.key.id)
            revoked = await client.get(
                f"/api/v1/documents/{job_id}/status",
                headers={"X-API-Key": key_a_1.value},
            )
            assert revoked.status_code == 401
            assert key_a_1.value not in revoked.text
    finally:
        async with async_session_factory() as cleanup_session, cleanup_session.begin():
            if job_id is not None:
                await cleanup_session.execute(
                    delete(DocumentJob).where(DocumentJob.id == job_id)
                )
            await cleanup_session.execute(
                delete(ApiKey).where(ApiKey.client_id.in_([client_a.id, client_b.id]))
            )
            await cleanup_session.execute(
                delete(ApiClient).where(ApiClient.id.in_([client_a.id, client_b.id]))
            )
