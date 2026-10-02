import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

SERVICE_ROOT = Path(__file__).resolve().parents[1]

WORKER_SCRIPT = r"""
import asyncio
import uuid
from datetime import UTC, datetime

from app.workers.document_worker import validate_worker_configuration
from app.core.database import Base, async_session_factory, engine

assert "api_client" in Base.metadata.tables
assert "document_job" in Base.metadata.tables

from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.repositories.document_job_repository import DocumentJobRepository
from cv_generator_shared.models import ApiClient
from sqlalchemy import delete


async def verify_worker_database_operation() -> None:
    client_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with async_session_factory() as session, session.begin():
            session.add(ApiClient(id=client_id, name="Client worker", created_at=now))
            await session.flush()
            session.add(
                DocumentJob(
                    id=job_id,
                    client_id=client_id,
                    document_type=DocumentType.CV,
                    status=DocumentJobStatus.PENDING,
                    avp_number="WORKER-TEST",
                    resume_data={"basics": {}},
                    created_at=now,
                    updated_at=now,
                )
            )

        async with async_session_factory() as session, session.begin():
            reserved = await DocumentJobRepository(session).reserve_next_pending(
                now=now
            )
            assert reserved is not None
            assert reserved.id == job_id
            assert reserved.client_id == client_id
            assert reserved.status is DocumentJobStatus.PROCESSING
    finally:
        async with async_session_factory() as session, session.begin():
            await session.execute(delete(DocumentJob).where(DocumentJob.id == job_id))
            await session.execute(delete(ApiClient).where(ApiClient.id == client_id))
        await engine.dispose()


validate_worker_configuration(llm_base_url="http://llm.test", llm_model="test")
asyncio.run(verify_worker_database_operation())
print("worker-postgresql-ok")
"""


def test_worker_starts_in_fresh_process_and_reserves_owned_job() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL n'est pas définie")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("TEST_DATABASE_URL doit désigner une base PostgreSQL de test")

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-c", WORKER_SCRIPT],
        cwd=SERVICE_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "worker-postgresql-ok"
